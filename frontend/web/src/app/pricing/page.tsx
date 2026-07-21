"use client";

/**
 * Pricing (SAAS_DESIGN §3). Plan numbers come from GET /api/billing/plans —
 * this page and the backend's PLAN_LIMITS must never disagree, so nothing
 * here is hardcoded except copy. Flat and calm on purpose: no fake urgency,
 * no crossed-out prices — the one emphasis is the Pro card's border.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuthToken } from "@/components/AuthTokenBridge";
import { authHeaders, PUBLIC_API_URL } from "@/lib/api";
import { CLERK_ENABLED } from "@/lib/auth-config";

interface PlanInfo {
  max_runs_per_period: number;
  specialist_model: string;
  synthesizer_model: string;
  critic_model: string;
}

const FAQ: [string, string][] = [
  [
    "What counts as a research run?",
    "One full pipeline execution for one ticker: four specialists, synthesis, adversarial critique, and any revision rounds. Re-reading finished reports and chat questions about them are free.",
  ],
  [
    "What happens if I hit my limit mid-month?",
    "Research runs pause until your period resets (the date is shown on your billing page) or you upgrade. Nothing is deleted — reports, chat, and history keep working.",
  ],
  [
    "Can I cancel anytime?",
    "Yes — billing is handled by Stripe's own portal, cancellation takes effect at the end of the paid period, and your reports remain readable on the free tier.",
  ],
];

export default function PricingPage() {
  const [plans, setPlans] = useState<Record<string, PlanInfo> | null>(null);
  const [upgrading, setUpgrading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const getToken = useAuthToken();

  useEffect(() => {
    fetch(`${PUBLIC_API_URL}/api/billing/plans`)
      .then((r) => r.json())
      .then((data) => setPlans(data.plans))
      .catch(() => setError("Could not load plan data from the backend."));
  }, []);

  async function upgrade() {
    setUpgrading(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await fetch(`${PUBLIC_API_URL}/api/billing/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders(token) },
        body: JSON.stringify({}),
      });
      if (res.status === 401) {
        window.location.href = "/sign-up";
        return;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Checkout failed (${res.status})`);
      }
      const { url } = await res.json();
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkout failed.");
      setUpgrading(false);
    }
  }

  const free = plans?.free;
  const pro = plans?.pro;

  return (
    <div className="space-y-16 pb-8">
      <header className="pt-6 text-center">
        <h1 className="text-4xl font-semibold tracking-tight text-text sm:text-5xl">
          Simple, usage-aware pricing
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          Free to start. Upgrade when you need more research.
        </p>
      </header>

      {error && (
        <p role="alert" className="mx-auto max-w-lg rounded-lg border border-bear/50 bg-bear/10 px-5 py-3 text-center text-[15px] text-text">
          {error}
        </p>
      )}

      <div className="mx-auto grid max-w-4xl gap-6 sm:grid-cols-2">
        {/* FREE */}
        <div className="flex flex-col rounded-xl border border-border bg-surface p-7">
          <h2 className="font-mono text-sm uppercase tracking-[0.2em] text-text-muted">Free</h2>
          <p className="mt-3 text-4xl font-semibold text-text">
            $0<span className="text-lg font-normal text-text-muted">/mo</span>
          </p>
          <ul className="mt-6 flex-1 space-y-3 text-[15px] text-text">
            <li>{free ? `${free.max_runs_per_period} research runs / month` : "…"}</li>
            <li className="text-text-muted">{free ? `${free.synthesizer_model} everywhere` : "…"}</li>
            <li>30-day history</li>
            <li>Chat: questions &amp; explanations</li>
          </ul>
          <Link
            href={CLERK_ENABLED ? "/sign-up" : "/console"}
            className="mt-7 rounded-lg border border-border px-5 py-2.5 text-center font-mono text-sm uppercase tracking-widest text-text transition-colors hover:border-brand"
          >
            Get started
          </Link>
        </div>

        {/* PRO */}
        <div className="relative flex flex-col rounded-xl border-2 border-brand bg-surface p-7">
          <span className="absolute -top-3 right-6 rounded-full bg-brand px-3 py-0.5 font-mono text-[12px] font-medium uppercase tracking-widest text-white">
            Popular
          </span>
          <h2 className="font-mono text-sm uppercase tracking-[0.2em] text-text-muted">Pro</h2>
          <p className="mt-3 text-4xl font-semibold text-text">
            $19<span className="text-lg font-normal text-text-muted">/mo</span>
          </p>
          <ul className="mt-6 flex-1 space-y-3 text-[15px] text-text">
            <li>{pro ? `${pro.max_runs_per_period} research runs / month` : "…"}</li>
            <li className="text-text-muted">
              {pro ? `Full model routing (${pro.synthesizer_model} synthesis & critique)` : "…"}
            </li>
            <li>Unlimited history</li>
            <li>Chat: full — can trigger research</li>
          </ul>
          <button
            onClick={upgrade}
            disabled={upgrading}
            className="mt-7 rounded-lg bg-brand px-5 py-2.5 font-mono text-sm font-medium uppercase tracking-widest text-white transition-colors hover:bg-brand-strong disabled:opacity-60"
          >
            {upgrading ? "Redirecting…" : "Upgrade to Pro"}
          </button>
        </div>
      </div>

      <section aria-labelledby="faq-heading" className="mx-auto max-w-2xl">
        <h2 id="faq-heading" className="font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted">
          FAQ
        </h2>
        <div className="mt-4 divide-y divide-border rounded-xl border border-border bg-surface">
          {FAQ.map(([q, a]) => (
            <details key={q} className="group px-6 py-4">
              <summary className="cursor-pointer list-none text-[15px] font-medium text-text">
                {q} <span className="float-right text-text-muted group-open:rotate-90">›</span>
              </summary>
              <p className="mt-3 text-[15px] leading-relaxed text-text-muted">{a}</p>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
