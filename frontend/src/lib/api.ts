const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Conut-Caller": "frontend",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function recommendCombos(body: {
  branch?: string;
  top_n: number;
  min_support: number;
}) {
  return postJson<Record<string, unknown>>("/tools/recommend_combos", body);
}

export function forecastDemand(body: {
  branch: string;
  horizon_days: number;
}) {
  return postJson<Record<string, unknown>>("/tools/forecast_demand", body);
}

export function estimateStaffing(body: {
  branch: string;
  target_period?: string;
  day_of_week?: "Mon" | "Tue" | "Wed" | "Thu" | "Fri" | "Sat" | "Sun";
  shift_name: "morning" | "afternoon" | "evening" | "night";
  shift_hours?: number;
  buffer_pct?: number;
  demand_override?: number;
}) {
  return postJson<Record<string, unknown>>("/tools/estimate_staffing", body);
}

export function expansionFeasibility(body: {
  candidate_location: string;
  target_region?: string;
}) {
  return postJson<Record<string, unknown>>("/tools/expansion_feasibility", body);
}

export function growthStrategy(body: {
  branch?: string;
  focus_categories: string[];
}) {
  return postJson<Record<string, unknown>>("/tools/growth_strategy", body);
}

export type ToolActivityEvent = {
  event_id: number;
  timestamp: string;
  tool_name: string;
  path: string;
  source: string;
  agent_tool?: string | null;
  payload: Record<string, unknown>;
  result_preview: Record<string, unknown>;
  raw_output: Record<string, unknown>;
};

export function fetchToolActivity(limit = 20) {
  return getJson<{ events: ToolActivityEvent[] }>(`/tools/activity?limit=${limit}`);
}

export type AgentChatResponse = {
  session_id: string;
  assistant_message: string;
  raw_gateway_response: Record<string, unknown>;
};

export function agentChat(body: { message: string; session_id?: string }) {
  return postJson<AgentChatResponse>("/agent/chat", body);
}
