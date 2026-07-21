# Setup Guide — Running FinSightAI Locally, Step by Step

This is the practical "get it running on your machine" guide. Different job
from the other docs: [README.md](README.md) is the pitch, [HOW_TO.md](HOW_TO.md)
is how the code was built, [DEPLOYMENT.md](DEPLOYMENT.md) is putting it on
Azure. This one is copy-paste commands, in order, to go from a fresh clone to
a working app — first in 5-minute dev mode, then with real accounts wired up.

## What you need before starting

- **Docker + Docker Compose** — everything runs in containers; nothing else
  is required for Path A.
- **An OpenAI API key** — the one thing that's never optional. Get one at
  [platform.openai.com/api-keys](https://platform.openai.com/api-keys). A
  typical research run costs **~$0.02**; budget a few dollars for testing.
- Optional, only for Path B: a free [Clerk](https://clerk.com) account (auth)
  and a free [Stripe](https://stripe.com) account in **test mode** (billing).

---

## Path A — Dev mode in 5 minutes (no Clerk, no Stripe)

This is the fastest way to see the app working. Auth is disabled (you're a
single built-in "dev" user with the Pro plan), billing routes 503 until
configured, and job execution runs inline in the request — no Redis needed.
This is also exactly how CI and the test suite run: zero vendor accounts.

```bash
git clone https://github.com/JeganT143/FinSightAI.git
cd FinSightAI
cp .env.example .env
```

Open `.env` and set the one required line:

```bash
OPENAI_API_KEY=sk-...your real key...
```

Leave everything else commented out. Then:

```bash
docker compose --profile full up --build
```

First build takes a few minutes (Python + Node dependencies, image layers).
When it settles, you'll see all containers report healthy. Open:

- **http://localhost:3000** → redirects straight to `/console` (no landing
  page yet — that's a signed-out-only surface, and auth is off)
- **http://localhost:8000/docs** → the API's interactive OpenAPI docs
- **http://localhost:8000/health/ready** → should return
  `{"status":"ready","database":"up"}`

Type a ticker (try `NVDA`) into the console and watch the four specialists
run in parallel, the synthesizer draft a report, and the critic review it —
live, streamed. That's the whole product, running with one API key.

To stop: `Ctrl+C`, then `docker compose --profile full down`. (See
[Troubleshooting](#troubleshooting) if `down` hangs with a permission error —
that's a known issue with this machine's Docker, not the app.)

---

## Path B — Full setup: real accounts, real login, real billing

Do this once you want the actual product experience: a landing page, sign-up
with your own account, per-user history, plan limits, and Stripe checkout.
Everything below is additive to Path A — nothing here changes what already
worked.

### Step 1 — Clerk (authentication)

1. Go to [clerk.com](https://clerk.com) → **Create application**. Any name.
   Enable at least "Email" as a sign-in method (add Google/GitHub OAuth too
   if you want — no code changes needed, it's a Clerk dashboard toggle).
2. In the dashboard, open **API Keys**. Copy three values:
   - **Publishable key** (`pk_test_...`)
   - **Secret key** (`sk_test_...`)
   - The **Frontend API URL**, shown as something like
     `https://your-app-name-12.clerk.accounts.dev` — this is your issuer URL.

### Step 2 — Stripe (billing, test mode)

Skip this step if you don't care about the billing pages yet — the rest of
the app works fine without it; `/pricing`'s upgrade button will just 503
until you add these.

1. Go to [dashboard.stripe.com](https://dashboard.stripe.com) and make sure
   the toggle in the top-right says **Test mode**.
2. **Products** → **Add product** → name it "FinSightAI Pro", set a
   recurring price (e.g. $19.00/month). Save, then copy the **Price ID**
   (`price_...`) from the pricing section of the product page.
3. **Developers → API keys** → copy the **Secret key** (`sk_test_...`).
4. The webhook signing secret comes later (Step 5) — Stripe needs to know
   your app's URL first, and for local dev that means the Stripe CLI.

### Step 3 — Fill in `.env`

Open `.env` (from Path A) and uncomment/fill these blocks:

```bash
# --- Phase 2: authentication ---
AUTH_MODE=clerk
CLERK_ISSUER=https://your-app-name-12.clerk.accounts.dev
CLERK_AUTHORIZED_PARTIES=["http://localhost:3000"]

# --- Phase 2: billing (Stripe TEST-mode keys) ---
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...          # fill after Step 5
STRIPE_PRICE_PRO=price_...

# --- Phase 2: async execution ---
QUEUE_ENABLED=true                        # already the compose default
```

Then add the frontend value — this is **not** read from `.env` at
runtime, it gets baked into the browser bundle at build time, so it's
passed as Docker build args (already wired in `docker-compose.yml`) that
read from your shell environment:

```bash
export NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
```

Either `export` it in your shell before building, or add it to `.env` and
`source .env` first — either way, it must be set in the environment `docker
compose build` runs in, not just inside the containers.

### Step 4 — Build and launch

```bash
docker compose --profile full build
docker compose --profile full up -d
docker compose --profile full ps          # all should say "healthy"
```

Now **http://localhost:3000** shows the real landing page. Click **Get
started**, accept the "research, not advice" consent checkbox, and sign up
with a real email (Clerk sends a verification code) or Google. You land on
`/welcome` — type a ticker and your first research run starts for real,
scoped to your new account.

### Step 5 — Wire up the Stripe webhook (local dev)

Stripe needs to call your app when a checkout completes. Locally, that means
the Stripe CLI forwards events to your machine:

```bash
# macOS: brew install stripe/stripe-cli/stripe
# Linux: see https://docs.stripe.com/stripe-cli#install
stripe login
stripe listen --forward-to localhost:8000/api/billing/webhook
```

This prints a webhook signing secret (`whsec_...`) — copy it into `.env` as
`STRIPE_WEBHOOK_SECRET`, then restart the backend so it picks it up:

```bash
docker compose --profile full up -d --build backend
```

Leave `stripe listen` running in its own terminal while you test checkout.
Go to `/pricing` → **Upgrade to Pro** → Stripe's hosted checkout → pay with
the test card `4242 4242 4242 4242`, any future expiry, any CVC. You'll be
redirected back, and `/account/billing` should show plan **PRO** within a
few seconds (the webhook flips it).

### Verify everything is actually wired up

| Check | Expected |
|---|---|
| `curl http://localhost:8000/health/ready` | `{"status":"ready","database":"up"}` |
| `curl http://localhost:8000/api/billing/plans` | JSON with `free` and `pro` plan limits |
| Visit `/` signed out | Landing page, not the console |
| Sign up, run a ticker | Report appears only in *your* `/reports`, not a stranger's |
| Ask the chat "should I buy NVDA?" | Fixed refusal (hold-toned), not an LLM-generated answer |
| Ask the chat "what is a PEG ratio?" | A real, generated explanation |
| Stripe test checkout | `/account/billing` shows plan flips to PRO after payment |
| `docker logs finsight-worker` | Shows `run started` / `run complete` lines when queued runs happen |

---

## Running without Docker (native dev loop)

Useful for backend iteration with hot reload. Requires
[uv](https://docs.astral.sh/uv/) and Node 22.

```bash
make setup      # uv sync + npm ci
make db         # just Postgres, via compose
make migrate    # alembic upgrade head
make api        # uvicorn --reload on :8000, separate terminal
make web        # next dev on :3000, separate terminal
```

`make check` runs everything CI runs (lint, typecheck, tests) before you
push. `make help` lists every target. This path defaults to
`AUTH_MODE=disabled` and `QUEUE_ENABLED=false` unless you export the Phase-2
variables yourself — Redis and the worker aren't started by `make db`.

---

## Troubleshooting

**`docker compose ... down` (or any `docker stop`) fails with "permission
denied"** — this is a known AppArmor issue on some snap-installed Docker
setups, unrelated to the app. Workaround:
```bash
docker update --restart=no <container-name>
docker exec <container-name> sh -c 'kill 1'
docker compose --profile full down
```
A `snap refresh docker` or a reboot usually clears it for good.

**Chat / console shows network errors in the browser, but `curl` against
the API works fine** — the frontend was probably built with a stale or
empty `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`. These are
baked into the JS bundle at **build** time, not read at container start —
changing `.env` alone does nothing until you rebuild:
```bash
docker compose --profile full build frontend
docker compose --profile full up -d frontend
```

**A research run fails with `MaxTurnsExceeded`** — rare; one specialist
occasionally loops on its filing-search tool past the default turn budget.
Just retry the ticker. `AGENT_MAX_TURNS` in `.env` raises the cap if you see
it often (default 16).

**Sign-up works but `/api/reports` returns 401** — the backend's
`CLERK_ISSUER` and the frontend's `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` must
be from the **same** Clerk application. Double check both came from the one
app you created in Step 1.

**Stripe webhook events never arrive** — `stripe listen` must stay running
in its own terminal for the whole session; it's not a one-time setup step.
Restarting your terminal means restarting `stripe listen` too (and the
forwarding secret stays the same as long as you don't re-run `stripe login`).

---

## What's next

- Ready to put this somewhere with a real URL instead of `localhost`? →
  [DEPLOYMENT.md](DEPLOYMENT.md) walks through Azure Container Apps,
  budgeted for a $100 student credit, at a custom domain.
- Curious why anything is built the way it is? → [ARCHITECTURE.md](ARCHITECTURE.md)
  (core engine) and [SAAS_ARCHITECTURE.md](SAAS_ARCHITECTURE.md) (Phase 2)
  have the full reasoning, including rejected alternatives.
