from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ToolResponse


class ComboRequest(BaseModel):
    mode: Literal["top_combos", "with_item", "branch_pairs"] = Field(
        default="top_combos",
        description="Query mode for combo retrieval.",
    )
    branch: str | None = Field(default=None, description="Optional branch filter.")
    anchor_item: str | None = Field(default=None, description="Specific item to center combo analysis on.")
    include_categories: list[Literal["beverage", "sweet", "savory", "other"]] = Field(
        default_factory=list,
        description="Optional category filters for returned rules.",
    )
    exclude_items: list[str] = Field(
        default_factory=list,
        description="Optional item names to exclude before mining or ranking.",
    )
    top_n: int = Field(default=5, ge=1, le=20)
    min_support: float = Field(default=0.02, ge=0, le=1)
    min_confidence: float = Field(default=0.3, ge=0, le=1)
    min_lift: float = Field(default=1.0, ge=0)


class ForecastRequest(BaseModel):
    branch: str = Field(..., description="Branch to forecast.")
    horizon_days: int = Field(default=7, ge=1, le=31)


class StaffingRequest(BaseModel):
    branch: str
    shift: Literal["morning", "afternoon", "evening", "night"] = "evening"
    target_date: date | None = None


class ExpansionRequest(BaseModel):
    candidate_location: str = Field(..., description="Human-readable proposed area or branch label.")
    target_region: str | None = Field(default=None, description="Optional regional grouping if you use one.")


class GrowthStrategyRequest(BaseModel):
    branch: str | None = None
    focus_categories: list[str] = Field(default_factory=lambda: ["coffee", "milkshake"])
