from fastapi import APIRouter, HTTPException

from app.schemas.tools import ComboRequest, ToolResponse
from app.objectives.objectives_combos import recommend_combos

router = APIRouter(prefix="/combos", tags=["Combo Recommendations"])


@router.post("/recommend", response_model=ToolResponse)
def get_combo_recommendations(payload: ComboRequest) -> ToolResponse:
    """
    Mine association rules from transaction data and return ranked combo recommendations.

    **Modes:**
    - `top_combos` — Strategic cross-sell combos ranked by lift × confidence × support.
    - `with_item` — All rules involving a specific `anchor_item` (e.g. "LATTE").
    - `branch_pairs` — Most frequent item pairs within a specific branch.

    **Filters:**
    - `branch` — Restrict analysis to a single branch (optional).
    - `anchor_item` — Required when mode is `with_item`.
    - `include_categories` — Limit rules to specific categories: `beverage`, `sweet`, `savory`, `other`.
    - `exclude_items` — Remove specific items from the basket before mining.

    **Thresholds:**
    - `min_support` — Minimum fraction of orders an item pair must appear in (default: 0.01).
    - `min_confidence` — Minimum conditional probability antecedent → consequent (default: 0.1).
    - `min_lift` — Minimum lift above random chance (default: 1.0).
    - `top_n` — Number of rules/recommendations to return (default: 10).
    """
    try:
        return recommend_combos(payload)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Combo engine failed: {e}")
