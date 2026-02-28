import { ToolActivityEvent } from "../lib/api";
import { Card } from "./ui/card";

function formatTimestamp(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function ActivityPanel({
  events,
  error,
}: {
  events: ToolActivityEvent[];
  error: string | null;
}) {
  return (
    <div className="grid gap-4">
      <Card className="sticky top-6">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Live Tool Activity</h2>
            <p className="text-sm text-stone-600">
              Tracks backend tool calls from OpenClaw and the frontend.
            </p>
          </div>
          <span className="rounded-full bg-stone-900 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-white">
            {events.length} recent
          </span>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {error}
          </div>
        )}

        <div className="grid gap-3">
          {events.length === 0 && !error ? (
            <div className="rounded-md border border-dashed border-stone-300 px-3 py-4 text-sm text-stone-500">
              No tool activity yet. Run a card or ask OpenClaw a question.
            </div>
          ) : null}

          {events.map((event) => (
            <article
              key={event.event_id}
              className="rounded-lg border border-stone-200 bg-stone-50 p-3"
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold">{event.tool_name}</p>
                  <p className="truncate text-[11px] text-stone-500">{event.path}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                      event.source === "openclaw"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-sky-100 text-sky-700"
                    }`}
                  >
                    {event.source}
                  </span>
                  <span className="text-[10px] text-stone-500">
                    {formatTimestamp(event.timestamp)}
                  </span>
                </div>
              </div>

              {event.agent_tool ? (
                <p className="mb-2 text-[11px] text-stone-600">
                  Agent tool: <span className="font-medium">{event.agent_tool}</span>
                </p>
              ) : null}

              <div className="grid gap-2">
                <div>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-stone-500">
                    Payload
                  </p>
                  <pre className="max-h-24 overflow-auto rounded-md bg-white p-2 text-[11px] text-stone-700">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                </div>
                <div>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-stone-500">
                    Result Preview
                  </p>
                  <pre className="max-h-24 overflow-auto rounded-md bg-white p-2 text-[11px] text-stone-700">
                    {JSON.stringify(event.result_preview, null, 2)}
                  </pre>
                </div>
              </div>
            </article>
          ))}
        </div>
      </Card>
    </div>
  );
}
