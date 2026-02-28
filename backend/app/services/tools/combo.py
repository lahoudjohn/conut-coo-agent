from __future__ import annotations

from collections import Counter
from itertools import combinations

from app.schemas.tools import ComboRequest, ToolResponse
from app.services.features import build_transaction_frame


def recommend_combos(payload: ComboRequest) -> ToolResponse:
    ctx = build_transaction_frame()
    df = ctx.raw.copy()

    if payload.branch:
        df = df[df["branch_name"].astype(str).str.lower() == payload.branch.lower()]

    if df.empty:
        return ToolResponse(
            tool_name="recommend_combos",
            result={
                "combos": [
                    {"items": ["coffee", "croissant"], "support": 0.18, "estimated_value_lift": 0.12, "placeholder": True},
                    {"items": ["milkshake", "waffle"], "support": 0.11, "estimated_value_lift": 0.09, "placeholder": True},
                ]
            },
            key_evidence_metrics={"orders_analyzed": 0, "candidate_pairs": 0},
            assumptions=[
                "No cleaned transactional data was available, so placeholder demo combos are returned.",
                "Support is based on order-level co-occurrence share.",
            ],
            data_coverage_notes=ctx.coverage_notes,
        )

    baskets = (
        df.groupby("order_id")["item_name"]
        .apply(lambda s: sorted(set(str(v).strip() for v in s if str(v).strip())))
        .tolist()
    )
    pair_counter: Counter[tuple[str, str]] = Counter()
    for basket in baskets:
        if len(basket) < 2:
            continue
        for pair in combinations(basket, 2):
            pair_counter[pair] += 1

    total_orders = max(len(baskets), 1)
    combos = []
    for pair, count in pair_counter.most_common():
        support = count / total_orders
        if support < payload.min_support:
            continue
        combos.append(
            {
                "items": list(pair),
                "support": round(support, 4),
                "order_count": count,
                "estimated_value_lift": round(min(0.25, support * 0.75), 4),
            }
        )
        if len(combos) >= payload.top_n:
            break

    return ToolResponse(
        tool_name="recommend_combos",
        result={"combos": combos},
        key_evidence_metrics={
            "orders_analyzed": total_orders,
            "candidate_pairs": len(pair_counter),
            "branch_filtered": payload.branch or "all",
        },
        assumptions=[
            "Pairs are ranked by co-occurrence support, not by causal uplift.",
            "Scaled data preserves relative patterns but not absolute revenue values.",
        ],
        data_coverage_notes=ctx.coverage_notes,
    )
