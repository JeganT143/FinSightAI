"use client";

/**
 * The streaming state machine (DESIGN.md §5).
 *
 * POST + fetch/ReadableStream SSE parsing (native EventSource is GET-only,
 * ADR-7). Every SSE event goes through one reducer so each UI state is
 * renderable in isolation and the tape is a pure projection of events.
 */

import { useCallback, useReducer, useRef } from "react";
import { useAuthToken } from "@/components/AuthTokenBridge";
import type {
  AgentKey,
  CriticVerdictEvent,
  GroundingEvent,
  PipelineEvent,
} from "./events";
import type { Report, SpecialistOutput, Usage, UsageSummary } from "./types";
import { authHeaders, PUBLIC_API_URL } from "./api";

export type NodeState = "idle" | "working" | "done" | "failed";

export interface AgentNodeState {
  state: NodeState;
  score?: number;
  data?: SpecialistOutput;
  usage?: Usage;
}

export interface TapeEntry {
  at: number; // epoch ms, client clock
  kind: "info" | "agent" | "critic" | "error" | "done";
  text: string;
  cost_usd?: number;
  latency_ms?: number;
}

export interface RunState {
  status: "idle" | "running" | "complete" | "error" | "disconnected" | "quota_exceeded";
  ticker: string;
  reportId?: string;
  startedAt?: number;
  phaseMessage?: string;
  grounding?: GroundingEvent;
  agents: Record<AgentKey, AgentNodeState>;
  synthesizerPhase: "synthesis" | "revision";
  tape: TapeEntry[];
  verdicts: CriticVerdictEvent[];
  report?: Report;
  critic?: CompleteCritic;
  revisionCount: number;
  usageSummary?: UsageSummary;
  totalCost: number;
  error?: string;
}

interface CompleteCritic {
  challenges: CriticVerdictEvent["challenges"];
  blocks_publication: boolean;
  overall_assessment: string;
}

const IDLE_AGENTS: Record<AgentKey, AgentNodeState> = {
  fundamentals: { state: "idle" },
  technicals: { state: "idle" },
  risk: { state: "idle" },
  sentiment: { state: "idle" },
  synthesizer: { state: "idle" },
  critic: { state: "idle" },
};

export const initialRunState: RunState = {
  status: "idle",
  ticker: "",
  agents: IDLE_AGENTS,
  synthesizerPhase: "synthesis",
  tape: [],
  verdicts: [],
  revisionCount: 0,
  totalCost: 0,
};

type Action =
  | { type: "run_requested"; ticker: string }
  | { type: "event"; event: PipelineEvent }
  | { type: "disconnected" }
  | { type: "failed"; message: string }
  | { type: "quota_exceeded"; message: string }
  | { type: "reset" };

const TAPE_CAP = 200;

function pushTape(tape: TapeEntry[], entry: TapeEntry): TapeEntry[] {
  const next = [...tape, entry];
  return next.length > TAPE_CAP ? next.slice(next.length - TAPE_CAP) : next;
}

function reduceEvent(state: RunState, event: PipelineEvent): RunState {
  const now = Date.now();
  switch (event.type) {
    case "start":
      return {
        ...state,
        reportId: event.report_id,
        tape: pushTape(state.tape, {
          at: now,
          kind: "info",
          text: `run ${event.report_id.slice(0, 8)} started for ${event.ticker}`,
        }),
      };

    case "phase":
      return {
        ...state,
        phaseMessage: event.message,
        synthesizerPhase: event.phase === "revision" ? "revision" : state.synthesizerPhase,
        tape: pushTape(state.tape, { at: now, kind: "info", text: event.message }),
      };

    case "grounding": {
      const text =
        event.status === "unavailable"
          ? `filings unavailable — ${event.detail}`
          : `${event.form_type} ${event.filing_date} · ${event.chunk_count} chunks ${event.status === "cached" ? "(cached)" : "embedded"}`;
      return {
        ...state,
        grounding: event,
        tape: pushTape(state.tape, { at: now, kind: "info", text }),
      };
    }

    case "agent_started":
      return {
        ...state,
        agents: { ...state.agents, [event.agent]: { ...state.agents[event.agent], state: "working" } },
      };

    case "agent_completed": {
      const isSpecialist = event.phase === "research";
      const score = isSpecialist
        ? (event.data as SpecialistOutput).score
        : (event.data as Report).overall_score;
      const next: RunState = {
        ...state,
        totalCost: state.totalCost + event.usage.cost_usd,
        agents: {
          ...state.agents,
          [event.agent]: {
            state: "done",
            score,
            data: isSpecialist ? (event.data as SpecialistOutput) : undefined,
            usage: event.usage,
          },
        },
        tape: pushTape(state.tape, {
          at: now,
          kind: "agent",
          text: `${event.agent} ${event.phase === "revision" ? "revised draft" : `scored ${score.toFixed(1)}`}`,
          cost_usd: event.usage.cost_usd,
          latency_ms: event.usage.latency_ms,
        }),
      };
      if (event.phase !== "research") {
        next.report = event.data as Report;
      }
      return next;
    }

    case "critic_verdict": {
      const text = event.blocks_publication
        ? `critic blocked publication — ${event.challenges.length} challenge${event.challenges.length === 1 ? "" : "s"}`
        : `critic cleared the draft — ${event.challenges.length} note${event.challenges.length === 1 ? "" : "s"}`;
      return {
        ...state,
        totalCost: state.totalCost + event.usage.cost_usd,
        verdicts: [...state.verdicts, event],
        agents: {
          ...state.agents,
          critic: { state: "done", usage: event.usage },
          // a blocking verdict re-arms the synthesizer (loop-back)
          synthesizer: event.blocks_publication
            ? { ...state.agents.synthesizer, state: "idle" }
            : state.agents.synthesizer,
        },
        tape: pushTape(state.tape, {
          at: now,
          kind: "critic",
          text,
          cost_usd: event.usage.cost_usd,
          latency_ms: event.usage.latency_ms,
        }),
      };
    }

    case "complete":
      return {
        ...state,
        status: "complete",
        report: event.report,
        critic: event.critic,
        revisionCount: event.revision_count,
        usageSummary: event.usage_summary,
        totalCost: event.usage_summary.cost_usd,
        phaseMessage: undefined,
        tape: pushTape(state.tape, {
          at: now,
          kind: "done",
          text: `published — ${event.report.verdict} ${event.report.overall_score.toFixed(1)}`,
          cost_usd: event.usage_summary.cost_usd,
          latency_ms: event.usage_summary.latency_ms ?? undefined,
        }),
      };

    case "error":
      return {
        ...state,
        status: "error",
        error: event.message,
        phaseMessage: undefined,
        tape: pushTape(state.tape, { at: now, kind: "error", text: event.message }),
      };
  }
}

function reducer(state: RunState, action: Action): RunState {
  switch (action.type) {
    case "run_requested":
      return {
        ...initialRunState,
        status: "running",
        ticker: action.ticker,
        startedAt: Date.now(),
      };
    case "event":
      return reduceEvent(state, action.event);
    case "disconnected":
      return state.status === "running" ? { ...state, status: "disconnected" } : state;
    case "failed":
      return { ...state, status: "error", error: action.message };
    case "quota_exceeded":
      // A limit, not an error (SAAS_DESIGN §8) — the console renders it hold-toned.
      return { ...state, status: "quota_exceeded", error: action.message };
    case "reset":
      return initialRunState;
  }
}

export function useResearchStream() {
  const [state, dispatch] = useReducer(reducer, initialRunState);
  const abortRef = useRef<AbortController | null>(null);
  const getToken = useAuthToken();

  const start = useCallback(
    async (ticker: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      dispatch({ type: "run_requested", ticker });

      try {
        const token = await getToken();
        const res = await fetch(`${PUBLIC_API_URL}/api/research/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders(token) },
          body: JSON.stringify({ ticker }),
          signal: controller.signal,
        });
        if (res.status === 402) {
          const body = await res.json().catch(() => ({ detail: "Plan limit reached." }));
          dispatch({ type: "quota_exceeded", message: body.detail ?? "Plan limit reached." });
          return;
        }
        if (!res.ok || !res.body) {
          const detail = await res.text().catch(() => "");
          throw new Error(`Backend refused the run (${res.status}). ${detail.slice(0, 200)}`);
        }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let sep: number;
        while ((sep = buffer.indexOf("\n\n")) >= 0) {
          const frame = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          for (const line of frame.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (!raw || raw === "{}") continue;
            try {
              dispatch({ type: "event", event: JSON.parse(raw) as PipelineEvent });
            } catch {
              // tolerate malformed frames rather than killing the run view
            }
          }
        }
      }
      dispatch({ type: "disconnected" });
    } catch (err) {
      if (controller.signal.aborted) return;
      dispatch({
        type: "failed",
        message:
          err instanceof Error && err.message.includes("fetch")
            ? "Cannot reach the backend at " + PUBLIC_API_URL + ". Is it running?"
            : err instanceof Error
              ? err.message
              : "Unexpected streaming error",
      });
    }
  }, [getToken]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "reset" });
  }, []);

  return { state, start, reset };
}
