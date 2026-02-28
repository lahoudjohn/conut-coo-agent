import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Card } from "./components/ui/card";
import { agentChat, fetchToolActivity, ToolActivityEvent } from "./lib/api";

type ViewMode = "chat" | "dashboard";
type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
};

const SESSION_STORAGE_KEY = "conut-openclaw-session-id";
const TOOL_ACTIVITY_STORAGE_KEY = "conut-openclaw-tool-activity";

const PROMPTS = [
  "What are the top 5 product combos to promote?",
  "Forecast demand for Conut Jnah for the next 7 days.",
  "Is North District a good candidate for a new branch in Beirut?",
  "How many staff do we need at Main Street Coffee for the evening shift in 2025-12?",
  "How can we increase coffee and milkshake sales across all branches?",
];

const STORY_CHIPS = [
  { label: "Centro Mall", sublabel: "10:00 AM to 10:00 PM" },
  { label: "Batroun", sublabel: "7:30 AM to 12:00 AM" },
  { label: "Tyre", sublabel: "3:00 PM to 3:00 AM" },
  { label: "Coffee", sublabel: "Signature uplift" },
  { label: "Milkshakes", sublabel: "Attach-rate watch" },
];

const OBJECTIVE_PILLS = [
  "Combo Optimization",
  "Demand Forecasting",
  "Expansion Feasibility",
  "Shift Staffing",
  "Growth Strategy",
];

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

function buildDefaultMessages(): ChatMessage[] {
  return [
    {
      role: "assistant",
      content:
        "Welcome to COOnut. I am connected to OpenClaw through your backend proxy. Ask an operational question and I will route it through the right Conut tool when needed.",
      timestamp: new Date().toISOString(),
    },
  ];
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

function buildInitialEvents() {
  if (typeof window === "undefined") {
    return [] as ToolActivityEvent[];
  }

  const raw = window.localStorage.getItem(TOOL_ACTIVITY_STORAGE_KEY);
  if (!raw) {
    return [] as ToolActivityEvent[];
  }

  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed as ToolActivityEvent[];
    }
  } catch {
    // Ignore malformed cache.
  }

  return [] as ToolActivityEvent[];
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
        <strong key={`${part}-${index}`} className="font-semibold text-stone-950">
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

function resolveUserPromptForEvent(eventTimestamp: string, messages: ChatMessage[]) {
  const userMessages = messages.filter((message) => message.role === "user");
  if (!userMessages.length) {
    return "No matching user prompt recorded yet.";
  }

  const eventTime = new Date(eventTimestamp).getTime();
  let match = userMessages[userMessages.length - 1];

  for (const message of userMessages) {
    const messageTime = new Date(message.timestamp).getTime();
    if (Number.isNaN(eventTime) || Number.isNaN(messageTime)) {
      continue;
    }

    if (messageTime <= eventTime) {
      match = message;
      continue;
    }

    break;
  }

  return match.content;
}

function ShellHeader({
  activeView,
  onViewChange,
}: {
  activeView: ViewMode;
  onViewChange: (view: ViewMode) => void;
}) {
  return (
    <header className="sticky top-0 z-10 border-b border-white/10 bg-[rgba(5,7,12,0.85)] backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 md:px-8">
        <div className="flex items-center gap-4">
          <div className="grid h-12 w-12 place-items-center rounded-full border border-[rgba(215,187,125,0.30)] bg-gradient-to-br from-[#8b1f2d] via-[#ad2a39] to-[#63141d] shadow-[0_12px_24px_rgba(94,10,20,0.35)]">
            <div className="h-8 w-8 rounded-full border-2 border-[#fff7e1]">
              <div className="mx-auto mt-2 h-3.5 w-3.5 rounded-full bg-[#fff7e1]" />
            </div>
          </div>
          <div>
            <p className="font-['Georgia'] text-3xl font-semibold tracking-tight text-[#fff7e1]">
              COOnut
            </p>
            <p className="text-xs uppercase tracking-[0.28em] text-[#d7bb7d]">
              Conut operations cockpit
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 p-1">
          <button
            type="button"
            onClick={() => onViewChange("chat")}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              activeView === "chat"
                ? "bg-[#fff7e1] text-[#5a111a]"
                : "text-[rgba(244,236,221,0.80)] hover:text-white"
            }`}
          >
            Agent Lounge
          </button>
          <button
            type="button"
            onClick={() => onViewChange("dashboard")}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              activeView === "dashboard"
                ? "bg-[#fff7e1] text-[#5a111a]"
                : "text-[rgba(244,236,221,0.80)] hover:text-white"
            }`}
          >
            Control Room
          </button>
        </div>
      </div>
    </header>
  );
}

function BrandHero() {
  return (
    <Card className="relative overflow-hidden border-white/10 bg-[rgba(9,13,20,0.90)] p-0 shadow-[0_24px_80px_rgba(3,6,15,0.35)]">
      <div className="absolute inset-0">
        <div className="absolute inset-y-0 left-0 w-full bg-[radial-gradient(circle_at_top_left,_rgba(185,38,56,0.5),_transparent_42%),radial-gradient(circle_at_bottom_right,_rgba(214,187,125,0.18),_transparent_36%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(115deg,rgba(9,13,20,0.92)_25%,rgba(9,13,20,0.6)_55%,rgba(122,19,34,0.42)_100%)]" />
      </div>

      <div className="relative grid gap-8 px-6 py-8 md:px-8 xl:grid-cols-[1.2fr_0.8fr]">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-[rgba(215,187,125,0.30)] bg-[rgba(255,247,225,0.10)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-[#f6ddae]">
            Authentic Hungarian pastry intelligence
          </div>
          <h2 className="mt-4 max-w-3xl font-['Georgia'] text-4xl font-semibold leading-tight text-[#fff8eb] md:text-5xl">
            Built for Conut&apos;s pastry, coffee, and milkshake decisions across every branch.
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-[rgba(244,236,221,0.78)] md:text-base">
            COOnut turns Conut&apos;s operational data into immediate, explainable actions across
            combos, demand, staffing, expansion, and beverage growth. One chat, one control room,
            five decision engines.
          </p>

          <div className="mt-6 flex flex-wrap gap-2">
            {OBJECTIVE_PILLS.map((pill) => (
              <span
                key={pill}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#f5efe0]"
              >
                {pill}
              </span>
            ))}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1">
          <div className="rounded-[28px] border border-[rgba(215,187,125,0.25)] bg-[linear-gradient(160deg,rgba(141,24,39,0.95),rgba(92,17,26,0.92))] p-5 text-[#fff8eb] shadow-[0_16px_36px_rgba(74,8,18,0.34)]">
            <p className="text-xs uppercase tracking-[0.24em] text-[#f6ddae]">Live command mode</p>
            <div className="mt-4 grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="font-['Georgia'] text-3xl font-semibold">5</p>
                <p className="mt-1 text-[11px] uppercase tracking-[0.22em] text-[rgba(252,234,191,0.75)]">Tools</p>
              </div>
              <div>
                <p className="font-['Georgia'] text-3xl font-semibold">1</p>
                <p className="mt-1 text-[11px] uppercase tracking-[0.22em] text-[rgba(252,234,191,0.75)]">Agent</p>
              </div>
              <div>
                <p className="font-['Georgia'] text-3xl font-semibold">24/7</p>
                <p className="mt-1 text-[11px] uppercase tracking-[0.22em] text-[rgba(252,234,191,0.75)]">Ops lens</p>
              </div>
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-white/5 p-5 backdrop-blur-sm">
            <p className="text-xs uppercase tracking-[0.24em] text-[#d7bb7d]">Branch pulse</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              {STORY_CHIPS.map((story) => (
                <div
                  key={story.label}
                  className="rounded-2xl border border-white/8 bg-black/10 px-4 py-3"
                >
                  <p className="font-semibold text-[#fff8eb]">{story.label}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[rgba(243,234,213,0.65)]">
                    {story.sublabel}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

function ChatView({
  sessionId,
  messages,
  loading,
  error,
  onSend,
  onNewSession,
}: {
  sessionId: string;
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  onSend: (message: string) => Promise<void>;
  onNewSession: () => void;
}) {
  const [input, setInput] = useState("");
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

    setInput("");
    await onSend(trimmed);
  }

  return (
    <div className="grid gap-6">
      <BrandHero />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(290px,0.9fr)]">
        <Card className="overflow-hidden border-white/10 bg-[rgba(10,16,24,0.90)] p-0 shadow-[0_22px_80px_rgba(2,6,14,0.32)]">
          <div className="border-b border-white/10 px-5 py-4 md:px-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-[#d7bb7d]">Agent lounge</p>
                <h3 className="mt-1 font-['Georgia'] text-2xl font-semibold text-[#fff8eb]">
                  Executive chat
                </h3>
                <p className="mt-2 text-sm text-[rgba(244,236,221,0.70)]">
                  Ask in plain language. OpenClaw will route the question through the Conut toolset.
                </p>
              </div>
              <button
                type="button"
                onClick={onNewSession}
                className="rounded-full border border-[rgba(215,187,125,0.35)] bg-[rgba(255,247,225,0.08)] px-4 py-2 text-sm font-semibold text-[#fff1c9] transition hover:bg-[rgba(255,247,225,0.14)]"
              >
                New Session
              </button>
            </div>
            <p className="mt-3 text-[11px] uppercase tracking-[0.18em] text-[rgba(244,236,221,0.45)]">
              Session ID: {sessionId || "pending"}
            </p>
          </div>

          {error ? (
            <div className="border-b border-white/10 bg-[rgba(60,16,23,0.60)] px-6 py-3 text-sm text-[#ffd6da]">
              {error}
            </div>
          ) : null}

          <div className="flex h-[68vh] flex-col">
            <div className="flex-1 space-y-5 overflow-auto bg-[radial-gradient(circle_at_top_right,_rgba(179,38,55,0.18),_transparent_35%),linear-gradient(180deg,_rgba(8,11,18,0.94),_rgba(10,16,24,0.92))] p-5 md:p-6">
              {messages.map((message, index) => (
                <div
                  key={`${message.role}-${message.timestamp}-${index}`}
                  className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-3xl rounded-[26px] px-4 py-4 shadow-[0_8px_24px_rgba(0,0,0,0.18)] md:px-5 ${
                      message.role === "user"
                        ? "bg-[linear-gradient(135deg,#8b1f2d,#63141d)] text-[#fff8eb]"
                        : "border border-[rgba(215,187,125,0.18)] bg-[#fff8eb] text-stone-800"
                    }`}
                  >
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] opacity-70">
                      {message.role === "user" ? "Operator" : "COOnut agent"}
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
                  <div className="rounded-[24px] border border-[rgba(215,187,125,0.18)] bg-[#fff8eb] px-5 py-4 text-sm text-stone-600 shadow-[0_8px_24px_rgba(0,0,0,0.14)]">
                    Thinking, checking evidence, and selecting the right tool...
                  </div>
                </div>
              ) : null}
              <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSubmit} className="border-t border-white/10 bg-[#0a1018] p-4 md:p-5">
              <div className="flex flex-col gap-3 md:flex-row">
                <input
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ask a Conut operations question..."
                  className="min-h-[56px] flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-[#fff8eb] outline-none placeholder:text-[rgba(244,236,221,0.40)] focus:border-[rgba(215,187,125,0.45)]"
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="min-h-[56px] rounded-2xl bg-[linear-gradient(135deg,#fff1c9,#d7bb7d)] px-6 py-3 text-sm font-bold uppercase tracking-[0.16em] text-[#5a111a] transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-55"
                >
                  Send
                </button>
              </div>
            </form>
          </div>
        </Card>

        <div className="grid gap-6">
          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(19,26,38,0.96),rgba(10,16,24,0.92))] text-[#fff8eb] shadow-[0_20px_64px_rgba(3,6,15,0.28)]">
            <p className="text-xs uppercase tracking-[0.24em] text-[#d7bb7d]">Prompt starters</p>
            <h3 className="mt-2 font-['Georgia'] text-2xl font-semibold">Fast asks</h3>
            <div className="mt-5 grid gap-3">
              {PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setInput(prompt)}
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left text-sm leading-6 text-[#f6efdf] transition hover:border-[rgba(215,187,125,0.30)] hover:bg-white/10"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </Card>

          <Card className="overflow-hidden border-white/10 bg-[linear-gradient(160deg,rgba(117,18,32,0.94),rgba(71,11,18,0.96))] p-0 text-[#fff8eb] shadow-[0_22px_54px_rgba(67,8,18,0.28)]">
            <div className="border-b border-white/10 px-5 py-4">
              <p className="text-xs uppercase tracking-[0.24em] text-[#f6ddae]">Operational mode</p>
              <h3 className="mt-2 font-['Georgia'] text-2xl font-semibold">What COOnut can do</h3>
            </div>
            <div className="grid gap-4 px-5 py-5">
              <div className="rounded-2xl bg-black/10 px-4 py-4">
                <p className="text-sm font-semibold">Evidence-led answers</p>
                <p className="mt-1 text-sm text-[rgba(255,231,219,0.76)]">
                  Every response is grounded in backend tool outputs, not free-form guessing.
                </p>
              </div>
              <div className="rounded-2xl bg-black/10 px-4 py-4">
                <p className="text-sm font-semibold">Five operational objectives</p>
                <p className="mt-1 text-sm text-[rgba(255,231,219,0.76)]">
                  Combos, demand, expansion, staffing, and beverage growth are all one prompt away.
                </p>
              </div>
              <div className="rounded-2xl bg-black/10 px-4 py-4">
                <p className="text-sm font-semibold">OpenClaw orchestration</p>
                <p className="mt-1 text-sm text-[rgba(255,231,219,0.76)]">
                  The agent selects the correct tool and your dashboard records the full raw output.
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function DashboardView({
  events,
  error,
  messages,
}: {
  events: ToolActivityEvent[];
  error: string | null;
  messages: ChatMessage[];
}) {
  const uniqueTools = new Set(events.map((event) => event.agent_tool || event.tool_name)).size;
  const latestEvent = events[0];

  return (
    <div className="grid gap-6">
      <BrandHero />

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-white/10 bg-[linear-gradient(160deg,rgba(117,18,32,0.94),rgba(71,11,18,0.96))] text-[#fff8eb]">
          <p className="text-xs uppercase tracking-[0.24em] text-[#f6ddae]">Tracked calls</p>
          <p className="mt-3 font-['Georgia'] text-4xl font-semibold">{events.length}</p>
          <p className="mt-2 text-sm text-[rgba(255,231,219,0.72)]">Last five OpenClaw-triggered actions</p>
        </Card>
        <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(19,26,38,0.96),rgba(10,16,24,0.92))] text-[#fff8eb]">
          <p className="text-xs uppercase tracking-[0.24em] text-[#d7bb7d]">Distinct tools</p>
          <p className="mt-3 font-['Georgia'] text-4xl font-semibold">{uniqueTools}</p>
          <p className="mt-2 text-sm text-[rgba(246,239,223,0.72)]">How many objective tools were invoked</p>
        </Card>
        <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(19,26,38,0.96),rgba(10,16,24,0.92))] text-[#fff8eb]">
          <p className="text-xs uppercase tracking-[0.24em] text-[#d7bb7d]">Last event</p>
          <p className="mt-3 text-lg font-semibold">{latestEvent ? formatTimestamp(latestEvent.timestamp) : "No activity"}</p>
          <p className="mt-2 text-sm text-[rgba(246,239,223,0.72)]">
            {latestEvent ? latestEvent.agent_tool || latestEvent.tool_name : "Ask the agent a question first"}
          </p>
        </Card>
      </div>

      {error ? (
        <Card className="border-[#54212a] bg-[rgba(60,16,23,0.60)] text-[#ffd6da]">
          <p className="text-sm">{error}</p>
        </Card>
      ) : null}

      {events.length === 0 && !error ? (
        <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(19,26,38,0.96),rgba(10,16,24,0.92))] text-[#fff8eb]">
          <p className="text-sm text-[rgba(244,236,221,0.72)]">
            No OpenClaw tool activity yet. Ask a question in the Agent Lounge first.
          </p>
        </Card>
      ) : null}

      <div className="grid gap-5">
        {events.map((event, index) => (
          <Card
            key={event.event_id}
            className="overflow-hidden border-white/10 bg-[linear-gradient(180deg,rgba(19,26,38,0.96),rgba(10,16,24,0.92))] p-0 text-[#fff8eb] shadow-[0_20px_56px_rgba(3,6,15,0.22)]"
          >
            <div className="border-b border-white/10 px-5 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="rounded-full border border-[rgba(215,187,125,0.30)] bg-[rgba(255,247,225,0.08)] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#f6ddae]">
                      Event {index + 1}
                    </span>
                    <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#f6efdf]">
                      {event.source}
                    </span>
                  </div>
                  <p className="mt-3 font-['Georgia'] text-2xl font-semibold">
                    {event.agent_tool || event.tool_name}
                  </p>
                </div>
                <p className="text-xs uppercase tracking-[0.18em] text-[rgba(244,236,221,0.52)]">
                  {formatTimestamp(event.timestamp)}
                </p>
              </div>
            </div>

            <details className="group px-5 py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-semibold text-[#f6efdf] transition hover:border-[rgba(215,187,125,0.30)] hover:bg-white/10">
                <span>View user prompt and JSON</span>
                <span className="text-xs uppercase tracking-[0.18em] text-[#d7bb7d] group-open:hidden">
                  Expand
                </span>
                <span className="hidden text-xs uppercase tracking-[0.18em] text-[#d7bb7d] group-open:inline">
                  Collapse
                </span>
              </summary>

              <div className="mt-4 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
                <section className="rounded-3xl border border-white/10 bg-[rgba(255,255,255,0.04)] p-4">
                  <p className="mb-2 text-xs uppercase tracking-[0.22em] text-[#d7bb7d]">User prompt</p>
                  <p className="text-sm leading-7 text-[rgba(244,236,221,0.86)]">
                    {resolveUserPromptForEvent(event.timestamp, messages)}
                  </p>
                </section>

                <section>
                  <p className="mb-2 text-xs uppercase tracking-[0.22em] text-[#d7bb7d]">JSON output</p>
                  <pre className="max-h-72 overflow-auto rounded-3xl border border-white/10 bg-[#070b11] p-4 text-xs text-[#f4ecdd]">
                    {JSON.stringify(event.raw_output, null, 2)}
                  </pre>
                </section>
              </div>
            </details>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState<ViewMode>("chat");
  const [sessionId, setSessionId] = useState<string>(() => buildInitialSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>(() => buildDefaultMessages());
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [events, setEvents] = useState<ToolActivityEvent[]>(() => buildInitialEvents());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    window.localStorage.setItem(TOOL_ACTIVITY_STORAGE_KEY, JSON.stringify(events));
  }, [events]);

  async function handleChatSend(message: string) {
    if (chatLoading) {
      return;
    }

    setChatLoading(true);
    setChatError(null);
    setMessages((current) => [
      ...current,
      { role: "user", content: message, timestamp: new Date().toISOString() },
    ]);

    try {
      const response = await agentChat({ message, session_id: sessionId || undefined });
      if (response.session_id !== sessionId) {
        setSessionId(response.session_id);
        window.localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
      }
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.assistant_message,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (chatErrorValue) {
      const messageText =
        chatErrorValue instanceof Error ? chatErrorValue.message : "Failed to reach the OpenClaw proxy.";
      setChatError(messageText);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            "The OpenClaw proxy request failed. Check that `openclaw gateway run` is active, the OpenAI key is set, and the gateway chat-completions endpoint is enabled.",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  function handleNewSession() {
    const fresh = window.crypto?.randomUUID?.() || `session-${Date.now()}`;
    window.localStorage.setItem(SESSION_STORAGE_KEY, fresh);
    setSessionId(fresh);
    setMessages([
      {
        role: "assistant",
        content: "Fresh COOnut session started. Ask a new operational question to continue.",
        timestamp: new Date().toISOString(),
      },
    ]);
    setChatError(null);
  }

  useEffect(() => {
    let mounted = true;

    async function loadActivity() {
      try {
        const response = await fetchToolActivity(20);
        if (!mounted) {
          return;
        }
        setEvents((current) => (response.events.length > 0 ? response.events : current));
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
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(145,22,37,0.18),_transparent_28%),linear-gradient(180deg,#05070c_0%,#0b121a_42%,#101927_100%)] text-stone-900">
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute left-[8%] top-24 h-48 w-48 rounded-full bg-[rgba(122,19,34,0.18)] blur-3xl" />
        <div className="absolute bottom-12 right-[10%] h-60 w-60 rounded-full bg-[rgba(215,187,125,0.10)] blur-3xl" />
      </div>

      <ShellHeader activeView={view} onViewChange={setView} />

      <main className="mx-auto max-w-7xl px-4 py-6 md:px-8 md:py-8">
        {view === "chat" ? (
          <ChatView
            sessionId={sessionId}
            messages={messages}
            loading={chatLoading}
            error={chatError}
            onSend={handleChatSend}
            onNewSession={handleNewSession}
          />
        ) : (
          <DashboardView events={recentAgentEvents} error={error} messages={messages} />
        )}
      </main>
    </div>
  );
}
