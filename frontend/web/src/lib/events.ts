/** SSE event protocol — mirrors ARCHITECTURE.md §6. */

import type { Challenge, Report, SpecialistOutput, Usage, UsageSummary } from "./types";

export type AgentKey = "fundamentals" | "technicals" | "risk" | "sentiment" | "synthesizer" | "critic";

export type PipelinePhase = "grounding" | "research" | "synthesis" | "critique" | "revision";

export interface StartEvent {
  type: "start";
  report_id: string;
  ticker: string;
}

export interface PhaseEvent {
  type: "phase";
  phase: PipelinePhase;
  message: string;
}

export interface GroundingEvent {
  type: "grounding";
  status: "ingested" | "cached" | "unavailable";
  detail: string;
  form_type: string | null;
  filing_date: string | null;
  chunk_count: number;
}

export interface AgentStartedEvent {
  type: "agent_started";
  agent: AgentKey;
  phase: PipelinePhase;
}

export interface AgentCompletedEvent {
  type: "agent_completed";
  agent: AgentKey;
  phase: PipelinePhase;
  data: SpecialistOutput & Partial<Report>;
  usage: Usage;
}

export interface CriticVerdictEvent {
  type: "critic_verdict";
  revision: number;
  challenges: Challenge[];
  blocks_publication: boolean;
  assessment: string;
  usage: Usage;
}

export interface CompleteEvent {
  type: "complete";
  report_id: string;
  ticker: string;
  report: Report;
  critic: { challenges: Challenge[]; blocks_publication: boolean; overall_assessment: string };
  revision_count: number;
  usage_summary: UsageSummary;
}

export interface ErrorEvent {
  type: "error";
  message: string;
  report_id?: string;
}

export type PipelineEvent =
  | StartEvent
  | PhaseEvent
  | GroundingEvent
  | AgentStartedEvent
  | AgentCompletedEvent
  | CriticVerdictEvent
  | CompleteEvent
  | ErrorEvent;
