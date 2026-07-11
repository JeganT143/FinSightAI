# FinSightAI — UI/UX Design

> Written **before** the frontend was built; the implementation follows this document.
> Companion to [ARCHITECTURE.md](ARCHITECTURE.md) (ADR-10 explains the stack choice).

## 1. Product framing

**Who uses it.** Two audiences: (a) anyone researching a US stock who wants a grounded, criticized AI report rather than a chatbot's opinion; (b) technical reviewers evaluating this as an AI engineering project. Both need the same thing: to *see the system think* — not a spinner followed by a wall of text.

**The page's single job.** Watch a team of AI analysts research a ticker live — four specialists in parallel, a synthesizer, an adversarial critic — then read the verdict with full provenance: filing citations, critic challenges, per-agent cost and latency.

**Design thesis.** The product's story is *machine process → published artifact*. The UI encodes that story in its materials, and — as of Rev 3 — in **two independent axes**:

- **The desk vs. the paper** (surface/content axis, unchanged since Rev 1). "The desk" is the console chrome: nav, cards, the live tape, tables. This is where agents work. "The paper" is the report artifact: a bone-white sheet with serif type that appears only when research survives critique. This is what you keep. The desk *narrates*; the paper *publishes*.
- **Night desk vs. day desk** (light/dark axis, new in Rev 3). The desk's color scheme follows the user's preference — system by default, overridable with a toggle. The paper does **not** follow this toggle; it is always the same warm, printed-page color in both modes.

The surface you're looking at tells you which world you're in — desk or paper — regardless of light/dark. That transition, paper rising off the desk, is still the signature moment; Rev 3 makes it survive a theme switch instead of only existing in one.

## 2. Design system

> **Rev 3 (2026-07-11):** full color theme replacement, plus a real light theme
> (previously only the report paper was light — the desk chrome was always dark).
> See §2.1 for the reasoning and the alternative themes considered.
> **Rev 2 (2026-07-11):** after user feedback ("very hard to read, very small"), the
> type scale was raised across the board and the brand accent now comes from the
> provided logo. Readability beats terminal density — that is now a design rule.
> Both rules still apply; Rev 3 only replaces color tokens, not type or spacing.

### 2.0 Brand

The FinSightAI logo (an "F" inside a magnifying-glass lens with circuit traces —
`resources/logo.png`) appears in the top bar, inside a small neutral chip
(`surface` + `border`), and as the console hero mark, on a transparent
background (web assets are generated from the source PNG with the white matte
removed). The **chip exists specifically so the logo's dark navy "F" stays
legible on both the night desk and the day desk** — without it, the F would
sit directly on a background whose lightness flips between modes, and a mark
tuned for one would wash out on the other.

The lens-ring teal is sampled as the **brand accent** — buttons, links, focus
rings, brand text, the theme toggle's hover state. Brand teal is a UI accent
only, never a chart/status mark (see ADR-9-equivalent color rules below).

### 2.1 Color tokens — the desk/paper/theme system

**Why a full repaint, and why light mode.** The Rev 1/2 palette worked but had
one structural gap: only the report was ever light. Reviewers who prefer a
light UI (a large fraction of any audience) had no option, and the single dark
"ink" hue read as a fairly generic navy-black rather than something distinctly
*this* product's. Rev 3 fixes both: two real, independently validated desk
themes, built around the actual brand hue instead of a generic dark-mode navy.

**Alternatives considered and rejected** (documented per the project's ADR
habit — see ARCHITECTURE.md):
- *Pure grayscale/near-black + single accent* (the generic "AI product" dark
  theme) — rejected because it's the single most common default across AI
  tools right now; it would have made the desk look like every other chat UI
  instead of a specific, brand-derived space.
- *Invert the existing palette 1:1 for light mode* (same hues, swapped
  lightness) — rejected because a naive inversion produces muddy, low-chroma
  colors; each mode needed its own pass through the validator, not a formula.
- *Light mode = paper, everywhere* (desk and report share one color) —
  seriously considered, since it would have been "free" (paper was already
  validated). Rejected because it collapses the desk/paper distinction that is
  this product's actual visual thesis: if the chrome and the artifact are the
  same color, "the report rising off the desk" stops being a visible event in
  light mode. Keeping the desk on its own (cooler, grayer) neutral preserves
  that moment in *both* themes — paper is always a *slightly* different,
  warmer material than the surface it sits on.

**The system.** Two color axes, four token groups:

| Group | Governed by | Changes with theme toggle? |
|---|---|---|
| `bg` / `surface` / `surface-hover` / `border` / `text` / `text-muted` / `text-faint` | Desk theme (day/night) | **Yes** |
| `brand` / `brand-strong` / `brand-blue` | Desk theme (re-validated per mode) | Yes (different exact hex per mode, same hue family) |
| `bull` / `hold` / `bear` (status) | Desk theme (re-validated per mode) | Yes |
| `paper` / `paper-ink` / `paper-line` | Fixed — the artifact's own "material" | **No** |

**Night desk (dark):**

| Token | Hex | Role |
|---|---|---|
| `bg` | `#0B1615` | Page background — deep, desaturated teal-black, not blue-black |
| `surface` | `#12211F` | Raised cards, tape, tables |
| `surface-hover` | `#1A2E2B` | Hover state on interactive rows |
| `border` | `#24413C` | Dividers, card outlines |
| `text` | `#EAF3F0` | Primary text |
| `text-muted` | `#9FB8B2` | Secondary text |
| `text-faint` | `#6C8681` | Tertiary text, idle-state icons |
| `brand` | `#1AA189` | Primary action, links, focus ring |
| `brand-blue` | `#4A8FD6` | Secondary brand accent (from the logo's circuit blue) |
| `bull` / `hold` / `bear` | `#2FA97C` / `#B08F1E` / `#E05A63` | Status colors |

**Day desk (light):**

| Token | Hex | Role |
|---|---|---|
| `bg` | `#EDF1EE` | Page background — soft, cool-neutral gray-green |
| `surface` | `#FFFFFF` | Raised cards, tape, tables |
| `surface-hover` | `#E3E9E4` | Hover state |
| `border` | `#D3DBD5` | Dividers, card outlines |
| `text` | `#10201D` | Primary text |
| `text-muted` | `#47605A` | Secondary text |
| `text-faint` | `#7C948D` | Tertiary text |
| `brand` | `#0E9C82` | Primary action, links, focus ring |
| `brand-blue` | `#1D6FB8` | Secondary brand accent |
| `bull` / `hold` / `bear` | `#1E8A5F` / `#9C7A12` / `#C23A44` | Status colors |

Note the two desk `bg` values share a hue family (teal-green) at opposite ends
of the lightness range — "same material, different lighting," reinforcing
that this is one product with a day/night switch, not two unrelated skins.

**Paper (fixed, both themes) — the artifact's own material:**

| Token | Hex | Role |
|---|---|---|
| `paper` | `#F7F4EE` | Report sheet background |
| `paper-ink` | `#1C2530` | Text on paper |
| `paper-line` | `#E3DDD2` | Rules/dividers on paper |

`amber` (`#E8A33D`, unthemed) remains the working/live-state color, reserved
for in-progress agents — never a chart mark, never used decoratively.

Phase colors for the trace timeline (categorical, fixed order, re-validated
against the new night-desk surface): research `#C97F1D` · synthesis `#3E85C7`
· critique `#8464DD` · revision `#209B8E`.

**Every color above was machine-validated**, not eyeballed: OKLCH lightness
band, chroma floor, CVD ΔE separation (deuteranopia/protanopia), and contrast
— run per theme, against both `bg` and `surface`, using the same validator
script as Rev 1/2. The `hold` tone is intentionally the lowest-contrast status
color in both modes, which is exactly why verdicts and scores always pair
color with a text label — never color alone.

Score → color mapping is one function used everywhere (dials, chips, table
rows), unchanged by the theme rewrite: `≥6.5 bull · ≥4.5 hold · <4.5 bear`.

**Mechanics.** Raw CSS custom properties live in `:root` (light default),
overridden by `@media (prefers-color-scheme: dark)` (system fallback) and by
`:root[data-theme="light"|"dark"]` (explicit user choice — always wins in
either direction). A `beforeInteractive` script in the root layout reads
`localStorage` (falling back to system preference) and stamps `data-theme` on
`<html>` before first paint, so there's no flash of the wrong theme. Tailwind
utilities (`bg-bg`, `text-text-muted`, `border-border`, …) are generated from
those custom properties via `@theme inline`, so components never hardcode a
hex value or a light/dark branch — they just use the semantic class and the
active theme resolves it.

### 2.2 Typography

| Role | Face | Why |
|---|---|---|
| Report display & narrative | **Newsreader** (serif) | Editorial gravity of a printed research note; only ever on the paper surface |
| UI / labels / controls | **IBM Plex Sans** | Engineering-flavored neutral; disciplined at small sizes |
| Telemetry, tickers, numbers | **IBM Plex Mono** | The voice of the desk: tape events, costs, latencies, scores — always `tabular-nums` |

Rules: tickers are always mono, uppercase, letter-spaced (`NVDA`). Money and latency are always mono. Serif never appears on desk surfaces; mono never sets paragraphs on paper. All fonts self-hosted via `next/font` (no external requests, consistent with the self-contained deploy).

Scale (Rev 2 — readability first, unchanged by Rev 3): **16px base**, 13px floor for labels/telemetry
(nothing smaller than 12px anywhere), tape at 14px mono, working notes at 15px,
paper serif body 16–19px, display 36/48/60. Line-height 1.55 prose, 1.15 display.
Secondary text uses `text-muted`; de-emphasis is done with size and
weight, not by dimming below readable contrast — true in both themes.

### 2.3 Spacing, shape, depth

- 4px base grid; component padding 16/20; section rhythm 32/48.
- Radius: 6px on desk cards, 2px on paper (paper is a document, not a widget). No shadows on the desk — separation comes from surface steps (`surface` on `bg`) and 1px `border` outlines, in both themes. Paper gets one soft ambient shadow to lift it off the desk, more dramatic in dark mode (bright artifact on a dark floor) than light mode (cream on cool gray) — an intentional, theme-dependent difference, not a bug.
- The desk never scrolls horizontally; the tape and tables scroll inside their own containers.

### 2.4 Motion

Sparse and orchestrated; every animation respects `prefers-reduced-motion`.

1. **Running pulse** — an amber node dot breathes (opacity 0.5↔1, 1.6s) while an agent works. The only looping animation on the page.
2. **Tape writes** — new events slide in 8px + fade, 180ms. Feels like a ledger being written, not a chat.
3. **The publication moment** — on `complete`, the paper report rises into the console (translateY 24px→0 + fade, 480ms ease-out) while the pipeline section compresses. One deliberate, product-story moment; nothing else animates during it.
4. **Critic block** — the `REVISION REQUIRED` stamp scales 1.06→1 with a 2° settle, like a rubber stamp landing.

## 3. Information architecture

```
/                    Console — start research, watch the run live, read the result
/reports             Ledger — history of runs (table), filter by ticker
/reports/[id]        Dossier — full report + critic trail + agent traces + costs
```

Three screens, no dashboard-for-dashboard's-sake. The console is the product; the ledger and dossier are its memory.

## 4. Screen designs

### 4.1 Console `/` — idle state

```
┌────────────────────────────────────────────────────────────────┐
│  FINSIGHT AI                                  Console · Ledger │   top bar (ink)
├────────────────────────────────────────────────────────────────┤
│                                                                │
│        Research any US-listed stock with a team of             │   H1 (Plex Sans,
│        adversarial AI analysts.                                │   not serif — this
│                                                                │   is the machine
│        ┌──────────────────────────────┬───────────────┐        │   room speaking)
│        │  TICKER   e.g. NVDA          │  Run research │        │   order-entry bar
│        └──────────────────────────────┴───────────────┘        │
│         4 specialists · adversarial critic · SEC-grounded      │   quiet caption
│                                                                │
│  ── THE DESK ────────────────────────────────────────────────  │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐       │   agent roster:
│  │FUNDAMENTALS│ │TECHNICALS │ │  RISK     │ │ SENTIMENT │      │   idle nodes with
│  │ ○ idle    │ │ ○ idle    │ │ ○ idle    │ │ ○ idle    │       │   role captions
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘       │
│        └─────────────┴──────┬──────┴─────────────┘              │   confluence lines
│                      ┌──────┴──────┐    ┌────────────┐         │   (SVG)
│                      │ SYNTHESIZER │───▶│   CRITIC   │         │
│                      └─────────────┘ ◀──└────────────┘         │   loop-back arrow
│                            revision loop (max 2)                │
└────────────────────────────────────────────────────────────────┘
```

The idle desk shows the *architecture itself* as the hero — the reviewer sees the multi-agent design before running anything. The order-entry bar is the only call to action.

### 4.2 Console `/` — live run

```
┌────────────────────────────────────────────────────────────────┐
│  NVDA — research in progress            $0.0121 · 00:23 · ▍▍▍░ │   run status strip
├──────────────────────────────────────────┬─────────────────────┤
│  THE DESK (nodes now stateful)           │  THE TAPE           │
│  ┌───────────┐ ┌───────────┐             │  14:02:01 grounding │
│  │FUNDAMENTALS│ │TECHNICALS │  ...       │  10-K 02-25 · 54    │
│  │ ● 8.5     │ │ ◍ working │             │  chunks embedded    │
│  └───────────┘ └───────────┘             │  14:02:04 desk      │
│                                          │  4 analysts working │
│  ┌─ WORKING NOTES ──────────────────┐    │  14:02:14 technicals│
│  │ ▸ FUNDAMENTALS  8.5  high conf   │    │  scored 8.0 · $0.00 │
│  │   • Revenue growth 85.2% …       │    │  14:02:18 sentiment │
│  │   • [10-K Item 7] "gross margin  │    │  scored 9.0 · $0.00 │
│  │     71.1%…"                      │    │  …                  │
│  │ ▸ TECHNICALS — working…          │    │                     │
│  └──────────────────────────────────┘    │  (mono, aria-live)  │
└──────────────────────────────────────────┴─────────────────────┘
```

- Node states: `○ idle` → `◍ working` (amber pulse) → `● done` (score chip in score color) → `✕ failed`.
- Working notes accumulate one collapsible card per completed specialist: score, confidence, bullets, citations (citations rendered as filing tags: `10-K · Item 1A`).
- The tape is the audit trail: timestamped mono lines, one per SSE event, with cost/latency chips. It is `aria-live="polite"` — screen readers hear the run.
- Critic verdict: an inset card on the tape. If it blocks → `bear` border + stamp + challenge list; the synthesizer node re-enters working state and the loop-back arrow illuminates.

### 4.3 Console `/` — published

The desk collapses to a one-line summary strip. The paper rises:

```
┌────────────────────────────────────────────────────────────────┐
│ run summary: 6 agents · 1 revision · $0.0204 · 38.0s   [Ledger]│   ink strip
├────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────────┐ │
│ │                    (paper surface)                         │ │
│ │   INVESTMENT REPORT                          ┌─────────┐   │ │  serif display;
│ │   NVDA · 2026-07-11                          │   7.9   │   │ │  score dial (SVG)
│ │                                              │  ● BUY  │   │ │  verdict chip
│ │   Thesis                                     └─────────┘   │ │
│ │   NVIDIA exhibits exceptional growth …                     │ │
│ │                                                            │ │
│ │   Pillars    FUND 9.0 ─ TECH 8.0 ─ RISK 6.0 ─ SENT 9.0     │ │  pillar bars
│ │   Key risks  · Debt/equity 6.56 …                          │ │
│ │   Catalysts  · …                                           │ │
│ │   Sources    [10-K 2026-02-25 · Item 1A] [Item 7] …        │ │  citation tags
│ │                                                            │ │
│ │   ⊘ CRITIC: cleared for publication · 0 challenges         │ │  review note
│ └────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 4.4 Ledger `/reports`

A mono table on the desk — deliberately ledger-like, dense, sortable by recency only (no faux-BI controls). Columns: ticker · verdict chip · score · revisions (⟳ n when > 0) · cost · duration · when. Row click → dossier. Ticker filter is a small mono input, not a filter bar. Empty state: "No research yet. Run your first ticker from the Console." with a link.

### 4.5 Dossier `/reports/[id]`

Top: the paper report (same component as console-published — one source of truth).
Below, back on the desk, three panels:

1. **Critique trail** — every challenge (claim / reason / severity chip / pillar), blocks-publication verdict, revision count. Failed challenges are the *product working correctly* — they're displayed with pride, not hidden.
2. **Agent traces** — horizontal latency bars per agent run (research bars overlap in time — visually proving the parallel fan-out), each labeled with model, tokens in/out, cost. This is ADR-8 made visible.
3. **Run economics** — total cost, tokens, wall time; per-phase split.

Failed runs: dossier shows the error, whatever agent traces exist, and a "Run again" affordance.

## 5. Streaming UX — state machine

SSE event → UI transition (single reducer; every state renderable in isolation):

| Event | Transition |
|---|---|
| `start` | Console → running; status strip mounts; timer starts |
| `phase(grounding)` | Tape line; desk header shows "reading the 10-K…" |
| `grounding` | Tape line with form/date/chunks (or degraded-grounding note) |
| `agent_started` | Node → working (pulse) |
| `agent_completed` | Node → done + score chip; working-notes card expands; tape line with usage |
| `critic_verdict` | Critic card on tape; if blocks → stamp + loop-back arrow lights, synthesizer node re-arms |
| `phase(revision)` | Tape line "Revising — round n" |
| `complete` | The publication moment (§2.4); summary strip |
| `error` | Desk freezes; `bear` banner: "The run failed: {reason}. Finished work is saved in the Ledger." |

Disconnect mid-run: banner "Connection lost — the run continues on the server. Check the Ledger in a minute." (The backend finishes and persists regardless; ADR: Failure Modes.)

## 6. Component inventory

| Component | Notes |
|---|---|
| `TickerForm` | Uppercases as you type; validates A–Z, 1–5 chars; disabled while running |
| `Desk` / `AgentNode` | SVG confluence lines; node state machine above |
| `Tape` / `TapeLine` | Mono, timestamped, aria-live, capped buffer (last 200 events) |
| `SpecialistCard` | Score, confidence, bullets, data-warnings, citation tags |
| `CriticCard` + `Stamp` | Verdict, challenges, severities |
| `ScoreDial` | SVG arc, mono numeral, score color |
| `VerdictChip` | Text + color (never color alone) |
| `PillarBars` | Four horizontal bars, shared scale 0–10 |
| `ReportPaper` | The paper artifact; used on console + dossier |
| `TraceTimeline` | Per-agent latency bars on a shared time axis |
| `LedgerTable` | Dense mono table; verdict chips; relative timestamps |
| `RunStatusStrip` | Live cost accumulator, elapsed timer, phase dots |
| `ThemeToggle` | Sun/moon icon button; persists to `localStorage`; system-preference fallback (Rev 3) |

## 7. Quality floor

- **Responsive**: console collapses to single column < 900px (desk on top, tape below); paper is readable at 360px; tables scroll horizontally inside their container.
- **Keyboard**: every interactive element focusable; brand focus ring on the desk, `paper-ink` ring on paper; `/` focuses the ticker input.
- **Screen readers**: tape is the accessible narration of the run (`aria-live="polite"`); nodes carry `aria-label` state text; the stamp has a text equivalent.
- **Reduced motion**: pulse becomes a static amber dot; publication moment becomes a plain fade.
- **Color independence**: verdicts and severities always pair color with text.
- **No horizontal page scroll, ever.**
- **Theme correctness (Rev 3)**: every desk color is a semantic token (`bg`/`surface`/`border`/`text`/…), never a hardcoded hex — so nothing can silently break in one theme while looking fine in the other. Both themes were screenshotted and diffed manually for every screen before shipping (see HOW_TO.md Phase 14).

## 8. Deliberate omissions

- No *separate* light/dark **component sets** — one component tree, driven entirely by CSS custom properties, so the two themes cannot drift apart from each other over time (a hand-maintained parallel "LightDesk"/"DarkDesk" split was considered and rejected for exactly that maintenance-debt reason).
- No price charts — this is a research console, not a trading terminal; the only "chart" is the trace timeline, which visualizes *the system*, not the market.
- No component library — hand-rolled on Tailwind tokens (ADR-10): the look shouldn't be attributable to a kit.
- No user-configurable accent color — the brand teal/blue pair is fixed and validated per theme; exposing it as a setting would reopen the whole color-validation problem per combination for no real user benefit at this scale.
