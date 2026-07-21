"use client";

/**
 * Billing (SAAS_DESIGN §7): plan + usage meter + Stripe portal handoff.
 * The meter reuses the product's three-tone system inverted for remaining
 * budget: <70% used = bull, 70-90% = hold, >90% = bear + upgrade CTA.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuthToken } from "@/components/AuthTokenBridge";
import { authHeaders, PUBLIC_API_URL } from "@/lib/api";

interface Usage {
  plan: string;
  runs_used: number;
  runs_limit: number;
  period_end: string;
}

function meterTone(fraction: number): { bar: string; label: string } {
  if (fraction >= 0.9) return { bar: "bg-bear", label: "text-bear" };
  if (fraction >= 0.7) return { bar: "bg-hold", label: "text-hold" };
  return { bar: "bg-bull", label: "text-bull" };
}

export default function BillingPage() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [redirecting, setRedirecting] = useState(false);
  const getToken = useAuthToken();

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        const res = await fetch(`${PUBLIC_API_URL}/api/account/usage`, {
          headers: authHeaders(token),
        });
        if (!res.ok) throw new Error(`Failed to load usage (${res.status})`);
        setUsage(await res.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load usage.");
      }
    })();
  }, [getToken]);

  async function openPortal() {
    setRedirecting(true);
    try {
      const token = await getToken();
      const res = await fetch(`${PUBLIC_API_URL}/api/billing/portal`, {
        method: "POST",
        headers: authHeaders(token),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? "Could not open the billing portal.");
      }
      const { url } = await res.json();
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open the billing portal.");
      setRedirecting(false);
    }
  }

  const fraction = usage ? usage.runs_used / Math.max(usage.runs_limit, 1) : 0;
  const tone = meterTone(fraction);

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <h1 className="text-3xl font-semibold tracking-tight text-text">Billing</h1>

      {error && (
        <p role="alert" className="rounded-lg border border-bear/50 bg-bear/10 px-5 py-3 text-[15px] text-text">
          {error}
        </p>
      )}

      <section className="rounded-xl border border-border bg-surface p-7">
        <div className="flex items-center justify-between">
          <h2 className="font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted">
            Current plan
          </h2>
          <span className="rounded-full border border-brand px-3 py-0.5 font-mono text-sm font-medium uppercase tracking-widest text-brand">
            {usage?.plan ?? "…"}
          </span>
        </div>

        <div className="mt-7">
          <h3 className="font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted">
            Usage this period
          </h3>
          <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-bg">
            <div
              className={`h-full rounded-full ${tone.bar} transition-all`}
              style={{ width: `${Math.min(fraction * 100, 100)}%` }}
            />
          </div>
          <p className="mt-2.5 text-[15px] text-text">
            <span className={`font-mono font-medium ${tone.label}`}>
              {usage ? `${usage.runs_used} / ${usage.runs_limit}` : "… / …"}
            </span>{" "}
            research runs used
            {usage && (
              <span className="text-text-muted">
                {" "}
                · resets {new Date(usage.period_end).toLocaleDateString()}
              </span>
            )}
          </p>
          {fraction >= 0.9 && (
            <p className="mt-2 text-[15px]">
              <Link href="/pricing" className="text-brand underline hover:text-brand-strong">
                Nearly out — upgrade for a higher limit →
              </Link>
            </p>
          )}
        </div>

        <div className="mt-8 border-t border-border pt-6">
          <button
            onClick={openPortal}
            disabled={redirecting}
            className="rounded-lg border border-border bg-bg px-5 py-2.5 font-mono text-sm uppercase tracking-widest text-text transition-colors hover:border-brand disabled:opacity-60"
          >
            {redirecting ? "Opening…" : "Manage billing (Stripe) →"}
          </button>
          <p className="mt-2.5 text-sm text-text-muted">
            Payment methods, invoices, and cancellation are handled in Stripe&apos;s own portal —
            card details never touch FinSightAI.
          </p>
        </div>
      </section>
    </div>
  );
}
