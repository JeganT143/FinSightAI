import { PillarBars } from "./PillarBars";
import { ScoreDial } from "./ScoreDial";
import { VerdictChip } from "./VerdictChip";
import type { CriticOutput, Report } from "@/lib/types";

/**
 * The paper (DESIGN.md §4.3): the published artifact. Bone surface, serif
 * voice — the one place the machine room's mono/ink language doesn't reach.
 * Shared between console (post-publication) and dossier.
 */
export function ReportPaper({
  report,
  critic,
  revisionCount,
  publishedAt,
  animate = false,
}: {
  report: Report;
  critic?: CriticOutput | null;
  revisionCount?: number;
  publishedAt?: string;
  animate?: boolean;
}) {
  const unresolved = critic?.blocks_publication ?? false;

  return (
    <article
      className={`on-paper rounded bg-paper p-6 text-paper-ink shadow-[0_8px_40px_rgba(0,0,0,0.45)] sm:p-12 ${animate ? "animate-publish" : ""}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-8 border-b-2 border-paper-ink pb-8">
        <div>
          <p className="font-mono text-[13px] uppercase tracking-[0.22em] text-paper-ink/60">
            Investment report
          </p>
          <h1 className="mt-2 font-serif text-5xl font-medium tracking-tight sm:text-6xl">
            {report.ticker}
          </h1>
          <p className="mt-3 font-mono text-[14px] text-paper-ink/65">
            {publishedAt
              ? new Date(publishedAt).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })
              : "Published just now"}
            {revisionCount != null && revisionCount > 0 && (
              <> · survived {revisionCount} critic revision{revisionCount === 1 ? "" : "s"}</>
            )}
          </p>
        </div>
        <div className="flex flex-col items-center gap-3">
          <ScoreDial score={report.overall_score} size={116} onPaper />
          <VerdictChip verdict={report.verdict} size="lg" />
        </div>
      </header>

      <section className="mt-8">
        <h2 className="font-serif text-2xl font-medium">Thesis</h2>
        <p className="mt-3 font-serif text-[19px] leading-relaxed">{report.thesis}</p>
      </section>

      <section className="mt-8">
        <h2 className="mb-4 font-serif text-2xl font-medium">Pillars</h2>
        <PillarBars pillars={report.pillars} />
        <div className="mt-5 grid gap-x-8 gap-y-4 sm:grid-cols-2">
          {report.pillars.map((p) => (
            <p key={p.pillar} className="text-[15.5px] leading-relaxed text-paper-ink/85">
              <span className="font-mono text-xs uppercase tracking-wider text-paper-ink/55">
                {p.pillar} ·{" "}
              </span>
              {p.summary}
            </p>
          ))}
        </div>
      </section>

      <div className="mt-8 grid gap-8 border-t border-paper-line pt-8 sm:grid-cols-2">
        <section>
          <h2 className="font-serif text-2xl font-medium">Key risks</h2>
          <ul className="mt-3 space-y-2 text-[16px] leading-relaxed">
            {report.key_risks.map((r, i) => (
              <li key={i} className="flex gap-2.5">
                <span className="text-bear" aria-hidden>
                  ▪
                </span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="font-serif text-2xl font-medium">Catalysts</h2>
          {report.catalysts.length > 0 ? (
            <ul className="mt-3 space-y-2 text-[16px] leading-relaxed">
              {report.catalysts.map((c, i) => (
                <li key={i} className="flex gap-2.5">
                  <span className="text-bull" aria-hidden>
                    ▪
                  </span>
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-[16px] text-paper-ink/60">
              No near-term catalysts identified in the data.
            </p>
          )}
        </section>
      </div>

      {report.citations.length > 0 && (
        <section className="mt-8 border-t border-paper-line pt-6">
          <h2 className="font-mono text-[13px] uppercase tracking-[0.18em] text-paper-ink/60">
            Sources — SEC filings
          </h2>
          <ul className="mt-3 space-y-2.5">
            {report.citations.map((c, i) => (
              <li key={i} className="text-[15px] leading-relaxed">
                <span className="rounded border border-paper-line bg-white/50 px-2 py-0.5 font-mono text-[12.5px]">
                  {/* scrub control bytes (LLM-garbled dashes) + dashes for the mono chip */}
                  {c.source.replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s*[\u2013\u2014]\s*/g, " \u00b7 ").replace(/\s{2,}/g, " ")}
                </span>{" "}
                <span className="font-serif text-[16px] italic text-paper-ink/80">
                  “{c.quote}”
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {critic && (
        <footer className="mt-8 border-t border-paper-line pt-5">
          <p className="font-mono text-[13.5px] text-paper-ink/75">
            <span className={unresolved ? "text-bear" : "text-bull"}>
              {unresolved ? "⚑ published with unresolved challenges" : "⊘ cleared by the critic"}
            </span>
            {" — "}
            {critic.challenges.length} challenge{critic.challenges.length === 1 ? "" : "s"} raised
            {revisionCount != null && ` · ${revisionCount} revision${revisionCount === 1 ? "" : "s"}`}
          </p>
        </footer>
      )}
    </article>
  );
}
