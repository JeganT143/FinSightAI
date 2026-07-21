# Deploying FinSightAI to Azure — finsightai.jegant.dev

This is the Azure adaptation of [SAAS_ARCHITECTURE.md](SAAS_ARCHITECTURE.md)
§11–§13, sized for a **$100 Azure for Students budget** (~$15–20/month at
this footprint → roughly 5–6 months of live uptime).

| Piece | Azure resource | ~Cost/mo |
|---|---|---|
| Web + API + worker | Container Apps (Consumption, scale-to-zero) | ~$0–5 |
| Redis (queue broker) | `redis:7` as an internal Container App | ~$1 |
| Postgres + pgvector | Flexible Server `B1ms`, 32 GB | ~$13–15 |
| Images | GitHub Container Registry | $0 |
| Logs | Log Analytics (30-day retention) | ~$0 at this volume |
| TLS certs | Container Apps managed certificates | $0 |

Cost guardrails that protect the budget beyond Azure itself: per-run LLM cost
tracking, `MAX_COST_USD` circuit breaker, per-IP rate limits, per-plan quotas
(free tier = 5 runs/month on the cheapest models), and API scale-to-zero.

---

## 1. One-time: accounts and keys

1. **Azure**: `az login` with your student subscription.
2. **Clerk** (free tier): create an application → copy the *publishable key*
   (`pk_test_…`), *secret key* (`sk_test_…`), and the issuer URL
   (`https://<slug>.clerk.accounts.dev`). Dev-instance keys are fine to start.
3. **Stripe** (test mode): create a product "FinSightAI Pro" with a $19/mo
   recurring price → copy the price id (`price_…`) and your test secret key.
   After deploy, add a webhook endpoint
   `https://api.finsightai.jegant.dev/api/billing/webhook` for the events
   `checkout.session.completed`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `invoice.payment_failed` → copy `whsec_…`.
4. **GHCR**: create a classic PAT with `read:packages` (used by Azure to pull
   images).

## 2. One-time: push the first images

The Deploy workflow does this on every run, but the first infra deploy needs
images to exist:

```bash
echo $GHCR_PAT | docker login ghcr.io -u JeganT143 --password-stdin
docker build -t ghcr.io/jegant143/finsightai-api:latest -f backend/Dockerfile .
docker build -t ghcr.io/jegant143/finsightai-web:latest \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_... \
  --build-arg NEXT_PUBLIC_API_URL=https://api.finsightai.jegant.dev \
  frontend/web
docker push ghcr.io/jegant143/finsightai-api:latest
docker push ghcr.io/jegant143/finsightai-web:latest
```

> `NEXT_PUBLIC_*` values are **inlined at build time** — rebuilding the web
> image is the only way to change them.

## 3. One-time: deploy the infrastructure

```bash
az group create -n finsightai-rg -l westeurope   # any region with B1ms capacity
cp infra/azure/params.example.json infra/azure/params.json  # fill in; gitignored
az deployment group what-if -g finsightai-rg \
  -f infra/azure/main.bicep -p @infra/azure/params.json     # review first
az deployment group create -g finsightai-rg \
  -f infra/azure/main.bicep -p @infra/azure/params.json
```

Outputs include `webFqdn`, `apiFqdn`, and `webVerificationId` — needed next.
Migrations run automatically on API start (the image's CMD), and pgvector is
allowlisted by the Bicep (`azure.extensions=VECTOR`).

## 4. GitHub Actions (repeat deploys)

Create an Entra app registration with **OIDC federated credentials** for this
repo (`az ad app create` + federated credential for
`repo:JeganT143/FinSightAI:ref:refs/heads/main`), grant it Contributor on
`finsightai-rg`, then set:

- Secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
  `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- Variables: `AZURE_RESOURCE_GROUP=finsightai-rg`,
  `NEXT_PUBLIC_API_URL=https://api.finsightai.jegant.dev`

From then on, **Actions → Deploy → Run workflow** builds, pushes, rolls all
three apps, and smoke-checks `/health/ready`.

## 5. The domain: yes, finsightai.jegant.dev works

Since you own `jegant.dev`, subdomains are yours to point wherever you like —
two CNAMEs and two TXT records at your DNS provider:

| Type | Name | Value |
|---|---|---|
| CNAME | `finsightai` | `<webFqdn>` (e.g. `finsight-web.<env>.westeurope.azurecontainerapps.io`) |
| TXT | `asuid.finsightai` | `<webVerificationId>` (deployment output) |
| CNAME | `api.finsightai` | `<apiFqdn>` |
| TXT | `asuid.api.finsightai` | `<webVerificationId>` (same id, per-app check uses it) |

Then bind + free managed TLS:

```bash
az containerapp hostname add -g finsightai-rg -n finsight-web --hostname finsightai.jegant.dev
az containerapp hostname bind -g finsightai-rg -n finsight-web --hostname finsightai.jegant.dev \
  --environment finsight-env --validation-method CNAME
az containerapp hostname add -g finsightai-rg -n finsight-api --hostname api.finsightai.jegant.dev
az containerapp hostname bind -g finsightai-rg -n finsight-api --hostname api.finsightai.jegant.dev \
  --environment finsight-env --validation-method CNAME
```

Certificates are issued and renewed by Azure automatically. Allow a few
minutes for DNS propagation before `bind`.

Afterwards, update Clerk (allowed origins / paths → `https://finsightai.jegant.dev`)
and Stripe (webhook endpoint, §1.3) to the real domain.

## 6. Verify the deployment

```bash
curl https://api.finsightai.jegant.dev/health/ready   # {"status":"ready","database":"up"}
open https://finsightai.jegant.dev                    # storefront -> sign-up -> first run
```

End-to-end: sign up (consent checkbox), run NVDA from /welcome, watch the
live desk, open the dossier, ask the chat "should I buy NVDA?" (fixed
refusal), upgrade with Stripe test card `4242 4242 4242 4242`, confirm the
plan flips to Pro on /account/billing.

## 7. Trade-offs made for the budget (interview-ready)

- **Scale-to-zero API** → first request after idle takes ~5s. Acceptable for
  a portfolio; `minReplicas: 1` fixes it for ~$8/mo more.
- **Redis as a container, no persistence** → in-flight queue jobs are lost if
  it restarts (finished reports are in Postgres; the report row shows
  `running` until re-run). Azure Cache for Redis Basic C0 (~$16/mo) is the
  managed upgrade.
- **Postgres open to Azure-internal traffic** (firewall `0.0.0.0`) instead of
  VNet integration — VNet-injected Container Apps environments carry a cost
  and complexity footprint this stage doesn't justify. Password is strong,
  TLS required.
- **Container Apps secrets** instead of Key Vault — same encrypted-at-rest
  guarantee at this scale; Key Vault + managed identity is the documented
  upgrade when >1 environment exists.
