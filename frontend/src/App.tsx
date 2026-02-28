import { useState } from "react";
import { ToolCard } from "./components/ToolCard";
import {
  estimateStaffing,
  expansionFeasibility,
  forecastDemand,
  growthStrategy,
  recommendCombos,
} from "./lib/api";

type JsonValue = Record<string, unknown> | null;

export default function App() {
  const [comboResult, setComboResult] = useState<JsonValue>(null);
  const [forecastResult, setForecastResult] = useState<JsonValue>(null);
  const [staffingResult, setStaffingResult] = useState<JsonValue>(null);
  const [expansionResult, setExpansionResult] = useState<JsonValue>(null);
  const [strategyResult, setStrategyResult] = useState<JsonValue>(null);

  return (
    <div className="min-h-screen bg-stone-100 text-stone-900">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[240px_1fr]">
        <aside className="border-r border-stone-300 bg-white p-6">
          <h1 className="text-xl font-semibold">Conut COO Agent</h1>
          <p className="mt-2 text-sm text-stone-600">OpenClaw-ready business tools.</p>
          <nav className="mt-6 space-y-2 text-sm">
            <div className="rounded-md bg-stone-900 px-3 py-2 text-white">Tools</div>
            <div className="rounded-md px-3 py-2">Combo Optimization</div>
            <div className="rounded-md px-3 py-2">Demand Forecasting</div>
            <div className="rounded-md px-3 py-2">Staffing Estimation</div>
            <div className="rounded-md px-3 py-2">Expansion Feasibility</div>
            <div className="rounded-md px-3 py-2">Growth Strategy</div>
          </nav>
        </aside>

        <main className="p-6">
          <div className="grid gap-4 xl:grid-cols-2">
            <ToolCard
              title="Combo Optimization"
              description="Recommend high-support product bundles."
              fields={[
                { key: "branch", label: "Branch", defaultValue: "" },
                { key: "top_n", label: "Top N", defaultValue: "5" },
              ]}
              onSubmit={async (values) =>
                setComboResult(
                  await recommendCombos({
                    branch: values.branch || undefined,
                    top_n: Number(values.top_n || 5),
                    min_support: 0.02,
                  })
                )
              }
              result={comboResult}
            />

            <ToolCard
              title="Demand Forecasting"
              description="Forecast branch demand for the next N days."
              fields={[
                { key: "branch", label: "Branch", defaultValue: "demo-branch" },
                { key: "horizon_days", label: "Horizon Days", defaultValue: "7" },
              ]}
              onSubmit={async (values) =>
                setForecastResult(
                  await forecastDemand({
                    branch: values.branch,
                    horizon_days: Number(values.horizon_days || 7),
                  })
                )
              }
              result={forecastResult}
            />

            <ToolCard
              title="Shift Staffing"
              description="Estimate required employees per shift."
              fields={[
                { key: "branch", label: "Branch", defaultValue: "demo-branch" },
                { key: "shift", label: "Shift", defaultValue: "evening" },
              ]}
              onSubmit={async (values) =>
                setStaffingResult(
                  await estimateStaffing({
                    branch: values.branch,
                    shift: values.shift as "morning" | "afternoon" | "evening" | "night",
                  })
                )
              }
              result={staffingResult}
            />

            <ToolCard
              title="Expansion Feasibility"
              description="Score a candidate location against internal benchmarks."
              fields={[
                { key: "candidate_location", label: "Candidate Location", defaultValue: "North District" },
                { key: "target_region", label: "Target Region", defaultValue: "" },
              ]}
              onSubmit={async (values) =>
                setExpansionResult(
                  await expansionFeasibility({
                    candidate_location: values.candidate_location,
                    target_region: values.target_region || undefined,
                  })
                )
              }
              result={expansionResult}
            />

            <div className="xl:col-span-2">
              <ToolCard
                title="Coffee + Milkshake Growth Strategy"
                description="Generate category-focused action recommendations."
                fields={[
                  { key: "branch", label: "Branch", defaultValue: "" },
                  { key: "focus_categories", label: "Categories (comma-separated)", defaultValue: "coffee,milkshake" },
                ]}
                onSubmit={async (values) =>
                  setStrategyResult(
                    await growthStrategy({
                      branch: values.branch || undefined,
                      focus_categories: values.focus_categories
                        .split(",")
                        .map((v) => v.trim())
                        .filter(Boolean),
                    })
                  )
                }
                result={strategyResult}
              />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
