"use client";

import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";
import { CriticCard } from "@/components/CriticCard";
import { Desk } from "@/components/Desk";
import { ReportPaper } from "@/components/ReportPaper";
import { RunStatusStrip } from "@/components/RunStatusStrip";
import { SpecialistCard } from "@/components/SpecialistCard";
import { Tape } from "@/components/Tape";
import { TickerForm } from "@/components/TickerForm";
import { BILLING_ENABLED } from "@/lib/billing-config";
import type { AgentKey } from "@/lib/events";
import { formatDuration, formatMoney, formatTokens } from "@/lib/score";
import { useResearchStream } from "@/lib/useResearchStream";

const SPECIALIST_KEYS: AgentKey[] = ["fundamentals", "technicals", "risk", "sentiment"];

export default function ConsolePage() {
  return (
    <Suspense>
      <Console />
    </Suspense>
  );
}

function Console() {
  const { state: run, start, reset } = useResearchStream();
  const running = run.status === "running";
  const published = run.status === "complete" && run.report;

  // Onboarding handoff (SAAS_DESIGN §5): /console?ticker=NVDA starts the run
  // immediately — the first research run IS the onboarding.
  const searchParams = useSearchParams();
  const autoStarted = useRef(false);
  useEffect(() => {
    const ticker = searchParams.get("ticker");
    if (ticker && !autoStarted.current) {
      autoStarted.current = true;
      start(ticker.toUpperCase());
    }
  }, [searchParams, start]);

  return (
    <div className="space-y-8">
      {/* ---- Order entry ---- */}
      {!published && (
        <section className="flex items-start gap-8 pt-2">
          <div className="min-w-0 flex-1 space-y-5">
            <h1 className="max-w-2xl text-[28px] font-semibold leading-snug tracking-tight text-text sm:text-4xl">
              Research any US-listed stock with a team of adversarial AI analysts.
            </h1>
            <TickerForm onSubmit={start} disabled={running} />
            <p className="text-[15px] text-text-muted">
              4 specialists in parallel · SEC-filing grounded · critic-reviewed before
              publication · press <kbd className="rounded border border-border bg-surface px-1.5 font-mono text-[13px]">/</kbd> to type
            </p>
          </div>
          <Image
            src="/logo.png"
            alt=""
            width={148}
            height={148}
            priority
            className="hidden shrink-0 opacity-90 lg:block"
          />
        </section>
      )}

      {/* ---- Status / error banners ---- */}
      {running && <RunStatusStrip run={run} />}

      {run.status === "error" && (
        <div role="alert" className="rounded-lg border border-bear/50 bg-bear/10 px-5 py-4">
          <p className="text-[15px] text-text">The run failed: {run.error}</p>
          <p className="mt-1.5 text-[15px] text-text-muted">
            Finished work is saved in the{" "}
            <Link href="/reports" className="underline hover:text-text">
              Ledger
            </Link>
            . You can start another run above.
          </p>
        </div>
      )}

      {run.status === "quota_exceeded" && (
        <div role="status" className="rounded-lg border border-hold/50 bg-hold/10 px-5 py-4">
          <p className="text-[15px] text-text">{run.error}</p>
          <p className="mt-1.5 text-[15px] text-text-muted">
            This is a plan limit, not an error.{" "}
            {BILLING_ENABLED ? (
              <Link href="/pricing" className="underline hover:text-text">
                Upgrade for a higher monthly limit →
              </Link>
            ) : (
              "Your limit resets next period."
            )}
          </p>
        </div>
      )}

      {run.status === "disconnected" && (
        <div role="alert" className="rounded-lg border border-hold/50 bg-hold/10 px-5 py-4">
          <p className="text-[15px] text-text">
            Connection lost — the run continues on the server.
          </p>
          <p className="mt-1.5 text-[15px] text-text-muted">
            Check the{" "}
            <Link href="/reports" className="underline hover:text-text">
              Ledger
            </Link>{" "}
            in a minute for the finished report.
          </p>
        </div>
      )}

      {/* ---- Published: the paper rises, the desk compresses ---- */}
      {published && run.report && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-5 py-3.5 font-mono text-[14px] text-text-muted">
            <span>
              run complete · {run.revisionCount} revision{run.revisionCount === 1 ? "" : "s"} ·{" "}
              {run.usageSummary && (
                <>
                  {formatTokens(run.usageSummary.input_tokens + run.usageSummary.output_tokens)}{" "}
                  tokens · {formatMoney(run.usageSummary.cost_usd)} ·{" "}
                  {formatDuration(run.usageSummary.latency_ms)}
                </>
              )}
            </span>
            <span className="flex items-center gap-5">
              {run.reportId && (
                <Link href={`/reports/${run.reportId}`} className="underline hover:text-brand">
                  Open dossier
                </Link>
              )}
              <button onClick={reset} className="underline hover:text-brand">
                New research
              </button>
            </span>
          </div>
          <ReportPaper
            report={run.report}
            critic={run.critic}
            revisionCount={run.revisionCount}
            animate
          />
        </>
      )}

      {/* ---- The desk + tape ---- */}
      {!published && (
        <div className="grid gap-8 lg:grid-cols-[1.6fr_1fr]">
          <div className="space-y-6">
            <Desk run={run} />

            {(running || run.status === "error") &&
              SPECIALIST_KEYS.some((k) => run.agents[k].data) && (
                <section aria-label="Working notes" className="space-y-2.5">
                  <h2 className="font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted">
                    Working notes
                  </h2>
                  {SPECIALIST_KEYS.map((key) => {
                    const node = run.agents[key];
                    return node.data ? (
                      <SpecialistCard key={key} agent={key} output={node.data} />
                    ) : null;
                  })}
                </section>
              )}

            {run.verdicts.length > 0 && (
              <section aria-label="Critic verdicts" className="space-y-2">
                {run.verdicts.map((v, i) => (
                  <CriticCard
                    key={i}
                    blocked={v.blocks_publication}
                    challenges={v.challenges}
                    assessment={v.assessment}
                    revision={v.revision}
                  />
                ))}
              </section>
            )}
          </div>

          <div className="min-h-[320px] lg:min-h-[480px]">
            <Tape entries={run.tape} />
          </div>
        </div>
      )}
    </div>
  );
}
