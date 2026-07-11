import { formatDuration, formatMoney, formatTokens } from "@/lib/score";
import type { AgentRunDetail } from "@/lib/types";

/** Phase palette — categorical, fixed order, machine-validated (DESIGN.md §2.1). */
const PHASE_COLOR: Record<AgentRunDetail["phase"], string> = {
  research: "var(--color-phase-research)",
  synthesis: "var(--color-phase-synthesis)",
  critique: "var(--color-phase-critique)",
  revision: "var(--color-phase-revision)",
};

const PHASE_ORDER: AgentRunDetail["phase"][] = ["research", "synthesis", "critique", "revision"];

/**
 * Per-agent latency bars on one shared time axis (DESIGN.md §4.5) — the
 * research bars overlapping in time is the parallel fan-out, made visible.
 */
export function TraceTimeline({ runs }: { runs: AgentRunDetail[] }) {
  if (runs.length === 0) return null;

  const starts = runs.map((r) => new Date(r.started_at + "Z").getTime());
  const t0 = Math.min(...starts);
  const tEnd = Math.max(
    ...runs.map((r, i) => starts[i] + Math.max(r.latency_ms, 1)),
  );
  const span = Math.max(tEnd - t0, 1);

  const phasesPresent = PHASE_ORDER.filter((p) => runs.some((r) => r.phase === p));

  return (
    <div>
      {/* Legend — identity never color-alone; each bar is also direct-labeled */}
      <div className="mb-4 flex flex-wrap gap-5">
        {phasesPresent.map((phase) => (
          <span key={phase} className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-text-muted">
            <span
              className="h-2.5 w-2.5 rounded-[3px]"
              style={{ background: PHASE_COLOR[phase] }}
              aria-hidden
            />
            {phase}
          </span>
        ))}
      </div>

      <ol className="space-y-2">
        {runs.map((run, i) => {
          const left = ((starts[i] - t0) / span) * 100;
          const width = Math.max((run.latency_ms / span) * 100, 0.75);
          // bars ending near the right edge get their label BEFORE the bar
          const labelAfter = left + width < 78;
          return (
            <li key={i} className="grid grid-cols-[8.5rem_1fr] items-center gap-3 sm:grid-cols-[10rem_1fr]">
              <span className="truncate font-mono text-[13px] text-text-muted">
                {run.agent_name.replace("Agent", "").toLowerCase()}
                {run.phase === "revision" && " ⟳"}
              </span>
              <div className="relative h-6 rounded bg-surface">
                <div
                  className="group absolute top-1/2 h-3 -translate-y-1/2 rounded-[3px]"
                  style={{
                    left: `${left}%`,
                    width: `${width}%`,
                    background: PHASE_COLOR[run.phase],
                  }}
                  title={`${run.agent_name} · ${run.phase} · ${formatDuration(run.latency_ms)} · ${formatTokens(run.input_tokens)}→${formatTokens(run.output_tokens)} tok · ${formatMoney(run.cost_usd)} · ${run.model}`}
                />
                <span
                  className="absolute top-1/2 -translate-y-1/2 whitespace-nowrap font-mono text-xs text-text-muted"
                  style={
                    labelAfter
                      ? { left: `calc(${left + width}% + 8px)` }
                      : { left: `calc(${left}% - 8px)`, transform: "translate(-100%, -50%)" }
                  }
                >
                  {formatDuration(run.latency_ms)} · {formatMoney(run.cost_usd)}
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
