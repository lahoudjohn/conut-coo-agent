import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Card } from "./components/ui/card";
import { agentChat, fetchToolActivity, ToolActivityEvent } from "./lib/api";

type ViewMode = "chat" | "dashboard";
type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const SESSION_STORAGE_KEY = "conut-openclaw-session-id";

function formatTimestamp(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    month: "short",
    day: "numeric",
  });
}

function buildInitialSessionId() {
  if (typeof window === "undefined") {
    return "";
  }

  const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) {
    return existing;
  }

  const generated = window.crypto?.randomUUID?.() || `session-${Date.now()}`;
  window.localStorage.setItem(SESSION_STORAGE_KEY, generated);
  return generated;
}

function normalizeAssistantText(content: string) {
  return content
    .replace(/(?<=\S)\s(?=\d+\.\s+\*\*)/g, "\n")
    .replace(/(?<=\S)\s(?=-\s+\*\*)/g, "\n")
    .replace(/\s{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function renderInlineFormatting(text: string) {
  const parts = text.split(/(\*\*.*?\*\*)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={`${part}-${index}`} className="font-semibold text-stone-900">
          {part.slice(2, -2)}
        </strong>
      );
    }

    return <span key={`${part}-${index}`}>{part}</span>;
  });
}

function renderMessageContent(content: string): ReactNode {
  const normalized = normalizeAssistantText(content);
  const lines = normalized
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\d+\.\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ol key={`ol-${blocks.length}`} className="list-decimal space-y-2 pl-5">
          {items.map((item, itemIndex) => (
            <li key={`ol-item-${itemIndex}`}>{renderInlineFormatting(item)}</li>
          ))}
        </ol>
      );
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^[-*]\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="list-disc space-y-2 pl-5">
          {items.map((item, itemIndex) => (
            <li key={`ul-item-${itemIndex}`}>{renderInlineFormatting(item)}</li>
          ))}
        </ul>
      );
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length && !/^\d+\.\s+/.test(lines[index]) && !/^[-*]\s+/.test(lines[index])) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    blocks.push(
      <p key={`p-${blocks.length}`} className="leading-7">
        {renderInlineFormatting(paragraphLines.join(" "))}
      </p>
    );
  }

  return <div className="space-y-3 text-[15px] text-stone-700">{blocks}</div>;
}

function ChatView() {
  const [sessionId, setSessionId] = useState<string>(() => buildInitialSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "I am connected to OpenClaw through your backend proxy. Ask an operational question and I will route it through the Conut tools when needed.",
    },
  ]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [loading, messages]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || loading) {
      return;
    }

    setLoading(true);
    setError(null);
    setMessages((current) => [...current, { role: "user", content: trimmed }]);
    setInput("");

    try {
      const response = await agentChat({ message: trimmed, session_id: sessionId || undefined });
      if (response.session_id !== sessionId) {
        setSessionId(response.session_id);
        window.localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
      }
      setMessages((current) => [
        ...current,
        { role: "assistant", content: response.assistant_message },
      ]);
    } catch (chatError) {
      const message =
        chatError instanceof Error ? chatError.message : "Failed to reach the OpenClaw proxy.";
      setError(message);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            "The OpenClaw proxy request failed. Check that `openclaw gateway run` is active and that the gateway HTTP endpoint is enabled.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleNewSession() {
    const fresh = window.crypto?.randomUUID?.() || `session-${Date.now()}`;
    window.localStorage.setItem(SESSION_STORAGE_KEY, fresh);
    setSessionId(fresh);
    setMessages([
      {
        role: "assistant",
        content:
          "New OpenClaw session started. Ask a Conut operations question to continue.",
      },
    ]);
    setError(null);
  }

  return (
    <div className="grid gap-4">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold">Agent Chat</h2>
            <p className="mt-2 max-w-3xl text-sm text-stone-600">
              This is a custom frontend chat client. Messages are sent to your FastAPI
              `/agent/chat` proxy, which forwards them to OpenClaw. OpenClaw then decides when to
              call the Conut tools.
            </p>
          </div>
          <button
            type="button"
            onClick={handleNewSession}
            className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700"
          >
            New Session
          </button>
        </div>
        <p className="mt-3 text-xs text-stone-500">Session ID: {sessionId || "pending"}</p>
      </Card>

      {error ? (
        <Card>
          <p className="text-sm text-rose-700">{error}</p>
        </Card>
      ) : null}

      <Card className="p-0">
        <div className="flex h-[68vh] flex-col">
          <div className="flex-1 space-y-5 overflow-auto bg-gradient-to-b from-stone-50 to-white p-5">
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-3xl rounded-2xl px-4 py-3 shadow-sm ${
                    message.role === "user"
                      ? "bg-stone-900 text-white"
                      : "border border-stone-200 bg-white text-stone-800"
                  }`}
                >
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] opacity-70">
                    {message.role === "user" ? "You" : "Conut Agent"}
                  </div>
                  {message.role === "user" ? (
                    <div className="text-sm leading-7 whitespace-pre-wrap">{message.content}</div>
                  ) : (
                    renderMessageContent(message.content)
                  )}
                </div>
              </div>
            ))}

            {loading ? (
              <div className="flex justify-start">
                <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-600 shadow-sm">
                  Thinking and checking tools...
                </div>
              </div>
            ) : null}
            <div ref={messagesEndRef} />
          </div>

          <form
            onSubmit={handleSubmit}
            className="border-t border-stone-200 p-4"
          >
            <div className="flex gap-3">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask a Conut operations question..."
                className="flex-1 rounded-md border border-stone-300 bg-white px-4 py-3 text-sm"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="rounded-md bg-stone-900 px-5 py-3 text-sm font-medium text-white disabled:opacity-60"
              >
                Send
              </button>
            </div>
          </form>
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold">Suggested Prompts</h3>
        <div className="mt-4 grid gap-3">
          {[
            "What are the top 5 product combos to promote?",
            "Forecast demand for Conut Jnah for the next 7 days.",
            "Is North District a good candidate for a new branch in Beirut?",
            "How many staff do we need at Main Street Coffee for the evening shift in 2025-12?",
            "How can we increase coffee and milkshake sales across all branches?",
          ].map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => setInput(prompt)}
              className="rounded-md border border-stone-200 bg-stone-50 px-3 py-2 text-left text-sm text-stone-700"
            >
              {prompt}
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}

function DashboardView({
  events,
  error,
}: {
  events: ToolActivityEvent[];
  error: string | null;
}) {
  return (
    <div className="grid gap-4">
      <Card>
        <h2 className="text-2xl font-semibold">Agent Tool Dashboard</h2>
        <p className="mt-2 text-sm text-stone-600">
          Tracks the last 5 OpenClaw-triggered tool calls, including the backend tool used and
          the raw JSON response returned to the agent.
        </p>
      </Card>

      {error ? (
        <Card>
          <p className="text-sm text-rose-700">{error}</p>
        </Card>
      ) : null}

      {events.length === 0 && !error ? (
        <Card>
          <p className="text-sm text-stone-500">
            No OpenClaw tool activity yet. Ask a question in the Chat page first.
          </p>
        </Card>
      ) : null}

      {events.map((event) => (
        <Card key={event.event_id}>
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-lg font-semibold">{event.agent_tool || event.tool_name}</p>
              <p className="text-sm text-stone-500">
                Backend tool: {event.tool_name} at {event.path}
              </p>
            </div>
            <div className="text-right text-xs text-stone-500">
              <div className="rounded-full bg-emerald-100 px-2 py-1 font-semibold uppercase tracking-wide text-emerald-700">
                {event.source}
              </div>
              <p className="mt-2">{formatTimestamp(event.timestamp)}</p>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <section>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
                Tool Input
              </p>
              <pre className="max-h-72 overflow-auto rounded-md bg-stone-950 p-3 text-xs text-stone-100">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </section>

            <section>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
                Raw Output Returned To OpenClaw
              </p>
              <pre className="max-h-72 overflow-auto rounded-md bg-stone-950 p-3 text-xs text-stone-100">
                {JSON.stringify(event.raw_output, null, 2)}
              </pre>
            </section>
          </div>
        </Card>
      ))}
    </div>
  );
}

export default function App() {
  const [view, setView] = useState<ViewMode>("chat");
  const [events, setEvents] = useState<ToolActivityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadActivity() {
      try {
        const response = await fetchToolActivity(20);
        if (!mounted) {
          return;
        }
        setEvents(response.events);
        setError(null);
      } catch (fetchError) {
        if (!mounted) {
          return;
        }
        setError(
          fetchError instanceof Error ? fetchError.message : "Failed to load agent tool activity."
        );
      }
    }

    void loadActivity();
    const intervalId = window.setInterval(() => {
      void loadActivity();
    }, 2500);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const recentAgentEvents = useMemo(
    () => events.filter((event) => event.source === "openclaw").slice(0, 5),
    [events]
  );

  return (
    <div className="min-h-screen bg-stone-100 text-stone-900">
      <div className="border-b border-stone-300 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div>
            <h1 className="text-2xl font-semibold">Conut COO Agent Console</h1>
            <p className="mt-1 text-sm text-stone-600">
              Custom chat UI powered by OpenClaw, with a live tool audit trail.
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-lg border border-stone-300 bg-stone-50 p-1">
            <button
              type="button"
              onClick={() => setView("chat")}
              className={`rounded-md px-4 py-2 text-sm font-medium ${
                view === "chat" ? "bg-stone-900 text-white" : "text-stone-700"
              }`}
            >
              Chat
            </button>
            <button
              type="button"
              onClick={() => setView("dashboard")}
              className={`rounded-md px-4 py-2 text-sm font-medium ${
                view === "dashboard" ? "bg-stone-900 text-white" : "text-stone-700"
              }`}
            >
              Dashboard
            </button>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-7xl px-6 py-6">
        {view === "chat" ? (
          <ChatView />
        ) : (
          <DashboardView events={recentAgentEvents} error={error} />
        )}
      </main>
    </div>
  );
}
