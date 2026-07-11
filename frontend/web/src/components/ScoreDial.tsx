import { scoreTone } from "@/lib/score";

const TONE_STROKE = {
  bull: "var(--color-bull)",
  hold: "var(--color-hold)",
  bear: "var(--color-bear)",
} as const;

/**
 * SVG arc meter for a 0–10 score. The numeral wears ink (text token),
 * the arc wears the score color — text never wears series color (dataviz rule).
 */
export function ScoreDial({
  score,
  size = 96,
  onPaper = false,
}: {
  score: number;
  size?: number;
  onPaper?: boolean;
}) {
  const stroke = 7;
  const r = (size - stroke) / 2;
  const c = size / 2;
  // 270° sweep from 135° to 405°
  const circumference = 2 * Math.PI * r;
  const sweep = 0.75 * circumference;
  const filled = Math.max(0, Math.min(1, score / 10)) * sweep;
  const tone = scoreTone(score);

  return (
    <div
      className="relative inline-flex items-center justify-center"
      role="img"
      aria-label={`Overall score ${score.toFixed(1)} out of 10`}
    >
      <svg width={size} height={size} className="-rotate-[135deg]">
        <circle
          cx={c}
          cy={c}
          r={r}
          fill="none"
          stroke={onPaper ? "var(--color-paper-line)" : "var(--border)"}
          strokeWidth={stroke}
          strokeDasharray={`${sweep} ${circumference}`}
          strokeLinecap="round"
        />
        <circle
          cx={c}
          cy={c}
          r={r}
          fill="none"
          stroke={TONE_STROKE[tone]}
          strokeWidth={stroke}
          strokeDasharray={`${filled} ${circumference}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={`font-mono font-medium leading-none ${onPaper ? "text-paper-ink" : "text-text"}`}
          style={{ fontSize: size * 0.28 }}
        >
          {score.toFixed(1)}
        </span>
        <span
          className={`font-mono uppercase tracking-widest ${onPaper ? "text-paper-ink/50" : "text-text-muted"}`}
          style={{ fontSize: size * 0.09 }}
        >
          / 10
        </span>
      </div>
    </div>
  );
}
