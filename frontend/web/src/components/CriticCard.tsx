import type { Challenge } from "@/lib/types";

const SEVERITY_STYLE: Record<Challenge["severity"], string> = {
  high: "text-bear border-bear/40 bg-bear/10",
  medium: "text-hold border-hold/40 bg-hold/10",
  low: "text-text-muted border-border bg-surface",
};

export function Stamp({ blocked }: { blocked: boolean }) {
  return (
    <span
      className={`inline-block rounded border-2 px-2.5 py-1 font-mono text-[13px] font-medium uppercase tracking-[0.12em] animate-stamp ${
        blocked ? "border-bear text-bear" : "border-bull text-bull"
      }`}
    >
      {blocked ? "Revision required" : "Cleared for publication"}
    </span>
  );
}

/** The critic's review note — challenges are shown with pride, not hidden. */
export function CriticCard({
  blocked,
  challenges,
  assessment,
  revision,
}: {
  blocked: boolean;
  challenges: Challenge[];
  assessment: string;
  revision?: number;
}) {
  return (
    <div
      className={`rounded-lg border bg-surface p-4 ${blocked ? "border-bear/50" : "border-border"}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="font-mono text-[13px] uppercase tracking-wider text-text-muted">
          Critic review{revision != null && revision > 0 ? ` · after revision ${revision}` : ""}
        </span>
        <Stamp blocked={blocked} />
      </div>
      <p className="mt-3 text-[15px] leading-relaxed text-text">{assessment}</p>
      {challenges.length > 0 && (
        <ul className="mt-3 space-y-2.5">
          {challenges.map((c, i) => (
            <li key={i} className="text-[15px] leading-relaxed">
              <span
                className={`mr-2 inline-block rounded border px-2 py-px font-mono text-xs uppercase tracking-wider ${SEVERITY_STYLE[c.severity]}`}
              >
                {c.severity}
              </span>
              <span className="text-text">“{c.claim}”</span>
              <span className="text-text-muted"> — {c.reason}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
