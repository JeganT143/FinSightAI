import type { Verdict } from "./types";

/** DESIGN.md §2.1 — the single score→color mapping used everywhere. */
export type ScoreTone = "bull" | "hold" | "bear";

export function scoreTone(score: number): ScoreTone {
  if (score >= 6.5) return "bull";
  if (score >= 4.5) return "hold";
  return "bear";
}

export function verdictTone(verdict: Verdict): ScoreTone {
  if (verdict === "STRONG_BUY" || verdict === "BUY") return "bull";
  if (verdict === "HOLD") return "hold";
  return "bear";
}

export const TONE_TEXT: Record<ScoreTone, string> = {
  bull: "text-bull",
  hold: "text-hold",
  bear: "text-bear",
};

export const TONE_BG: Record<ScoreTone, string> = {
  bull: "bg-bull",
  hold: "bg-hold",
  bear: "bg-bear",
};

export const TONE_BORDER: Record<ScoreTone, string> = {
  bull: "border-bull",
  hold: "border-hold",
  bear: "border-bear",
};

export function formatVerdict(verdict: Verdict): string {
  return verdict.replace("_", " ");
}

export function formatMoney(usd: number): string {
  return `$${usd.toFixed(4)}`;
}

export function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

export function formatTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}
