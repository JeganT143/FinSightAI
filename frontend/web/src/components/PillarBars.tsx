import { scoreTone } from "@/lib/score";
import type { PillarSummary } from "@/lib/types";

const TONE_FILL = {
  bull: "bg-bull",
  hold: "bg-hold",
  bear: "bg-bear",
} as const;

const PILLAR_ORDER = ["fundamentals", "technicals", "risk", "sentiment"] as const;

/**
 * Four thin horizontal bars, shared 0–10 scale, direct-labeled with name +
 * mono value (color never the sole carrier). Paper-surface variant only —
 * this lives inside the report.
 */
export function PillarBars({ pillars }: { pillars: PillarSummary[] }) {
  const byPillar = new Map(pillars.map((p) => [p.pillar, p]));
  const ordered = PILLAR_ORDER.map((k) => byPillar.get(k)).filter(
    (p): p is PillarSummary => p != null,
  );

  return (
    <div className="space-y-2.5">
      {ordered.map((p) => (
        <div key={p.pillar} className="grid grid-cols-[8.5rem_1fr_3rem] items-center gap-4">
          <span className="font-mono text-[13px] uppercase tracking-wider text-paper-ink/70">
            {p.pillar}
          </span>
          <div
            className="h-2.5 rounded-[3px] bg-paper-line"
            role="img"
            aria-label={`${p.pillar} score ${p.score.toFixed(1)} out of 10`}
          >
            <div
              className={`h-full rounded-[3px] ${TONE_FILL[scoreTone(p.score)]}`}
              style={{ width: `${Math.max(2, (p.score / 10) * 100)}%` }}
            />
          </div>
          <span className="text-right font-mono text-[15px] font-medium text-paper-ink">
            {p.score.toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  );
}
