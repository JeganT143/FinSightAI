/** Mirrors backend/schemas/agents.py — the typed contracts (ADR-3). */

export type Pillar = "fundamentals" | "technicals" | "risk" | "sentiment";

export type Verdict = "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL";

export interface Citation {
  source: string;
  quote: string;
}

export interface SpecialistOutput {
  score: number;
  confidence: "low" | "medium" | "high";
  summary: string;
  bullets: string[];
  data_warnings: string[];
  citations?: Citation[];
}

export interface PillarSummary {
  pillar: Pillar;
  score: number;
  summary: string;
}

export interface Report {
  ticker: string;
  verdict: Verdict;
  overall_score: number;
  pillars: PillarSummary[];
  thesis: string;
  key_risks: string[];
  catalysts: string[];
  citations: Citation[];
  narrative_markdown: string;
}

export interface Challenge {
  claim: string;
  reason: string;
  severity: "low" | "medium" | "high";
  pillar: Pillar | null;
}

export interface CriticOutput {
  challenges: Challenge[];
  blocks_publication: boolean;
  overall_assessment: string;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  model?: string;
}

export interface UsageSummary {
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number | null;
}

/** Mirrors backend/schemas/research.py responses. */

export interface ReportSummary {
  id: string;
  ticker: string;
  status: "running" | "complete" | "failed";
  verdict: Verdict | null;
  overall_score: number | null;
  revision_count: number;
  cost_usd: number;
  latency_ms: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface ReportListResponse {
  reports: ReportSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface AgentRunDetail {
  agent_name: string;
  phase: "research" | "synthesis" | "critique" | "revision";
  status: string;
  model: string;
  output: Record<string, unknown> | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  started_at: string;
  finished_at: string | null;
}

export interface ReportDetail {
  id: string;
  ticker: string;
  status: "running" | "complete" | "failed";
  verdict: Verdict | null;
  overall_score: number | null;
  report: Report | null;
  critic: CriticOutput | null;
  revision_count: number;
  error: string | null;
  usage: UsageSummary;
  agent_runs: AgentRunDetail[];
  created_at: string;
  completed_at: string | null;
}
