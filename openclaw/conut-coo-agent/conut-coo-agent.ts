const USER_API_URL = process.env.CONUT_API_URL;
const DEFAULT_API_URL = (USER_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const DEFAULT_TIMEOUT_MS = Number(process.env.CONUT_API_TIMEOUT_MS || 20000);
const OPTIONAL_AUTH_TOKEN = process.env.CONUT_API_TOKEN;

const TOOL_SPECS = [
  {
    name: "conut_combo_optimization",
    path: "/tools/recommend_combos",
    description:
      "Objective 1: Combo optimization. Finds high-value product combinations and association rules from historical baskets.",
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        mode: {
          type: "string",
          enum: ["top_combos", "with_item", "branch_pairs"],
          default: "top_combos",
        },
        branch: { type: "string" },
        anchor_item: { type: "string" },
        include_categories: {
          type: "array",
          items: { type: "string", enum: ["beverage", "sweet", "savory", "other"] },
          default: [],
        },
        exclude_items: {
          type: "array",
          items: { type: "string" },
          default: [],
        },
        top_n: { type: "integer", minimum: 1, maximum: 20, default: 5 },
        min_support: { type: "number", minimum: 0, maximum: 1, default: 0.02 },
        min_confidence: { type: "number", minimum: 0, maximum: 1, default: 0.3 },
        min_lift: { type: "number", minimum: 0, default: 1.0 },
      },
    },
  },
  {
    name: "conut_demand_forecast",
    path: "/tools/forecast_demand",
    description:
      "Objective 2: Demand forecasting by branch. Forecasts branch demand for a requested horizon.",
    parameters: {
      type: "object",
      additionalProperties: false,
      required: ["branch"],
      properties: {
        branch: { type: "string" },
        horizon_days: { type: "integer", minimum: 1, maximum: 31, default: 7 },
      },
    },
  },
  {
    name: "conut_expansion_feasibility",
    path: "/tools/expansion_feasibility",
    description:
      "Objective 3: Expansion feasibility. Scores a candidate location using internal branch benchmarks.",
    parameters: {
      type: "object",
      additionalProperties: false,
      required: ["candidate_location"],
      properties: {
        candidate_location: { type: "string" },
        target_region: { type: "string" },
      },
    },
  },
  {
    name: "conut_shift_staffing",
    path: "/tools/estimate_staffing",
    description:
      "Objective 4: Shift staffing estimation. Estimates required employees per shift using demand and attendance timing data.",
    parameters: {
      type: "object",
      additionalProperties: false,
      required: ["branch", "shift_name"],
      properties: {
        branch: { type: "string" },
        target_period: { type: "string", pattern: "^\\d{4}-\\d{2}$" },
        day_of_week: {
          type: "string",
          enum: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        },
        shift_name: {
          type: "string",
          enum: ["morning", "afternoon", "evening", "night"],
        },
        shift_hours: { type: "number", minimum: 0.1, maximum: 24, default: 8.0 },
        buffer_pct: { type: "number", minimum: 0, maximum: 1, default: 0.15 },
        demand_override: { type: "number", minimum: 0 },
      },
    },
  },
  {
    name: "conut_growth_strategy",
    path: "/tools/growth_strategy",
    description:
      "Objective 5: Coffee and milkshake growth strategy. Returns category metrics and recommended actions.",
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        branch: { type: "string" },
        focus_categories: {
          type: "array",
          items: { type: "string" },
          default: ["coffee", "milkshake"],
        },
      },
    },
  },
];

function buildApiUrlCandidates() {
  const candidates = [];
  const defaults = [
    DEFAULT_API_URL,
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://host.docker.internal:8000",
  ];

  for (const value of defaults) {
    const normalized = value.replace(/\/+$/, "");
    if (!candidates.includes(normalized)) {
      candidates.push(normalized);
    }
  }

  return candidates;
}

async function callBackend(agentTool, path, payload) {
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  const attemptedUrls = [];
  let lastError = null;

  try {
    const headers = {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Conut-Caller": "openclaw",
      "X-Conut-Agent-Tool": agentTool,
    };

    if (OPTIONAL_AUTH_TOKEN) {
      headers.Authorization = `Bearer ${OPTIONAL_AUTH_TOKEN}`;
    }

    for (const baseUrl of buildApiUrlCandidates()) {
      const requestUrl = `${baseUrl}${path}`;
      attemptedUrls.push(requestUrl);

      try {
        const response = await fetch(requestUrl, {
          method: "POST",
          headers,
          body: JSON.stringify(payload || {}),
          signal: controller.signal,
        });

        const rawText = await response.text();
        let data;

        try {
          data = rawText ? JSON.parse(rawText) : {};
        } catch {
          data = { raw: rawText };
        }

        if (!response.ok) {
          throw new Error(
            `Conut backend request failed (${response.status}) for ${requestUrl}: ${JSON.stringify(data)}`
          );
        }

        return data;
      } catch (error) {
        lastError = error;
      }
    }

    throw new Error(
      `Unable to reach Conut backend after trying ${attemptedUrls.join(", ")}. Last error: ${
        lastError instanceof Error ? lastError.message : String(lastError)
      }`
    );
  } finally {
    clearTimeout(timeoutHandle);
  }
}

function formatToolOutput(toolName, payload) {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(
          {
            tool: toolName,
            source: "conut-coo-agent",
            payload,
          },
          null,
          2
        ),
      },
    ],
  };
}

export default function registerConutCooAgentTools(api) {
  for (const tool of TOOL_SPECS) {
    api.registerTool({
      name: tool.name,
      description: tool.description,
      parameters: tool.parameters,
      async execute(_id, input) {
        const payload = await callBackend(tool.name, tool.path, input);
        return formatToolOutput(tool.name, payload);
      },
    });
  }
}
