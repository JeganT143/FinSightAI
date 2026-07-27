// FinSightAI on Azure Container Apps — pay-per-use only, no always-on paid
// resources, so cost approaches $0/month once the Azure for Students credit
// is gone (superseded the original Postgres-Flexible-Server plan recorded in
// SAAS_ARCHITECTURE.md §11 — see internal-docs/DEPLOYMENT.md for the change).
//
//   finsight-web      Next.js    — external ingress, custom domain finsightai.jegant.dev
//   finsight-api      FastAPI    — external ingress (api.finsightai.jegant.dev), CORS-locked
//   finsight-postgres pgvector   — internal TCP, scale-to-zero. Data lives on the
//                                  container's own ephemeral disk (Azure Files/SMB can't
//                                  give Postgres the POSIX permissions initdb requires —
//                                  confirmed by a failed deploy, not a guess). That means
//                                  data is wiped on ANY restart, not just scale-to-zero:
//                                  redeploys, crashes, host maintenance too. Accepted for
//                                  a $0-when-idle portfolio demo; not for real user data.
//
// No worker, no Redis: QUEUE_ENABLED=false, so research runs are synchronous
// (the original Phase-1 request/SSE path) instead of queued. An always-on
// Arq worker is the one piece of SAAS §7 that can't scale to zero — running
// it 24/7 costs real money regardless of traffic, which defeats the pay-
// only-for-usage goal of this deploy. Dropped deliberately; revisit if this
// ever needs background/queued execution again (SAAS_ARCHITECTURE.md §7).
//
// Every container app scales to zero when idle (HTTP apps on request count,
// Postgres on active TCP connections) — nothing bills while nobody's using
// the site. Trade-off: a request after idle time pays a cold-start cost
// (API+web ~5s; if Postgres also had to cold-start, the chain can run
// longer) — acceptable for a demo, not for latency-sensitive production use.
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

var ghcrRegistry = {
  server: 'ghcr.io'
  username: ghcrUsername
  passwordSecretRef: 'ghcr-token'
}

// --- Postgres (pgvector, containerized — scale-to-zero on idle TCP conns) ---
resource postgresApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'finsight-postgres'
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: false
        targetPort: 5432
        transport: 'tcp'
      }
      secrets: [
        { name: 'postgres-password', value: postgresPassword }
      ]
    }
    template: {
      containers: [
        {
          name: 'postgres'
          image: 'pgvector/pgvector:pg17'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'POSTGRES_USER', value: 'finsight' }
            { name: 'POSTGRES_PASSWORD', secretRef: 'postgres-password' }
            { name: 'POSTGRES_DB', value: 'finsight' }
          ]
          // No volume: ephemeral container disk. Azure Files (SMB) can't give
          // Postgres the POSIX permissions initdb requires — confirmed by a
          // failed deploy. Data is wiped on any restart; see the header note.
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1 // never >1: a second replica against the same data dir corrupts it
        rules: [
          {
            name: 'tcp-scaling'
            tcp: { metadata: { concurrentConnections: '10' } }
          }
        ]
      }
    }
  }
}

var databaseUrl = 'postgresql+asyncpg://finsight:${postgresPassword}@finsight-postgres:5432/finsight'

// Azure rejects a secret whose value is an empty string — only declare the
// optional ones (Clerk/Stripe) when they're actually filled in.
var apiSecrets = concat(
  [
    { name: 'openai-api-key', value: openaiApiKey }
    { name: 'database-url', value: databaseUrl }
    { name: 'ghcr-token', value: ghcrToken }
  ],
  empty(stripeSecretKey) ? [] : [{ name: 'stripe-secret-key', value: stripeSecretKey }],
  empty(stripeWebhookSecret) ? [] : [{ name: 'stripe-webhook-secret', value: stripeWebhookSecret }]
)

var apiEnv = [
  { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  empty(stripeSecretKey)
    ? { name: 'STRIPE_SECRET_KEY', value: '' }
    : { name: 'STRIPE_SECRET_KEY', secretRef: 'stripe-secret-key' }
  empty(stripeWebhookSecret)
    ? { name: 'STRIPE_WEBHOOK_SECRET', value: '' }
    : { name: 'STRIPE_WEBHOOK_SECRET', secretRef: 'stripe-webhook-secret' }
  { name: 'STRIPE_PRICE_PRO', value: stripePricePro }
  { name: 'AUTH_MODE', value: empty(clerkIssuer) ? 'disabled' : 'clerk' }
  { name: 'CLERK_ISSUER', value: clerkIssuer }
  { name: 'CLERK_AUTHORIZED_PARTIES', value: '["https://${appDomain}"]' }
  { name: 'CORS_ORIGINS', value: '["https://${appDomain}"]' }
  { name: 'QUEUE_ENABLED', value: 'false' }
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
      secrets: concat(
        [{ name: 'ghcr-token', value: ghcrToken }],
        empty(clerkSecretKey) ? [] : [{ name: 'clerk-secret-key', value: clerkSecretKey }]
      )
    }
    template: {
      containers: [
        {
          name: 'web'
          image: webImage
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
          env: [
            { name: 'BACKEND_URL', value: 'https://${apiDomain}' }
            empty(clerkSecretKey)
              ? { name: 'CLERK_SECRET_KEY', value: '' }
              : { name: 'CLERK_SECRET_KEY', secretRef: 'clerk-secret-key' }
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
