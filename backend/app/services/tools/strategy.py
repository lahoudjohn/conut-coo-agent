from __future__ import annotations

from app.schemas.tools import ComboRequest, GrowthStrategyRequest, ToolResponse
from app.services.features import category_keyword_share
from app.services.tools.combo import recommend_combos


def build_growth_strategy(payload: GrowthStrategyRequest) -> ToolResponse:
    category_df, ctx = category_keyword_share(payload.focus_categories)

    if category_df.empty:
        return ToolResponse(
            tool_name="growth_strategy",
            result={
                "focus_categories": payload.focus_categories,
                "recommendations": [
                    "Bundle coffee with breakfast pastry during morning hours.",
                    "Promote milkshake add-ons with dessert-heavy baskets.",
                    "Feature low-friction upsell prompts in POS and delivery menus.",
                ],
                "placeholder": True,
            },
            key_evidence_metrics={"category_lines_analyzed": 0},
            assumptions=[
                "No category-level data found; recommendations are rule-based placeholders.",
            ],
            data_coverage_notes=ctx.coverage_notes,
        )

    total_revenue = float(category_df["revenue_proxy"].sum()) or 1.0
    category_df["revenue_share"] = category_df["revenue_proxy"] / total_revenue
    weakest = category_df.sort_values("revenue_share").head(1).iloc[0]

    combo_response = recommend_combos(ComboRequest(branch=payload.branch, top_n=3, min_support=0.01))
    recommendations = [
        f"Protect and scale {row['category']} where share is {row['revenue_share']:.1%} of tracked focus-category revenue."
        for _, row in category_df.iterrows()
    ]
    recommendations.append(
        f"Primary whitespace: {weakest['category']} under-indexes in the tracked mix; use meal bundles and homepage placement."
    )
    if combo_response.result.get("combos"):
        top_combo = combo_response.result["combos"][0]
        recommendations.append(
            f"Test attach offer built around {', '.join(top_combo['items'])} to lift beverage add-ons."
        )

    return ToolResponse(
        tool_name="growth_strategy",
        result={
            "branch": payload.branch or "all",
            "focus_categories": payload.focus_categories,
            "category_metrics": category_df.to_dict(orient="records"),
            "recommendations": recommendations,
        },
        key_evidence_metrics={
            "category_lines_analyzed": int(category_df["lines"].sum()),
            "categories_tracked": int(len(category_df)),
        },
        assumptions=[
            "Category detection is keyword-based and depends on item naming conventions.",
            "This is intended as a decision-support heuristic, not a marketing attribution model.",
        ],
        data_coverage_notes=ctx.coverage_notes,
    )
