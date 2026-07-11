"use client";

import type { AgentKey } from "@/lib/events";
import { scoreTone } from "@/lib/score";
import type { AgentNodeState, RunState } from "@/lib/useResearchStream";

const SPECIALISTS: { key: AgentKey; label: string; role: string }[] = [
  { key: "fundamentals", label: "Fundamentals", role: "valuation · growth · filings" },
  { key: "technicals", label: "Technicals", role: "momentum · trend · volatility" },
  { key: "risk", label: "Risk", role: "leverage · beta · Item 1A" },
  { key: "sentiment", label: "Sentiment", role: "analysts · news flow" },
];

const TONE_TEXT = { bull: "text-bull", hold: "text-hold", bear: "text-bear" } as const;

function StateDot({ node }: { node: AgentNodeState }) {
  if (node.state === "working")
    return <span className="h-2.5 w-2.5 rounded-full bg-amber animate-breathe" aria-hidden />;
  if (node.state === "done")
    return <span className="h-2.5 w-2.5 rounded-full bg-bull" aria-hidden />;
  if (node.state === "failed")
    return <span className="h-2.5 w-2.5 rounded-full bg-bear" aria-hidden />;
  return <span className="h-2.5 w-2.5 rounded-full border-[1.5px] border-text-faint" aria-hidden />;
}

function stateText(node: AgentNodeState): string {
  if (node.state === "working") return "working";
  if (node.state === "done") return node.score != null ? node.score.toFixed(1) : "done";
  if (node.state === "failed") return "failed";
  return "idle";
}

function AgentNodeCard({
  label,
  role,
  node,
}: {
  label: string;
  role: string;
  node: AgentNodeState;
}) {
  const active = node.state === "working";
  const scoreClass =
    node.state === "done" && node.score != null ? TONE_TEXT[scoreTone(node.score)] : "text-text-muted";
  return (
    <div
      aria-label={`${label} agent: ${stateText(node)}`}
      className={`rounded-lg border bg-surface px-4 py-3 transition-colors ${
        active ? "border-amber/70" : "border-border"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[15px] font-semibold">{label}</span>
        <StateDot node={node} />
      </div>
      <div className="mt-1.5 flex items-baseline justify-between gap-3">
        <span className="truncate text-[13px] text-text-muted">{role}</span>
        <span
          className={`font-mono text-[15px] font-medium ${active ? "text-amber" : scoreClass}`}
        >
          {stateText(node)}
        </span>
      </div>
    </div>
  );
}

/**
 * The desk (DESIGN.md §4.1): the architecture drawn as UI. Four specialists
 * converge on the synthesizer, which trades drafts with the critic; the
 * loop-back edge lights up when a revision is running.
 */
export function Desk({ run }: { run: RunState }) {
  const revising = run.synthesizerPhase === "revision";
  const synthNode = run.agents.synthesizer;
  const criticNode = run.agents.critic;

  return (
    <section aria-label="Agent pipeline">
      <h2 className="mb-4 font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted">
        The desk
      </h2>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        {SPECIALISTS.map((s) => (
          <AgentNodeCard key={s.key} label={s.label} role={s.role} node={run.agents[s.key]} />
        ))}
      </div>

      {/* Confluence lines */}
      <svg viewBox="0 0 400 36" className="mx-auto block h-9 w-full max-w-2xl" aria-hidden>
        {[50, 150, 250, 350].map((x) => (
          <path
            key={x}
            d={`M ${x} 0 C ${x} 18, 200 14, 200 36`}
            fill="none"
            stroke="var(--border)"
            strokeWidth="1.5"
          />
        ))}
      </svg>

      <div className="mx-auto grid max-w-2xl grid-cols-[1fr_auto_1fr] items-stretch gap-0">
        <AgentNodeCard
          label="Synthesizer"
          role={revising ? "revising the draft" : "drafts the report"}
          node={synthNode}
        />
        <div className="flex w-20 flex-col items-center justify-center gap-1.5" aria-hidden>
          <svg viewBox="0 0 64 12" className="h-3 w-16">
            <path d="M 4 6 H 52" stroke="var(--border)" strokeWidth="1.5" />
            <path d="M 52 6 l -6 -4 v 8 z" fill="var(--border)" transform="rotate(180 49 6)" />
          </svg>
          <span className="font-mono text-[11px] uppercase tracking-wider text-text-muted">draft</span>
          <svg viewBox="0 0 64 12" className="h-3 w-16">
            <path
              d="M 60 6 H 12"
              stroke={revising ? "var(--color-bear)" : "var(--border)"}
              strokeWidth="1.5"
            />
            <path
              d="M 12 6 l 6 -4 v 8 z"
              fill={revising ? "var(--color-bear)" : "var(--border)"}
            />
          </svg>
          <span
            className={`font-mono text-[11px] uppercase tracking-wider ${revising ? "text-bear" : "text-text-muted"}`}
          >
            revise
          </span>
        </div>
        <AgentNodeCard label="Critic" role="attacks every claim" node={criticNode} />
      </div>
      <p className="mt-3 text-center font-mono text-xs uppercase tracking-wider text-text-muted">
        revision loop · max 2 rounds
      </p>
    </section>
  );
}
