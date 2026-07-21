# FinSightAI — Phase 2 UI/UX: Every Page in the SaaS Product

> Companion to [DESIGN.md](DESIGN.md) (the research console's design system —
> desk/paper duality, day/night theme, color and type tokens) and
> [SAAS_ARCHITECTURE.md](SAAS_ARCHITECTURE.md) (what each page talks to).
> **This document extends DESIGN.md's token system — it does not redefine
> it.** Every color, font, spacing value, and the day-desk/night-desk toggle
> named below is the exact one already built (`frontend/web/src/app/globals.css`,
> HOW_TO.md Phase 17). Where a page needs something DESIGN.md doesn't have
> yet, that's called out explicitly as a **new token/component**, not
> invented silently.
>
> Written before any Phase 2 frontend code, same discipline as DESIGN.md
> §1's rule for Phase 1: design first, build second.

## Routing change this document assumes

Today, `/` **is** the research console. Once auth (§3) exists:

| Route | Who sees it | What it is |
|---|---|---|
| `/` | Signed-out visitors | **New** — marketing landing page (§2) |
| `/` | Signed-in users | Redirects to `/console` |
| `/pricing` | Everyone | **New** — plan comparison (§3) |
| `/sign-in`, `/sign-up` | Signed-out | **New** — Clerk-hosted, themed (§4) |
| `/console` | Signed-in | The existing research console, moved from `/` — unchanged design, scoped to the signed-in user |
| `/chat` | Signed-in | **New** — the Concierge (§6) |
| `/reports`, `/reports/[id]` | Signed-in | Existing Ledger/Dossier, unchanged design, now user-scoped |
| `/account`, `/account/billing` | Signed-in | **New** — settings + billing (§7) |

Nothing about the Console/Ledger/Dossier's *design* changes — DESIGN.md §4.1–4.5
stand exactly as built. This document covers only what's new.

---

## 1. Design thesis for the new surfaces

DESIGN.md's thesis was **desk vs. paper** — the app has two materials, one
for working, one for the artifact you keep. Phase 2 adds a **third material**,
because it has a third job:

- **The desk** (existing) — where signed-in users work.
- **The paper** (existing) — the artifact they keep.
- **The storefront** (new) — where a stranger decides whether to become a
  user at all. Its job is persuasion in under ten seconds, not operation —
  so it's allowed to be more spacious, more typographically dramatic, and
  more willing to repeat its point than the desk ever is.

The storefront is **not a fourth visual language invented from nothing** —
it uses the exact desk/paper tokens (the brand teal, IBM Plex, Newsreader)
at a different scale and density, and its single most important asset is
**a real screenshot of the actual product**, not an illustration of one.
A research tool's best marketing material is proof it works, and this
product already has that proof (`docs/screenshots/`) — the landing page's
hero *is* the desk mid-run and the paper on completion, the two real,
already-built moments DESIGN.md calls "the signature moment," now doing
persuasion work instead of operation work.

**New token, one addition only:** a `--display-scale` context for the
storefront's headlines — DESIGN.md's largest existing size is the report
title (`text-6xl`, paper-only). The landing page hero headline goes one step
larger (`text-7xl`/`~72px`) since it's the one place in the whole product
whose entire job is to be read from across a room. Everything else — body
sizes, spacing scale, radius, motion — is reused exactly as DESIGN.md §2.2–2.4
already defined it.

---

## 2. Landing page (`/`, signed-out only)

```
┌────────────────────────────────────────────────────────────────┐
│  [logo] FinSightAI          Pricing   Sign in   [Get started →]│  nav, transparent
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   Adversarial AI equity research.                              │  hero, text-7xl,
│   Grounded in filings. Reviewed before you see it.              │  IBM Plex Sans
│                                                                │
│   Four AI analysts research a stock in parallel. A critic       │  subhead, text-xl,
│   attacks every claim before it's published.                    │  text-muted
│                                                                │
│   [ Start researching free → ]   [ See a sample report ]        │  primary + ghost CTA
│                                                                │
│   ┌──────────────────────────────────────────────────────┐     │
│   │        (looping hero visual — see below)              │     │  the proof
│   └──────────────────────────────────────────────────────┘     │
├────────────────────────────────────────────────────────────────┤
│  HOW IT WORKS                                                   │
│  ①  Four specialists research in parallel — fundamentals,        │  simplified Desk
│      technicals, risk, sentiment — each grounded in real          │  diagram, static,
│      filings via citation.                                        │  labeled ①②③
│  ②  A synthesizer drafts one report from all four.                │
│  ③  An adversarial critic attacks every number before             │
│      publication — and sends it back for revision if it can't     │
│      defend itself.                                                │
├────────────────────────────────────────────────────────────────┤
│  WHY IT'S DIFFERENT               (3-column feature grid)        │
│  Grounded, not guessed        Reviewed, not trusted blindly       │
│  Every claim traces to a       A critic checks every number       │
│  10-K/10-Q passage, cited.     against the source before you      │
│                                 see it — and shows its work.       │
│                                                                     │
│  Priced like infrastructure    Built in the open                  │
│  See exactly what each          Full architecture, design, and    │
│  report costs — tokens,         eval methodology documented,      │
│  latency, model, all of it.     not a black box.                  │
├────────────────────────────────────────────────────────────────┤
│  PRICING                                    [ See full pricing →]│  3 cards, teaser
├────────────────────────────────────────────────────────────────┤
│  Research your first stock free. No card required.                │  final CTA band,
│              [ Get started → ]                                    │  brand-teal bg
├────────────────────────────────────────────────────────────────┤
│  FinSightAI   Pricing  Terms  Privacy  GitHub        © 2026       │  footer
└────────────────────────────────────────────────────────────────┘
```

**The hero visual, precisely.** Not a static screenshot — a **looping,
autoplaying, silent** recreation of the desk→paper transition, built from
**recorded canned data** (one real, good-looking historical run, replayed —
never a live API call on every page view, which would mean every visitor
costs real OpenAI spend). Sequence: idle desk (2s) → nodes light up one by
one with their real scores appearing (4s) → critic card appears, clears (2s)
→ the paper rises (DESIGN.md's existing `animate-publish` keyframe, unchanged)
→ holds on the finished report (3s) → fades back to idle, loops. Respects
`prefers-reduced-motion` by freezing on the finished paper state instead of
looping — same rule DESIGN.md §2.4 already applies everywhere else.

**Why this and not a generic hero pattern.** The frontend-design discipline
this project already follows (DESIGN.md, Rev 1) warns against the generic
"big number + small label + gradient accent" AI-startup hero. This hero is
the opposite of generic specifically *because* it's real product footage,
not an illustration — a competitor's landing page can copy the *layout*,
not the *proof*.

**Components, reused vs. new:**
| Component | Source |
|---|---|
| Nav, footer | New, thin wrapper — same tokens as the app nav |
| Hero visual | New `<HeroDemo>` — reuses `Desk`, `Tape`, `ReportPaper` (all existing) fed canned data instead of `useResearchStream` |
| "How it works" diagram | New `<PipelineDiagram>` — a simplified, static, labeled SVG version of `Desk`'s confluence-line drawing |
| Feature grid, pricing teaser, CTA band | New, plain layout components — no novel visual system needed |

---

## 3. Pricing page (`/pricing`)

```
┌────────────────────────────────────────────────────────────────┐
│                         Simple, usage-aware pricing               │
│         Free to start. Upgrade when you need more research.       │
├───────────────────┬───────────────────┬──────────────────────────┤
│  FREE              │  PRO  [Popular]    │  TEAM                     │
│  $0/mo             │  $19/mo            │  Contact us               │
│  5 research runs    │  100 research runs  │  Pooled across seats     │
│  gpt-4o-mini only    │  Full model routing │  Full model routing      │
│  30-day history      │  Unlimited history  │  Unlimited history       │
│  Chat: Q&A only       │  Chat: full          │  Chat: full              │
│  —                    │  —                   │  API access              │
│  [Get started]        │  [Start free trial]  │  [Talk to us]            │
├───────────────────┴───────────────────┴──────────────────────────┤
│  FAQ                                                               │
│  What counts as a "research run"?  ›                              │
│  What happens if I hit my limit mid-month?  ›                     │
│  Can I cancel anytime?  ›                                          │
└────────────────────────────────────────────────────────────────┘
```

Three `PricingCard` components (new), data-driven from the exact
`SAAS_ARCHITECTURE.md §15` table — this page and the backend's
`PLAN_LIMITS` dict (`backend/billing/limits.py`) must never state different
numbers, so the frontend reads plan metadata from `GET /api/billing/plans`
(a small new endpoint mirroring `PLAN_LIMITS`) rather than hardcoding the
table twice. The Pro card gets a `border-brand` + "Popular" chip
(`VerdictChip`-style, reused component, bull-toned) — the only visual
emphasis on the page; everything else stays as flat and calm as the rest of
the product, deliberately not using aggressive SaaS-pricing-page tactics
(fake urgency, crossed-out prices) that would read as inconsistent with the
transparency-as-a-feature positioning from §2's "priced like infrastructure"
line.

---

## 4. Sign in / Sign up (`/sign-in`, `/sign-up`)

```
┌────────────────────────────────────────────────────────────────┐
│                    [logo]  FinSightAI                            │  centered, small
│                                                                    │
│              ┌──────────────────────────────┐                    │
│              │   Sign in to FinSightAI       │                    │  Clerk <SignIn/>,
│              │                                │                    │  themed via
│              │   [ Continue with Google ]     │                    │  appearance prop
│              │   ─────────  or  ─────────     │                    │
│              │   Email  [______________]      │                    │
│              │   Password [___________]       │                    │
│              │   [ Sign in ]                   │                    │
│              │                                │                    │
│              │   No account? Sign up           │                    │
│              └──────────────────────────────┘                    │
│                                                                    │
│         Research demo — not investment advice.                    │  same footer
└────────────────────────────────────────────────────────────────┘
```

Centered card on the plain desk background (`bg-bg`, respects the
day/night toggle exactly like every other page — auth is not exempt from
the theme system). Deliberately **not** a split-screen marketing layout
(logo + testimonial on one side, form on the other) — that pattern serves a
consumer app optimizing for delight; a finance-adjacent tool signing in a
user who's about to trust it with research decisions reads as more credible
minimal and fast, one job, no distractions. Clerk's `appearance` prop maps
directly onto existing tokens:

```ts
appearance={{
  variables: {
    colorPrimary: "var(--brand)",
    colorBackground: "var(--surface)",
    colorText: "var(--text)",
    borderRadius: "0.5rem",       // matches DESIGN.md's card radius
    fontFamily: "var(--font-sans)",
  },
}}
```

Sign-up is the identical layout with Clerk's `<SignUp/>` swapped in; no
separate visual design needed. **One addition specific to sign-up, not
sign-in:** a required, un-checked-by-default checkbox — "I understand
FinSightAI provides research information, not personalized investment
advice" — linking to the Terms — this is the one moment
`SAAS_ARCHITECTURE.md` §9's compliance posture asks for explicit consent,
not just a footer disclaimer.

---

## 5. Onboarding (first sign-in only, one screen, not a wizard)

```
┌────────────────────────────────────────────────────────────────┐
│                                                                    │
│              Welcome to FinSightAI.                               │  text-4xl
│         Let's research your first stock.                          │
│                                                                    │
│         ┌──────────────────────────────────┐                     │
│         │  TICKER    NVDA               [→]│                     │  the EXACT
│         └──────────────────────────────────┘                     │  TickerForm
│                                                                    │  component,
│         or try: NVDA · AAPL · MSFT                                │  reused verbatim
│                                                                    │
│                              [ Skip for now → /console ]           │
└────────────────────────────────────────────────────────────────┘
```

Deliberately **one screen, not a multi-step wizard** — this product's value
is demonstrated by running it once, not by explaining it in five slides
first. Reuses `TickerForm` (the exact existing component) directly; "try:"
chips are pre-fillable ticker suggestions (new, small `<TickerChip>`
buttons). Submitting routes straight into `/console` with the run already
started — onboarding *is* the first real research run, not a rehearsal for
one.

---

## 6. The Concierge (`/chat`) — new page, new UI pattern

This is the one page with no direct DESIGN.md precedent — a conversational
interface. It borrows the **desk's** visual register (this is working, not
reading) but introduces one new layout shape: sidebar + conversation.

```
┌───────────────┬────────────────────────────────────────────────┐
│  Conversations │  Ask about NVDA's risk profile           [i]   │  header + info
│  [+ New chat]  ├────────────────────────────────────────────────┤
│                │                                                │
│  ▸ NVDA risk    │                                    ┌─────────┐│
│    2h ago       │                                    │ What's  ││  user bubble,
│  ▸ Portfolio     │                                    │ NVDA's  ││  right-aligned,
│    check-in      │                                    │ risk?   ││  bg-brand/10
│    yesterday     │                                    └─────────┘│
│                │  ┌──────────────────────────────────┐          │
│                │  │ NVDA's risk pillar scored 6.0/10   │          │  assistant
│                │  │ (medium-high leverage, elevated     │          │  bubble,
│                │  │ beta). Full breakdown:               │          │  bg-surface
│                │  │ ┌────────────────────────────────┐  │          │
│                │  │ │ [mini report card: NVDA · 7.7 ] │  │          │  tool-result
│                │  │ │ [ Open full dossier → ]          │  │          │  card, links to
│                │  │ └────────────────────────────────┘  │          │  /reports/[id]
│                │  └──────────────────────────────────┘          │
│                │                                                │
│                ├────────────────────────────────────────────────┤
│                │  Ask a follow-up, or research a new ticker...   │  composer
│                │  [___________________________________] [Send]  │
│                ├────────────────────────────────────────────────┤
│                │  FinSightAI shares research, not personalized   │  disclaimer,
│                │  investment advice.                              │  ALWAYS visible
└───────────────┴────────────────────────────────────────────────┘
```

**Empty state** (new conversation, no messages yet): the composer is
centered vertically, with 3–4 suggested-prompt chips beneath it — "What's
NVDA's risk profile?", "Summarize my last report", "Research AMD" — each a
real, clickable example of the three non-refused intents from
`SAAS_ARCHITECTURE.md` §8 (research / follow-up / education), so the empty
state itself teaches the product's actual capability boundary without a
tutorial.

**When the Concierge triggers a full research run** (the `trigger_research`
tool, §8): the assistant bubble shows a **compact, non-interactive** version
of the existing `Desk` — same four node states (idle/working/done), same
amber pulse, rendered at roughly a third of the console's size, inline in
the chat — not a redirect away from the conversation. On completion, it
collapses into the "mini report card" shown above (ticker, score, verdict
chip, "Open full dossier" link to the real `/reports/[id]` page — no
information duplicated, just a doorway to it).

**When the classifier routes to the fixed refusal** (`advice_request`,
`SAAS_ARCHITECTURE.md` §8–9): the assistant bubble renders with a distinct,
quiet treatment — a `hold`-toned left border (not `bear` — this isn't an
error, it's a boundary) and the refusal text — never presented as a normal
generated response, so a user can visually tell "the product declined this
category of question" apart from "the product answered."

**New components this page needs:** `ConversationSidebar`, `MessageBubble`
(user/assistant/refusal variants), `ToolResultCard` (the mini report card),
`InlineDesk` (the compact `Desk` variant — same component, a `size="compact"`
prop, not a fork), `PromptChip`, `Composer`.

---

## 7. Account & Billing (`/account`, `/account/billing`)

```
┌────────────────────────────────────────────────────────────────┐
│  Account                                                          │
├──────────────┬─────────────────────────────────────────────────┤
│  Profile      │  Email        you@example.com                    │  left nav,
│  Billing      │  Password     Managed by your sign-in provider    │  same pattern
│  ──────────   │               [ Manage in Clerk → ]               │  as a settings
│                │                                                   │  panel — new,
│                │  Danger zone                                      │  but structurally
│                │  [ Delete account ]                                │  identical to
└──────────────┴─────────────────────────────────────────────────┘  the Dossier's
                                                                        Stat-tile grid
```

```
┌────────────────────────────────────────────────────────────────┐
│  Billing                                                           │
├──────────────┬─────────────────────────────────────────────────┤
│  Profile      │  Current plan:  PRO                    [BUY-toned│
│  Billing      │                                          chip]   │
│  ──────────   │                                                   │
│                │  Usage this period            [progress bar]     │  reuses the
│                │  42 / 100 research runs used                       │  ScoreDial /
│                │  Resets in 12 days                                  │  PillarBars
│                │                                                     │  visual language
│                │  [ Manage billing (Stripe) → ]                      │  (a bar, a
│                │                                                     │  number, a label)
└──────────────┴─────────────────────────────────────────────────┘
```

Both pages reuse the existing `Stat` tile component (from the Dossier's
"Run economics" section) for the usage numbers, and the existing progress-bar
visual language from `PillarBars` for the usage meter — a SaaS billing page
doesn't need a new data-viz idiom when the product already has a good one.
"Manage billing" and "Manage in Clerk" both hand off to the respective
vendor's hosted UI (`SAAS_ARCHITECTURE.md` §4/§3) rather than rebuilding
password-change or payment-method forms in-app.

**Usage meter color, specifically:** reuses the score-tone function
(`scoreTone`, DESIGN.md/`lib/score.ts`) inverted for "remaining budget"
framing — under 70% used renders `bull`, 70–90% renders `hold`, over 90%
renders `bear` with an inline upgrade CTA — the exact same three-tone
system as report scores, applied to a different number, not a new palette.

---

## 8. Error & edge states

- **404** (`app/not-found.tsx`, global) — same voice as the existing
  Dossier's not-found page (DESIGN.md's `ReportNotFound` component) —
  "Nothing here. [Back to Console →]" — no generic framework-default 404.
- **Quota exceeded** (a `402`-status API response, §6) — not a toast; a
  dedicated inline banner on the Console, `hold`-toned (a limit, not an
  error), with the exact remaining-quota number and an "Upgrade" button
  linking to `/pricing`.
- **Payment failed** (Stripe webhook → `status="past_due"`) — a persistent,
  dismissable-but-recurring banner across the app (`bear`-toned, this one
  *is* urgent) linking straight to the Stripe Customer Portal.

---

## 9. Component inventory addendum (new components only — DESIGN.md §6 still holds for existing ones)

| Component | Used on | Reuses |
|---|---|---|
| `HeroDemo` | Landing | `Desk`, `Tape`, `ReportPaper` (canned data) |
| `PipelineDiagram` | Landing | New static SVG, same line style as `Desk`'s confluence lines |
| `PricingCard` | Pricing | `VerdictChip`-style badge for "Popular" |
| `TickerChip` | Onboarding | New, trivial |
| `ConversationSidebar`, `MessageBubble`, `ToolResultCard`, `PromptChip`, `Composer` | Chat | New |
| `InlineDesk` | Chat | `Desk` with `size="compact"` |
| Settings panel (`SettingsNav` + content pane) | Account/Billing | Same two-column pattern as the Dossier |
| Usage meter | Billing | `PillarBars`' bar visual + `scoreTone` (inverted) |

## 10. Quality floor addendum

Everything in DESIGN.md §7 applies unchanged (responsive, keyboard, screen
readers, reduced motion, color independence, no horizontal scroll). Two
additions specific to Phase 2's new surfaces:

- **The hero demo (§2) must not autoplay audio** (it has none by design) and
  must pause entirely under `prefers-reduced-motion`, holding on the
  finished-paper frame rather than looping — the landing page is a visitor's
  first impression; a motion-sensitive visitor should not be forced to
  scroll past a spinning animation to reach the CTA.
- **The advice-refusal bubble (§6) must be distinguishable without color** —
  it carries the words "I can't give personalized advice" in its own text,
  not just a border color, so the boundary is legible in any theme, to any
  screen reader, and in any screenshot.
