import { formatVerdict, verdictTone } from "@/lib/score";
import type { Verdict } from "@/lib/types";

const TONE_STYLES = {
  bull: "text-bull border-bull/40 bg-bull/10",
  hold: "text-hold border-hold/40 bg-hold/10",
  bear: "text-bear border-bear/40 bg-bear/10",
} as const;

/** Verdict is always color + text, never color alone (DESIGN.md §7). */
export function VerdictChip({ verdict, size = "sm" }: { verdict: Verdict; size?: "sm" | "lg" }) {
  const tone = verdictTone(verdict);
  return (
    <span
      className={`inline-flex items-center rounded border font-mono font-medium uppercase tracking-wider ${TONE_STYLES[tone]} ${
        size === "lg" ? "px-3.5 py-1.5 text-base" : "px-2.5 py-0.5 text-[13px]"
      }`}
    >
      {formatVerdict(verdict)}
    </span>
  );
}
