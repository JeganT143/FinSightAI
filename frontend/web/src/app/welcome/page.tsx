"use client";

/**
 * Onboarding (SAAS_DESIGN §5): one screen, not a wizard. The product's value
 * is demonstrated by running it once — submitting routes into /console with
 * the run already starting. Reuses the exact TickerForm component.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { TickerForm } from "@/components/TickerForm";

const SUGGESTIONS = ["NVDA", "AAPL", "MSFT"];

export default function WelcomePage() {
  const router = useRouter();
  const startRun = (ticker: string) => router.push(`/console?ticker=${ticker}`);

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center pt-16 text-center">
      <h1 className="text-4xl font-semibold tracking-tight text-text">Welcome to FinSightAI.</h1>
      <p className="mt-3 text-2xl text-text-muted">Let&apos;s research your first stock.</p>

      <div className="mt-10 w-full">
        <TickerForm onSubmit={startRun} disabled={false} />
      </div>

      <p className="mt-5 font-mono text-sm uppercase tracking-widest text-text-muted">
        or try:{" "}
        {SUGGESTIONS.map((t, i) => (
          <span key={t}>
            <button onClick={() => startRun(t)} className="text-brand underline hover:text-brand-strong">
              {t}
            </button>
            {i < SUGGESTIONS.length - 1 && " · "}
          </span>
        ))}
      </p>

      <Link href="/console" className="mt-12 text-[15px] text-text-muted underline hover:text-text">
        Skip for now →
      </Link>
    </div>
  );
}
