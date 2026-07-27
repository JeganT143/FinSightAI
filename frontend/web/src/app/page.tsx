import { auth } from "@clerk/nextjs/server";
import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";
import { CLERK_ENABLED } from "@/lib/auth-config";
import { BILLING_ENABLED } from "@/lib/billing-config";

/**
 * The storefront (SAAS_DESIGN §2): signed-out visitors only. Signed-in users
 * — and every visitor when auth is disabled (dev mode) — go straight to the
 * console. The hero is real product proof: actual screenshots of the desk
 * mid-run and the published paper, not an illustration. (The looping
 * <HeroDemo> recreation from the design doc is a noted follow-up.)
 */
export default async function LandingPage() {
  if (!CLERK_ENABLED) redirect("/console");
  const { userId } = await auth();
  if (userId) redirect("/console");

  return (
    <div className="space-y-24 pb-12">
      {/* ---- Hero ---- */}
      <section className="pt-8 text-center sm:pt-16">
        <h1 className="mx-auto max-w-4xl text-5xl font-semibold leading-[1.05] tracking-tight text-text sm:text-7xl">
          Adversarial AI equity research.
        </h1>
        <p className="mx-auto mt-5 max-w-3xl text-2xl leading-snug text-text sm:text-3xl">
          Grounded in filings. <span className="text-brand">Reviewed before you see it.</span>
        </p>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-text-muted">
          Four AI analysts research a stock in parallel. A critic attacks every claim
          before it&apos;s published.
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
          <Link
            href="/sign-up"
            className="rounded-lg bg-brand px-6 py-3 font-mono text-sm font-medium uppercase tracking-widest text-white transition-colors hover:bg-brand-strong"
          >
            Start researching free →
          </Link>
          {BILLING_ENABLED && (
            <Link
              href="/pricing"
              className="rounded-lg border border-border bg-surface px-6 py-3 font-mono text-sm uppercase tracking-widest text-text transition-colors hover:border-brand"
            >
              See pricing
            </Link>
          )}
        </div>

        {/* The proof: the desk mid-run and the paper on completion. */}
        <div className="mt-14 grid gap-6 lg:grid-cols-2">
          <figure className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
            <Image
              src="/hero-run.png"
              alt="FinSightAI console mid-run: four specialist agents working in parallel with live cost and latency"
              width={1280}
              height={800}
              priority
              className="w-full"
            />
            <figcaption className="border-t border-border px-4 py-2.5 text-left font-mono text-[13px] uppercase tracking-widest text-text-muted">
              The desk — four specialists, live
            </figcaption>
          </figure>
          <figure className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
            <Image
              src="/hero-report.png"
              alt="A published FinSightAI research report with verdict, pillar scores, and filing citations"
              width={1280}
              height={800}
              priority
              className="w-full"
            />
            <figcaption className="border-t border-border px-4 py-2.5 text-left font-mono text-[13px] uppercase tracking-widest text-text-muted">
              The paper — critic-cleared, citation-grounded
            </figcaption>
          </figure>
        </div>
      </section>

      {/* ---- How it works ---- */}
      <section aria-labelledby="how-heading">
        <h2
          id="how-heading"
          className="font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted"
        >
          How it works
        </h2>
        <ol className="mt-6 grid gap-6 sm:grid-cols-3">
          {[
            {
              n: "1",
              title: "Four specialists research in parallel",
              body: "Fundamentals, technicals, risk, sentiment — each grounded in real market data and the company's own SEC filings, with citations.",
            },
            {
              n: "2",
              title: "A synthesizer drafts one report",
              body: "Typed, structured output from all four specialists becomes a single thesis with a verdict — the overall score is computed in code, not by an LLM.",
            },
            {
              n: "3",
              title: "An adversarial critic attacks it",
              body: "Every number is checked against the source data before publication — and the draft goes back for revision if it can't defend itself.",
            },
          ].map((step) => (
            <li key={step.n} className="rounded-xl border border-border bg-surface p-6">
              <span className="font-mono text-2xl text-brand">{step.n}</span>
              <h3 className="mt-3 text-lg font-semibold text-text">{step.title}</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-text-muted">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ---- Why it's different ---- */}
      <section aria-labelledby="why-heading">
        <h2
          id="why-heading"
          className="font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted"
        >
          Why it&apos;s different
        </h2>
        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          {[
            {
              title: "Grounded, not guessed",
              body: "Every claim traces to a 10-K/10-Q passage or a market data point, cited inline. Missing data is disclosed, never filled from memory.",
            },
            {
              title: "Reviewed, not trusted blindly",
              body: "A critic checks every number against the source before you see it — and shows its work. Unresolved challenges are published, not hidden.",
            },
            {
              title: "Priced like infrastructure",
              body: "See exactly what each report costs — tokens, latency, model, per agent. Transparency is the feature, not a settings page.",
            },
            {
              title: "Built in the open",
              body: "The full architecture, design system, and eval methodology are documented decisions, not a black box.",
            },
          ].map((f) => (
            <div key={f.title} className="rounded-xl border border-border bg-surface p-6">
              <h3 className="text-lg font-semibold text-text">{f.title}</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-text-muted">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---- CTA band ---- */}
      <section className="rounded-xl bg-brand px-8 py-12 text-center">
        <p className="text-2xl font-semibold text-white">
          Research your first stock free. No card required.
        </p>
        <Link
          href="/sign-up"
          className="mt-6 inline-block rounded-lg bg-white px-6 py-3 font-mono text-sm font-medium uppercase tracking-widest text-brand-strong transition-opacity hover:opacity-90"
        >
          Get started →
        </Link>
      </section>
    </div>
  );
}
