import Link from "next/link";
import { notFound } from "next/navigation";
import { CriticCard } from "@/components/CriticCard";
import { ReportPaper } from "@/components/ReportPaper";
import { TraceTimeline } from "@/components/TraceTimeline";
import { fetchReport } from "@/lib/api";
import { serverToken } from "@/lib/server-auth";
import { formatDuration, formatMoney, formatTokens } from "@/lib/score";

export const dynamic = "force-dynamic";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface px-5 py-4">
      <dt className="font-mono text-xs uppercase tracking-[0.18em] text-text-muted">{label}</dt>
      <dd className="mt-1.5 font-mono text-2xl font-medium text-text">{value}</dd>
    </div>
  );
}

export default async function DossierPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const detail = await fetchReport(id, await serverToken()).catch(() => {
    throw new Error("The backend is unreachable — start it and reload.");
  });
  if (!detail) notFound();

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="font-mono text-[15px] uppercase tracking-[0.2em] text-text-muted">
          Dossier · <span className="text-text">{detail.ticker}</span> ·{" "}
          <span className="normal-case tracking-normal">{detail.id.slice(0, 8)}</span>
        </h1>
        <Link
          href="/reports"
          className="font-mono text-[14px] uppercase tracking-wider text-text-muted underline hover:text-brand"
        >
          ← Ledger
        </Link>
      </div>

      {detail.status === "failed" && (
        <div role="alert" className="rounded-lg border border-bear/50 bg-bear/10 px-5 py-4">
          <p className="text-[15px]">This run failed: {detail.error ?? "unknown error"}</p>
          <p className="mt-1.5 text-[15px] text-text-muted">
            Whatever the agents finished before the failure is traced below.{" "}
            <Link href="/" className="underline hover:text-text">
              Run it again
            </Link>
            .
          </p>
        </div>
      )}

      {detail.status === "running" && (
        <div className="rounded-lg border border-hold/50 bg-hold/10 px-5 py-4 text-[15px]">
          This run is still in progress — reload in a moment.
        </div>
      )}

      {detail.report && (
        <ReportPaper
          report={detail.report}
          critic={detail.critic}
          revisionCount={detail.revision_count}
          publishedAt={detail.completed_at ?? detail.created_at}
        />
      )}

      {detail.critic && detail.critic.challenges.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted">
            Critique trail
          </h2>
          <CriticCard
            blocked={detail.critic.blocks_publication}
            challenges={detail.critic.challenges}
            assessment={detail.critic.overall_assessment}
          />
        </section>
      )}

      {detail.agent_runs.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted">
            Agent traces
          </h2>
          <div className="rounded-lg border border-border bg-bg p-5">
            <TraceTimeline runs={detail.agent_runs} />
          </div>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted">
          Run economics
        </h2>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Total cost" value={formatMoney(detail.usage.cost_usd)} />
          <Stat
            label="Tokens in / out"
            value={`${formatTokens(detail.usage.input_tokens)} / ${formatTokens(detail.usage.output_tokens)}`}
          />
          <Stat label="Wall time" value={formatDuration(detail.usage.latency_ms)} />
          <Stat
            label="Revisions"
            value={detail.revision_count > 0 ? `⟳ ${detail.revision_count}` : "none"}
          />
        </dl>
      </section>
    </div>
  );
}
