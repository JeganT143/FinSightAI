"use client";

import { useEffect, useRef } from "react";
import { formatDuration, formatMoney } from "@/lib/score";
import type { TapeEntry } from "@/lib/useResearchStream";

const KIND_COLOR: Record<TapeEntry["kind"], string> = {
  info: "text-text-muted",
  agent: "text-text",
  critic: "text-phase-critique",
  error: "text-bear",
  done: "text-brand",
};

function timestamp(at: number): string {
  return new Date(at).toLocaleTimeString("en-GB", { hour12: false });
}

/**
 * The tape (DESIGN.md §4.2): the audit trail of the run, written line by
 * line. aria-live so the run is narrated to screen readers.
 */
export function Tape({ entries }: { entries: TapeEntry[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [entries.length]);

  return (
    <section aria-label="Run activity tape" className="flex h-full min-h-0 flex-col">
      <h2 className="mb-4 font-mono text-[13px] uppercase tracking-[0.2em] text-text-muted">
        The tape
      </h2>
      <div
        ref={scrollRef}
        aria-live="polite"
        className="min-h-0 flex-1 overflow-y-auto rounded-lg border border-border bg-surface p-4 font-mono text-[14px] leading-[1.9]"
      >
        {entries.length === 0 ? (
          <p className="text-text-muted">Waiting for a run. Events will be written here live.</p>
        ) : (
          <ol className="space-y-1">
            {entries.map((e, i) => (
              <li key={`${e.at}-${i}`} className="animate-tape-in">
                <span className="text-text-muted/70">{timestamp(e.at)}</span>{" "}
                <span className={KIND_COLOR[e.kind]}>{e.text}</span>
                {e.cost_usd != null && (
                  <span className="text-text-muted/80">
                    {" "}
                    · {formatMoney(e.cost_usd)}
                    {e.latency_ms != null && ` · ${formatDuration(e.latency_ms)}`}
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
