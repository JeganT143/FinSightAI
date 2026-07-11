"use client";

import { useEffect, useState } from "react";
import { formatMoney } from "@/lib/score";
import type { RunState } from "@/lib/useResearchStream";

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const s = Math.max(0, Math.floor((now - since) / 1000));
  return (
    <span>
      {String(Math.floor(s / 60)).padStart(2, "0")}:{String(s % 60).padStart(2, "0")}
    </span>
  );
}

/** Live run header: ticker, phase message, cost accumulator, elapsed clock. */
export function RunStatusStrip({ run }: { run: RunState }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-5 py-3.5">
      <div className="flex items-center gap-3.5">
        <span className="font-mono text-lg font-medium uppercase tracking-[0.12em]">
          {run.ticker}
        </span>
        <span className="h-2 w-2 rounded-full bg-amber animate-breathe" aria-hidden />
        <span className="text-[15px] text-text-muted">
          {run.phaseMessage ?? "research in progress"}
        </span>
      </div>
      <div className="flex items-center gap-5 font-mono text-[15px] text-text-muted">
        <span title="Cost so far">{formatMoney(run.totalCost)}</span>
        {run.startedAt && <Elapsed since={run.startedAt} />}
      </div>
    </div>
  );
}
