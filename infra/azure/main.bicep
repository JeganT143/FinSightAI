// FinSightAI on Azure Container Apps (SAAS §11, adapted from the AWS plan —
// decision recorded in SAAS_ARCHITECTURE.md §11: ~$100 student credits fund
// ~5-6 months of this footprint).
//
//   finsight-web    Next.js  — external ingress, custom domain finsightai.jegant.dev
//   finsight-api    FastAPI  — external ingress (api.finsightai.jegant.dev), CORS-locked
//   finsight-worker Arq      — no ingress, same image as api, scale 0-1
//   finsight-redis  redis:7  — internal TCP only; queue broker (no persistence:
//                              a lost in-flight job re-enqueues; accepted + documented)
//   Postgres Flexible Server B1ms — pgvector enabled; cheapest HA-less burstable
//
// Validate: az deployment group what-if -g finsightai-rg -f main.bicep -p @params.json
// Custom domains + managed certs are bound AFTER first deploy (see DEPLOYMENT.md §5).

@description('Region for everything; pick one close to you with B1ms capacity')
param location string = resourceGroup().location

@secure()
param postgresPassword string
@secure()
param openaiApiKey string
@secure()
param clerkSecretKey string = ''
@secure()
param stripeSecretKey string = ''
@secure()
param stripeWebhookSecret string = ''

param clerkIssuer string = ''
param stripePricePro string = ''
param appDomain string = 'finsightai.jegant.dev'
param apiDomain string = 'api.finsightai.jegant.dev'

@description('Container images (pushed to GHCR by the deploy workflow)')
param apiImage string
param webImage string

@description('GHCR pull credentials (a read:packages PAT)')
param ghcrUsername string
@secure()
param ghcrToken string

var pgServerName = 'finsight-pg-${uniqueString(resourceGroup().id)}'

// --- Observability sink (Container Apps requires one; free tier ingestion) ---
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'finsight-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// --- Container Apps environment (Consumption: scale-to-zero, per-second billing) ---
resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'finsight-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// --- Postgres (pgvector) ---
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: pgServerName
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: 'finsight'
    administratorLoginPassword: postgresPassword
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
  }
}

resource pgDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: postgres
  name: 'finsight'
}

// pgvector must be allowlisted before CREATE EXTENSION works (ADR-5).
resource pgExtensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-12-01-preview' = {
  parent: postgres
  name: 'azure.extensions'
  properties: { value: 'VECTOR', source: 'user-override' }
}

// Demo-scale simplification: allow Azure-internal traffic instead of VNet
// peering (a paid feature footprint). Documented trade-off in DEPLOYMENT.md.
resource pgFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgres
  name: 'allow-azure-services'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

var databaseUrl = 'postgresql+asyncpg://finsight:${postgresPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/finsight?ssl=require'

var ghcrRegistry = {
  server: 'ghcr.io'
  username: ghcrUsername
  passwordSecretRef: 'ghcr-token'
}

// --- Redis (queue broker; internal TCP, no persistence) ---
resource redisApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'finsight-redis'
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: false
        targetPort: 6379
        transport: 'tcp'
      }
    }
    template: {
      containers: [
        {
          name: 'redis'
          image: 'redis:7-alpine'
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

var redisUrl = 'redis://finsight-redis:6379/0'

var apiSecrets = [
  { name: 'openai-api-key', value: openaiApiKey }
  { name: 'database-url', value: databaseUrl }
  { name: 'clerk-secret-key', value: clerkSecretKey }
  { name: 'stripe-secret-key', value: stripeSecretKey }
  { name: 'stripe-webhook-secret', value: stripeWebhookSecret }
  { name: 'ghcr-token', value: ghcrToken }
]

var apiEnv = [
  { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'STRIPE_SECRET_KEY', secretRef: 'stripe-secret-key' }
  { name: 'STRIPE_WEBHOOK_SECRET', secretRef: 'stripe-webhook-secret' }
  { name: 'STRIPE_PRICE_PRO', value: stripePricePro }
  { name: 'AUTH_MODE', value: empty(clerkIssuer) ? 'disabled' : 'clerk' }
  { name: 'CLERK_ISSUER', value: clerkIssuer }
  { name: 'CLERK_AUTHORIZED_PARTIES', value: '["https://${appDomain}"]' }
  { name: 'CORS_ORIGINS', value: '["https://${appDomain}"]' }
  { name: 'QUEUE_ENABLED', value: 'true' }
  { name: 'REDIS_URL', value: redisUrl }
  { name: 'LOG_FORMAT', value: 'json' }
  { name: 'BILLING_SUCCESS_URL', value: 'https://${appDomain}/account/billing?upgraded=1' }
  { name: 'BILLING_CANCEL_URL', value: 'https://${appDomain}/pricing' }
]

// --- API ---
resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'finsight-api'
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
      }
      registries: [ghcrRegistry]
      secrets: apiSecrets
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: apiEnv
          probes: [
            {
              type: 'Readiness'
              httpGet: { path: '/health/ready', port: 8000 }
              initialDelaySeconds: 20
              periodSeconds: 15
            }
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8000 }
              initialDelaySeconds: 20
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0 // scale-to-zero: cold start ~5s, credits last months longer
        maxReplicas: 2
        rules: [
          {
            name: 'http'
            http: { metadata: { concurrentRequests: '50' } }
          }
        ]
      }
    }
  }
}

// --- Worker (same image, arq command, never exposed) ---
resource workerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'finsight-worker'
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      registries: [ghcrRegistry]
      secrets: apiSecrets
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: apiImage
          command: ['arq', 'backend.worker.WorkerSettings']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: apiEnv
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

// --- Web ---
resource webApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'finsight-web'
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 3000
        transport: 'http'
      }
      registries: [ghcrRegistry]
      secrets: [
        { name: 'clerk-secret-key', value: clerkSecretKey }
        { name: 'ghcr-token', value: ghcrToken }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: webImage
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: [
            { name: 'BACKEND_URL', value: 'https://${apiDomain}' }
            { name: 'CLERK_SECRET_KEY', secretRef: 'clerk-secret-key' }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 2 }
    }
  }
}

output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output webFqdn string = webApp.properties.configuration.ingress.fqdn
output webVerificationId string = webApp.properties.customDomainVerificationId
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName
