import Link from "next/link";
import { VerdictChip } from "@/components/VerdictChip";
import { fetchReports } from "@/lib/api";
import { formatDuration, formatMoney, scoreTone, TONE_TEXT } from "@/lib/score";

export const dynamic = "force-dynamic";

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso + "Z").getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default async function LedgerPage({
  searchParams,
}: {
  searchParams: Promise<{ ticker?: string }>;
}) {
  const { ticker } = await searchParams;

  let error: string | null = null;
  let reports: Awaited<ReturnType<typeof fetchReports>>["reports"] = [];
  let total = 0;
  try {
    const data = await fetchReports({ ticker, limit: 50 });
    reports = data.reports;
    total = data.total;
  } catch {
    error = "The backend is unreachable — start it and reload.";
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-mono text-[14px] uppercase tracking-[0.2em] text-text-muted">Ledger</h1>
          <p className="mt-1.5 text-2xl font-semibold">
            {total} research run{total === 1 ? "" : "s"}
            {ticker && (
              <span className="font-mono font-normal text-text-muted">
                {" "}
                · filtered to {ticker.toUpperCase()}
              </span>
            )}
          </p>
        </div>
        <form method="get" className="flex overflow-hidden rounded-lg border border-border">
          <input
            name="ticker"
            defaultValue={ticker ?? ""}
            placeholder="Filter by ticker"
            className="bg-surface px-4 py-2.5 font-mono text-[14px] uppercase text-text placeholder:normal-case placeholder:text-text-muted/60 focus:outline-none"
          />
          <button className="border-l border-border bg-surface px-4 font-mono text-[14px] uppercase tracking-wider text-text-muted hover:text-brand">
            Filter
          </button>
        </form>
      </div>

      {error ? (
        <div role="alert" className="rounded-lg border border-bear/50 bg-bear/10 px-5 py-4 text-[15px]">
          {error}
        </div>
      ) : reports.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface px-6 py-14 text-center">
          <p className="text-lg text-text">No research yet.</p>
          <p className="mt-1.5 text-[15px] text-text-muted">
            Run your first ticker from the{" "}
            <Link href="/" className="underline hover:text-brand">
              Console
            </Link>
            .
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[760px] border-collapse font-mono text-[14px]">
            <thead>
              <tr className="border-b border-border bg-surface text-left text-[13px] uppercase tracking-wider text-text-muted">
                <th className="px-5 py-3.5 font-medium">Ticker</th>
                <th className="px-5 py-3.5 font-medium">Verdict</th>
                <th className="px-5 py-3.5 text-right font-medium">Score</th>
                <th className="px-5 py-3.5 text-right font-medium">Revisions</th>
                <th className="px-5 py-3.5 text-right font-medium">Cost</th>
                <th className="px-5 py-3.5 text-right font-medium">Duration</th>
                <th className="px-5 py-3.5 text-right font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className="border-b border-border/60 transition-colors hover:bg-surface">
                  <td className="px-5 py-3.5">
                    <Link
                      href={`/reports/${r.id}`}
                      className="text-[15px] font-medium uppercase tracking-widest text-text hover:text-brand"
                    >
                      {r.ticker}
                    </Link>
                  </td>
                  <td className="px-5 py-3.5">
                    {r.status === "failed" ? (
                      <span className="text-bear">failed</span>
                    ) : r.status === "running" ? (
                      <span className="text-amber">running</span>
                    ) : r.verdict ? (
                      <VerdictChip verdict={r.verdict} />
                    ) : (
                      "—"
                    )}
                  </td>
                  <td
                    className={`px-5 py-3.5 text-right text-[15px] font-medium ${
                      r.overall_score != null ? TONE_TEXT[scoreTone(r.overall_score)] : "text-text-muted"
                    }`}
                  >
                    {r.overall_score?.toFixed(1) ?? "—"}
                  </td>
                  <td className="px-5 py-3.5 text-right text-text-muted">
                    {r.revision_count > 0 ? `⟳ ${r.revision_count}` : "—"}
                  </td>
                  <td className="px-5 py-3.5 text-right text-text-muted">{formatMoney(r.cost_usd)}</td>
                  <td className="px-5 py-3.5 text-right text-text-muted">
                    {formatDuration(r.latency_ms)}
                  </td>
                  <td className="px-5 py-3.5 text-right text-text-muted">
                    {relativeTime(r.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
