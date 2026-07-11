"use client";

import { scoreTone, TONE_TEXT } from "@/lib/score";
import type { SpecialistOutput } from "@/lib/types";

/** Working-notes card: one specialist's structured output (DESIGN.md §4.2). */
export function SpecialistCard({
  agent,
  output,
}: {
  agent: string;
  output: SpecialistOutput;
}) {
  const tone = scoreTone(output.score);

  return (
    <details className="group rounded-lg border border-border bg-surface" open>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <span className="text-[15px] font-semibold capitalize">{agent}</span>
        <span className="flex items-center gap-4 font-mono text-[14px]">
          <span className="text-text-muted">{output.confidence} conf</span>
          <span className={`text-base font-medium ${TONE_TEXT[tone]}`}>
            {output.score.toFixed(1)}
          </span>
          <span className="text-text-muted transition-transform group-open:rotate-90" aria-hidden>
            ▸
          </span>
        </span>
      </summary>
      <div className="border-t border-border px-4 py-3.5 text-[15px] leading-relaxed">
        <p className="text-text">{output.summary}</p>
        <ul className="mt-2.5 space-y-1.5 text-text-muted">
          {output.bullets.map((b, i) => (
            <li key={i} className="flex gap-2.5">
              <span aria-hidden>·</span>
              <span>{b}</span>
            </li>
          ))}
        </ul>
        {output.citations && output.citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {output.citations.map((c, i) => (
              <span
                key={i}
                title={`“${c.quote}”`}
                className="rounded border border-border px-2 py-0.5 font-mono text-xs uppercase tracking-wider text-brand"
              >
                {c.source.split("—")[0].trim()}
              </span>
            ))}
          </div>
        )}
        {output.data_warnings.length > 0 && (
          <p className="mt-3 font-mono text-[13px] text-hold">
            data gaps: {output.data_warnings.join(", ")}
          </p>
        )}
      </div>
    </details>
  );
}
