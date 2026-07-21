"use client";

/**
 * The Concierge (SAAS_DESIGN §6): sidebar + conversation. Borrows the desk's
 * visual register. Refusal bubbles get a distinct, quiet treatment — a
 * hold-toned border (a boundary, not an error) AND self-describing text, so
 * the distinction survives any theme, screenshot, or screen reader.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthToken } from "@/components/AuthTokenBridge";
import { authHeaders, PUBLIC_API_URL } from "@/lib/api";

interface Conversation {
  id: string;
  title: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  refusal?: boolean;
  linkedReportId?: string | null;
  pending?: boolean;
}

const PROMPT_CHIPS = [
  "What's NVDA's risk profile?",
  "Summarize my last report",
  "Research AMD",
  "What is a PEG ratio?",
];

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const getToken = useAuthToken();
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const apiFetch = useCallback(
    async (path: string, init?: RequestInit) => {
      const token = await getToken();
      return fetch(`${PUBLIC_API_URL}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(token),
          ...(init?.headers ?? {}),
        },
      });
    },
    [getToken],
  );

  useEffect(() => {
    apiFetch("/api/conversations")
      .then((r) => r.json())
      .then((data) => setConversations(data.conversations ?? []))
      .catch(() => setError("Could not load conversations."));
  }, [apiFetch]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function openConversation(id: string) {
    setActiveId(id);
    setMessages([]);
    setError(null);
    const res = await apiFetch(`/api/conversations/${id}/messages`);
    if (!res.ok) {
      setError("Could not load this conversation.");
      return;
    }
    const data = await res.json();
    setMessages(
      data.messages.map((m: { role: string; content: string; linked_report_id: string | null }) => ({
        role: m.role === "user" ? "user" : "assistant",
        content: m.content,
        linkedReportId: m.linked_report_id,
      })),
    );
  }

  async function newConversation(): Promise<string | null> {
    const res = await apiFetch("/api/conversations", { method: "POST" });
    if (!res.ok) {
      setError("Could not start a conversation.");
      return null;
    }
    const conv = await res.json();
    setConversations((prev) => [{ id: conv.id, title: conv.title }, ...prev]);
    setActiveId(conv.id);
    setMessages([]);
    return conv.id;
  }

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy) return;
    setBusy(true);
    setError(null);
    setDraft("");

    let conversationId = activeId;
    if (!conversationId) {
      conversationId = await newConversation();
      if (!conversationId) {
        setBusy(false);
        return;
      }
    }

    setMessages((prev) => [
      ...prev,
      { role: "user", content },
      { role: "assistant", content: "", pending: true },
    ]);

    try {
      const res = await apiFetch(`/api/conversations/${conversationId}/messages/stream`, {
        method: "POST",
        body: JSON.stringify({ content }),
      });
      if (!res.ok || !res.body) throw new Error(`Concierge unavailable (${res.status})`);

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
              handleEvent(JSON.parse(raw));
            } catch {
              // tolerate malformed frames
            }
          }
        }
      }
    } catch (err) {
      setMessages((prev) => prev.filter((m) => !m.pending));
      setError(err instanceof Error ? err.message : "The Concierge is unavailable.");
    } finally {
      setBusy(false);
      setConversations((prev) =>
        prev.map((c) =>
          c.id === conversationId && c.title === "New conversation"
            ? { ...c, title: content.slice(0, 60) }
            : c,
        ),
      );
    }
  }

  function handleEvent(event: {
    type: string;
    content?: string;
    message?: string;
    linked_report_id?: string | null;
  }) {
    if (event.type === "refusal") {
      replacePending({ role: "assistant", content: event.content ?? "", refusal: true });
    } else if (event.type === "message") {
      replacePending({
        role: "assistant",
        content: event.content ?? "",
        linkedReportId: event.linked_report_id,
      });
    } else if (event.type === "error") {
      replacePending({ role: "assistant", content: event.message ?? "Something went wrong." });
    }
    // "thinking" keeps the pending bubble as-is.
  }

  function replacePending(message: ChatMessage) {
    setMessages((prev) => {
      const next = prev.filter((m) => !m.pending);
      return [...next, message];
    });
  }

  const empty = messages.length === 0;

  return (
    <div className="grid min-h-[70vh] gap-6 lg:grid-cols-[260px_1fr]">
      {/* ---- Sidebar ---- */}
      <aside className="rounded-xl border border-border bg-surface p-4">
        <button
          onClick={newConversation}
          className="w-full rounded-lg border border-border bg-bg px-4 py-2 font-mono text-sm uppercase tracking-widest text-text transition-colors hover:border-brand"
        >
          + New chat
        </button>
        <ul className="mt-4 space-y-1">
          {conversations.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => openConversation(c.id)}
                className={`w-full truncate rounded-md px-3 py-2 text-left text-[14px] transition-colors ${
                  c.id === activeId
                    ? "bg-brand/10 text-text"
                    : "text-text-muted hover:bg-surface-hover hover:text-text"
                }`}
              >
                {c.title}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      {/* ---- Conversation ---- */}
      <section className="flex flex-col rounded-xl border border-border bg-surface">
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {empty ? (
            <div className="flex h-full flex-col items-center justify-center gap-6 py-16">
              <p className="text-xl text-text-muted">
                Ask about your research, or start new research.
              </p>
              <div className="flex max-w-lg flex-wrap justify-center gap-2.5">
                {PROMPT_CHIPS.map((chip) => (
                  <button
                    key={chip}
                    onClick={() => send(chip)}
                    className="rounded-full border border-border bg-bg px-4 py-1.5 text-[14px] text-text-muted transition-colors hover:border-brand hover:text-text"
                  >
                    {chip}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[80%] rounded-xl bg-brand/10 px-4 py-3 text-[15px] leading-relaxed text-text">
                    {m.content}
                  </div>
                </div>
              ) : (
                <div key={i} className="flex justify-start">
                  <div
                    className={`max-w-[85%] rounded-xl px-4 py-3 text-[15px] leading-relaxed text-text ${
                      m.refusal
                        ? "border-l-4 border-hold bg-hold/5"
                        : "border border-border bg-bg"
                    }`}
                  >
                    {m.pending ? (
                      <span className="font-mono text-[13px] uppercase tracking-widest text-text-muted">
                        working…
                      </span>
                    ) : (
                      <>
                        <p className="whitespace-pre-wrap">{m.content}</p>
                        {m.linkedReportId && (
                          <Link
                            href={`/reports/${m.linkedReportId}`}
                            className="mt-3 block rounded-lg border border-border bg-surface px-4 py-2.5 font-mono text-[13px] uppercase tracking-widest text-brand transition-colors hover:border-brand"
                          >
                            Open full dossier →
                          </Link>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ),
            )
          )}
          <div ref={bottomRef} />
        </div>

        {error && (
          <p role="alert" className="border-t border-border px-6 py-3 text-[14px] text-bear">
            {error}
          </p>
        )}

        {/* ---- Composer ---- */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(draft);
          }}
          className="flex gap-3 border-t border-border p-4"
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask a follow-up, or research a new ticker…"
            disabled={busy}
            className="flex-1 rounded-lg border border-border bg-bg px-4 py-2.5 text-[15px] text-text placeholder:text-text-faint focus:border-brand focus:outline-none"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="rounded-lg bg-brand px-5 py-2.5 font-mono text-sm font-medium uppercase tracking-widest text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
          >
            Send
          </button>
        </form>

        {/* Always-visible boundary (SAAS_DESIGN §6). */}
        <p className="border-t border-border px-6 py-2.5 text-[13px] text-text-muted">
          FinSightAI shares research, not personalized investment advice.
        </p>
      </section>
    </div>
  );
}
