const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function postJson<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  shift: "morning" | "afternoon" | "evening" | "night";
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
