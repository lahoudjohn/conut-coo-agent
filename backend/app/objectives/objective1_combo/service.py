from __future__ import annotations

from itertools import combinations

import pandas as pd

from app.core.config import settings
from app.schemas.tools import ComboRequest, ToolResponse


COMBO_SOURCE_CANDIDATES = [
    settings.processed_data_dir / "REP_S_00502_cleaned_updated.csv",
    settings.processed_data_dir / "REP_S_00502_cleaned.csv",
]
REQUIRED_COLUMNS = {
    "branch",
    "customer_name",
    "line_qty",
    "item_description",
    "line_amount",
    "customer_total_qty",
    "customer_total_amount",
}
OPTIONAL_ORDER_COLUMNS = {"order_id", "order_sequence"}

TRIVIAL_EXACT_ITEMS = {
    "DELIVERY CHARGE",
    "FULL FAT MILK",
    "PRESSED",
    "REGULAR",
    "HOT",
    "ICED",
    "WATER",
    "ADD ICE CREAM",
    "THE SHARING BOX",
    "CONUT COMBO",
}
TRIVIAL_KEYWORDS = (
    "SAUCE",
    "SPREAD",
    "TOPPING",
    "DRESSING",
    "WHIPPED CREAM",
    "NO ",
    "CHARGE",
    "(R)",
    " ON THE SIDE",
)

BEVERAGE_KEYWORDS = (
    "COFFEE",
    "LATTE",
    "MOCHA",
    "FRAPPE",
    "MILKSHAKE",
    "SHAKE",
    "TEA",
    "ESPRESSO",
    "CAPPUCCINO",
    "MACCHIATO",
    "MACHIATO",
)
SWEET_KEYWORDS = ("CONUT", "CHIMNEY", "WAFFLE", "BROWNIE", "CHEESECAKE", "ICE CREAM", "COOKIE", "CROISSANT")
SAVORY_KEYWORDS = ("SANDWICH", "SAVORY", "WRAP", "TOAST", "BAGEL", "HOT DOG", "PANINI")
FAMILY_MARKERS = (
    ("CONUT", "CONUT"),
    ("CHIMNEY", "CHIMNEY"),
    ("MILKSHAKE", "MILKSHAKE"),
    ("SHAKE", "MILKSHAKE"),
    ("FRAPPE", "FRAPPE"),
    ("COFFEE", "COFFEE"),
    ("WAFFLE", "WAFFLE"),
    ("MINI ", "MINI"),
    (" MINI", "MINI"),
)


def _load_combo_source() -> tuple[pd.DataFrame, str]:
    for path in COMBO_SOURCE_CANDIDATES:
        if path.exists():
            return pd.read_csv(path), path.name
    return pd.DataFrame(), "REP_S_00502_cleaned_updated.csv"


def _normalize_item_name(value: object) -> str:
    text = " ".join(str(value).upper().split())
    for token in ("[", "]", "..."):
        text = text.replace(token, "")
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip(" .,")


def _is_trivial_item(item_name: str) -> bool:
    normalized = _normalize_item_name(item_name)
    if normalized in TRIVIAL_EXACT_ITEMS:
        return True
    return any(keyword in normalized for keyword in TRIVIAL_KEYWORDS)


def _classify_item(item_name: str) -> str:
    normalized = _normalize_item_name(item_name)
    if _is_trivial_item(normalized):
        return "modifier"
    if any(keyword in normalized for keyword in BEVERAGE_KEYWORDS):
        return "beverage"
    if any(keyword in normalized for keyword in SAVORY_KEYWORDS):
        return "savory"
    if any(keyword in normalized for keyword in SWEET_KEYWORDS):
        return "sweet"
    return "other"


def _normalize_category_filters(include_categories: list[str]) -> set[str]:
    return {str(category).strip().lower() for category in include_categories if str(category).strip()}


def _normalize_excluded_items(exclude_items: list[str]) -> set[str]:
    return {_normalize_item_name(item) for item in exclude_items if str(item).strip()}


def _family_key(item_name: str) -> str:
    normalized = _normalize_item_name(item_name)
    for marker, family in FAMILY_MARKERS:
        if marker in normalized:
            return family
    first_token = normalized.split(" ", 1)[0] if normalized else "UNKNOWN"
    return first_token


def _derive_order_ids(df: pd.DataFrame) -> pd.DataFrame:
    order_keys = df[["branch", "customer_name", "customer_total_qty", "customer_total_amount"]].astype(str)
    order_breaks = order_keys.ne(order_keys.shift()).any(axis=1)
    out = df.copy()
    out["order_id"] = order_breaks.cumsum().map(lambda idx: f"ORD-{int(idx):06d}")
    return out


def _ensure_order_id(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    if "order_id" in df.columns and df["order_id"].astype(str).str.strip().ne("").any():
        out = df.copy()
        out["order_id"] = out["order_id"].astype(str).str.strip()
        return out, "Used native order_id from REP_S_00502_cleaned.csv."
    return _derive_order_ids(df), "Derived synthetic order_id from contiguous customer/order-total blocks."


def _prepare_transaction_frame(
    df: pd.DataFrame,
    branch: str | None,
    excluded_items: set[str],
) -> tuple[pd.DataFrame, list[str], dict[str, int]]:
    notes: list[str] = []
    stats = {
        "rows_loaded": int(len(df)),
        "orders_before_branch_filter": 0,
        "orders_after_branch_filter": 0,
        "orders_dropped_non_positive": 0,
        "rows_dropped_non_positive_qty": 0,
        "rows_dropped_trivial": 0,
        "rows_dropped_excluded_items": 0,
    }

    if df.empty:
        return df, ["REP_S_00502_cleaned.csv is missing from backend/data/processed."], stats

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        return pd.DataFrame(), [f"REP_S_00502_cleaned.csv is missing required columns: {', '.join(sorted(missing))}."], stats

    out = df.copy()
    numeric_cols = ["line_qty", "line_amount", "customer_total_qty", "customer_total_amount"]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    out["item_name"] = out["item_description"].map(_normalize_item_name)
    out, order_note = _ensure_order_id(out)
    notes.append(order_note)

    stats["orders_before_branch_filter"] = int(out["order_id"].nunique())

    if branch:
        out = out[out["branch"].astype(str).str.lower() == branch.lower()]
        notes.append(f"Filtered to branch '{branch}'.")

    stats["orders_after_branch_filter"] = int(out["order_id"].nunique()) if not out.empty else 0

    if out.empty:
        return out, notes, stats

    positive_orders = out.groupby("order_id")["customer_total_amount"].first()
    valid_order_ids = positive_orders[positive_orders > 0].index
    stats["orders_dropped_non_positive"] = int(len(positive_orders) - len(valid_order_ids))
    out = out[out["order_id"].isin(valid_order_ids)]
    notes.append(f"Dropped {stats['orders_dropped_non_positive']} zero-or-negative net orders.")

    rows_before_qty = len(out)
    out = out[out["line_qty"] > 0]
    stats["rows_dropped_non_positive_qty"] = int(rows_before_qty - len(out))
    notes.append(f"Dropped {stats['rows_dropped_non_positive_qty']} non-positive quantity rows.")

    if excluded_items:
        excluded_mask = out["item_name"].isin(excluded_items)
        stats["rows_dropped_excluded_items"] = int(excluded_mask.sum())
        out = out[~excluded_mask]
        notes.append(f"Removed {stats['rows_dropped_excluded_items']} rows matching explicit excluded items.")

    obvious_items = out["item_name"].map(_is_trivial_item)
    stats["rows_dropped_trivial"] = int(obvious_items.sum())
    out = out[~obvious_items]
    notes.append(f"Pruned {stats['rows_dropped_trivial']} obvious modifiers/add-ons before mining.")

    out["item_category"] = out["item_name"].map(_classify_item)
    out["item_family"] = out["item_name"].map(_family_key)

    return out.reset_index(drop=True), notes, stats


def _build_baskets(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    basket_lines = (
        df.groupby("order_id", as_index=False)
        .agg(
            branch=("branch", "first"),
            customer_name=("customer_name", "first"),
            items=("item_name", lambda s: sorted(set(s))),
            net_order_amount=("customer_total_amount", "first"),
        )
    )
    basket_lines["basket_size"] = basket_lines["items"].map(len)
    basket_lines = basket_lines[basket_lines["basket_size"] >= 2].reset_index(drop=True)

    exploded = basket_lines[["order_id", "items"]].explode("items").rename(columns={"items": "item_name"})
    if exploded.empty:
        return basket_lines, pd.DataFrame()

    one_hot = pd.crosstab(exploded["order_id"], exploded["item_name"]).clip(upper=1)
    return basket_lines, one_hot


def _build_item_meta(df: pd.DataFrame) -> dict[str, dict[str, str]]:
    item_meta = (
        df.groupby("item_name", as_index=False)
        .agg(item_category=("item_category", "first"), item_family=("item_family", "first"))
        .set_index("item_name")
        .to_dict(orient="index")
    )
    return item_meta


def _pair_key(rule: dict[str, object]) -> tuple[str, str]:
    return tuple(sorted((str(rule["antecedent"]), str(rule["consequent"]))))


def _resolve_anchor_item(anchor_item: str | None, available_items: set[str]) -> str | None:
    if not anchor_item:
        return None

    normalized_anchor = _normalize_item_name(anchor_item)
    if normalized_anchor in available_items:
        return normalized_anchor

    partial_matches = sorted(
        item for item in available_items if normalized_anchor in item or item in normalized_anchor
    )
    if partial_matches:
        return partial_matches[0]
    return normalized_anchor


def _rule_matches_categories(rule: dict[str, object], included_categories: set[str]) -> bool:
    if not included_categories:
        return True
    rule_categories = {
        str(rule["antecedent_category"]).lower(),
        str(rule["consequent_category"]).lower(),
    }
    return bool(rule_categories & included_categories)


def _rule_involves_anchor(rule: dict[str, object], anchor_item: str | None) -> bool:
    if not anchor_item:
        return True
    return anchor_item in {rule["antecedent"], rule["consequent"]}


def _anchor_first(rule: dict[str, object], anchor_item: str) -> dict[str, object]:
    if rule["antecedent"] == anchor_item:
        return rule
    if rule["consequent"] != anchor_item:
        return rule

    anchored = dict(rule)
    anchored["antecedent"], anchored["consequent"] = anchored["consequent"], anchored["antecedent"]
    anchored["antecedent_support"], anchored["consequent_support"] = (
        anchored["consequent_support"],
        anchored["antecedent_support"],
    )
    anchored["antecedent_category"], anchored["consequent_category"] = (
        anchored["consequent_category"],
        anchored["antecedent_category"],
    )
    return anchored


def _filter_rules(
    rules: list[dict[str, object]],
    mode: str,
    include_categories: set[str],
    anchor_item: str | None,
) -> list[dict[str, object]]:
    filtered = [rule for rule in rules if _rule_matches_categories(rule, include_categories)]

    if mode == "with_item":
        if anchor_item:
            filtered = [rule for rule in filtered if _rule_involves_anchor(rule, anchor_item)]
            filtered = [_anchor_first(rule, anchor_item) for rule in filtered]
            filtered.sort(
                key=lambda rule: (rule["confidence"], rule["lift"], rule["support"], rule["strategic_score"]),
                reverse=True,
            )
        return filtered

    if mode == "branch_pairs":
        filtered = sorted(
            filtered,
            key=lambda rule: (rule["support"], rule["confidence"], rule["lift"], rule["strategic_score"]),
            reverse=True,
        )
        return filtered

    return filtered


def _mine_pair_rules(one_hot: pd.DataFrame, item_meta: dict[str, dict[str, str]], payload: ComboRequest) -> tuple[list[dict[str, object]], int]:
    if one_hot.empty:
        return [], 0

    total_orders = len(one_hot.index)
    item_support = one_hot.mean(axis=0)
    frequent_items = sorted(item_support[item_support >= payload.min_support].index.tolist())
    rules: list[dict[str, object]] = []
    candidate_pairs_evaluated = 0

    for left_item, right_item in combinations(frequent_items, 2):
        candidate_pairs_evaluated += 1
        pair_support = float((one_hot[left_item] & one_hot[right_item]).sum() / total_orders)
        if pair_support < payload.min_support:
            continue

        left_support = float(item_support[left_item])
        right_support = float(item_support[right_item])
        left_meta = item_meta.get(left_item, {"item_category": "other", "item_family": _family_key(left_item)})
        right_meta = item_meta.get(right_item, {"item_category": "other", "item_family": _family_key(right_item)})
        same_family = left_meta["item_family"] == right_meta["item_family"]
        same_category = left_meta["item_category"] == right_meta["item_category"]

        directional_rules = (
            (left_item, right_item, left_support, right_support, left_meta, right_meta),
            (right_item, left_item, right_support, left_support, right_meta, left_meta),
        )

        for antecedent, consequent, antecedent_support, consequent_support, ant_meta, con_meta in directional_rules:
            if antecedent_support <= 0 or consequent_support <= 0:
                continue
            confidence = pair_support / antecedent_support
            lift = confidence / consequent_support
            if confidence < payload.min_confidence or lift < payload.min_lift:
                continue

            cross_category = ant_meta["item_category"] != con_meta["item_category"]
            strategic_score = lift * confidence * (1 + min(pair_support, 0.25))
            if cross_category:
                strategic_score *= 1.35
            if same_family:
                strategic_score *= 0.35
            elif same_category:
                strategic_score *= 0.8

            rules.append(
                {
                    "antecedent": antecedent,
                    "consequent": consequent,
                    "support": round(pair_support, 4),
                    "confidence": round(confidence, 4),
                    "lift": round(lift, 4),
                    "antecedent_support": round(antecedent_support, 4),
                    "consequent_support": round(consequent_support, 4),
                    "antecedent_category": ant_meta["item_category"],
                    "consequent_category": con_meta["item_category"],
                    "same_family": same_family,
                    "same_category": same_category,
                    "strategic_score": round(strategic_score, 4),
                }
            )

    rules.sort(key=lambda rule: (rule["strategic_score"], rule["lift"], rule["confidence"], rule["support"]), reverse=True)
    return rules, candidate_pairs_evaluated


def _unique_rules(rules: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped: list[dict[str, object]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for rule in rules:
        key = _pair_key(rule)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        deduped.append(rule)
    return deduped


def _strategic_rule_pool(rules: list[dict[str, object]]) -> list[dict[str, object]]:
    return [rule for rule in rules if not rule["same_family"]]


def _select_top_rules(rules: list[dict[str, object]], top_n: int) -> list[dict[str, object]]:
    strategic = _strategic_rule_pool(rules)
    core_categories = {"beverage", "sweet", "savory"}

    tier_one = [
        rule
        for rule in strategic
        if rule["antecedent_category"] in core_categories
        and rule["consequent_category"] in core_categories
        if rule["antecedent_category"] != rule["consequent_category"]
        and "beverage" in {rule["antecedent_category"], rule["consequent_category"]}
    ]
    tier_two = [
        rule
        for rule in strategic
        if rule["antecedent_category"] in core_categories
        and rule["consequent_category"] in core_categories
        and rule["antecedent_category"] != rule["consequent_category"]
    ]
    tier_three = [
        rule
        for rule in strategic
        if rule["antecedent_category"] != rule["consequent_category"]
    ]

    selected: list[dict[str, object]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for pool in (tier_one, tier_two, tier_three, strategic, rules):
        for rule in pool:
            key = _pair_key(rule)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            selected.append(rule)
            if len(selected) >= top_n:
                return selected
    return selected


def _select_branch_pair_rules(rules: list[dict[str, object]], top_n: int) -> list[dict[str, object]]:
    return _unique_rules(rules)[:top_n]


def _select_hidden_gems(rules: list[dict[str, object]], top_n: int) -> list[dict[str, object]]:
    candidates = [
        rule
        for rule in _unique_rules(_strategic_rule_pool(rules))
        if rule["lift"] >= 1.25 and rule["support"] <= 0.12
    ]
    beverage_led = [
        rule
        for rule in candidates
        if "beverage" in {rule["antecedent_category"], rule["consequent_category"]}
        and rule["antecedent_category"] != rule["consequent_category"]
    ]
    if beverage_led:
        return beverage_led[:top_n]
    return candidates[:top_n]


def _build_recommendations(rules: list[dict[str, object]], top_n: int) -> list[dict[str, object]]:
    recommendations = []
    for rule in rules[:top_n]:
        fit = f"{rule['antecedent_category']} -> {rule['consequent_category']}"
        recommendations.append(
            {
                "bundle": [rule["antecedent"], rule["consequent"]],
                "recommended_anchor": rule["antecedent"],
                "attach_item": rule["consequent"],
                "why_it_matters": f"Confidence {rule['confidence']:.2f} and lift {rule['lift']:.2f} suggest a strong {fit} cross-sell.",
                "evidence": {
                    "support": rule["support"],
                    "confidence": rule["confidence"],
                    "lift": rule["lift"],
                },
            }
        )
    return recommendations


def recommend_combos(payload: ComboRequest) -> ToolResponse:
    raw_df, source_name = _load_combo_source()
    included_categories = _normalize_category_filters(payload.include_categories)
    excluded_items = _normalize_excluded_items(payload.exclude_items)
    df, prep_notes, prep_stats = _prepare_transaction_frame(raw_df, payload.branch, excluded_items)

    if df.empty:
        return ToolResponse(
            tool_name="recommend_combos",
            result={
                "top_rules": [],
                "hidden_gems": [],
                "recommended_combos": [],
                "one_hot_matrix_shape": {"orders": 0, "products": 0},
                "basket_preview": [],
            },
            key_evidence_metrics={"orders_analyzed": 0, "products_considered": 0, "rules_found": 0},
            assumptions=[
                "The 00502 processed source file was unavailable or could not be transformed into valid baskets.",
                "Association rules require at least 2 non-trivial items per order.",
            ],
            data_coverage_notes=prep_notes,
        )

    baskets, one_hot = _build_baskets(df)
    item_meta = _build_item_meta(df)
    resolved_anchor = _resolve_anchor_item(payload.anchor_item, set(item_meta))
    if payload.mode == "with_item" and not payload.anchor_item:
        prep_notes.append("Mode 'with_item' was requested without anchor_item; returning the general ranked rule set.")
    elif payload.anchor_item:
        prep_notes.append(f"Resolved anchor item to '{resolved_anchor}'.")
    rules, candidate_pairs_evaluated = _mine_pair_rules(one_hot, item_meta, payload)
    rules = _filter_rules(rules, payload.mode, included_categories, resolved_anchor)

    if payload.mode == "branch_pairs":
        top_rules = _select_branch_pair_rules(rules, payload.top_n)
    else:
        top_rules = _select_top_rules(rules, payload.top_n)

    hidden_gems = _select_hidden_gems(rules, payload.top_n)
    if payload.mode == "with_item" and resolved_anchor:
        hidden_gems = [
            rule for rule in hidden_gems if _rule_involves_anchor(rule, resolved_anchor)
        ][: payload.top_n]
    recommendations = _build_recommendations(top_rules, payload.top_n)

    product_frequency = pd.Series(dtype=float)
    if not one_hot.empty:
        product_frequency = one_hot.mean(axis=0).sort_values(ascending=False).head(payload.top_n)

    basket_preview = [
        {
            "order_id": row["order_id"],
            "customer_name": row["customer_name"],
            "branch": row["branch"],
            "items": row["items"],
        }
        for _, row in baskets.head(min(5, len(baskets))).iterrows()
    ]

    return ToolResponse(
        tool_name="recommend_combos",
        result={
            "top_rules": top_rules,
            "hidden_gems": hidden_gems,
            "recommended_combos": recommendations,
            "one_hot_matrix_shape": {"orders": int(one_hot.shape[0]), "products": int(one_hot.shape[1])},
            "top_products_by_support": [
                {"item": item, "support": round(float(support), 4)} for item, support in product_frequency.items()
            ],
            "basket_preview": basket_preview,
            "pruning_summary": prep_stats,
            "raw_top_rules": _unique_rules(rules)[: min(5, payload.top_n)],
            "query_context": {
                "mode": payload.mode,
                "resolved_anchor_item": resolved_anchor,
                "include_categories": sorted(included_categories),
                "exclude_items": sorted(excluded_items),
            },
        },
        key_evidence_metrics={
            "orders_analyzed": int(baskets.shape[0]),
            "orders_before_pair_filter": int(df["order_id"].nunique()),
            "products_considered": int(one_hot.shape[1]) if not one_hot.empty else 0,
            "rules_found": int(len(rules)),
            "candidate_pairs_evaluated": int(candidate_pairs_evaluated),
            "branch_filtered": payload.branch or "all",
        },
        assumptions=[
            "This tool prefers REP_S_00502_cleaned_updated.csv and falls back to REP_S_00502_cleaned.csv if needed.",
            "It uses a native order_id if present; otherwise it falls back to synthetic basket segmentation.",
            "Rules are mined with Apriori-style frequent-item pruning on single products, then 2-item association scoring with support, confidence, and lift.",
            "Strategic ranking penalizes same-family pairings so the returned recommendations are more cross-sell oriented than raw co-occurrence pairs.",
            "Mode controls how results are ranked: top_combos favors strategic cross-sells, with_item focuses on one anchor item, and branch_pairs ranks by raw frequency within the selected branch.",
            "Scaled data preserves relative patterns but not absolute revenue values.",
        ],
        data_coverage_notes=prep_notes
        + [
            f"Loaded {len(raw_df):,} line rows from {source_name}.",
            f"Retained {len(df):,} qualifying line rows across {df['order_id'].nunique():,} valid orders after pruning.",
            f"Applied mode '{payload.mode}' to {len(rules):,} qualifying rules.",
        ],
    )
