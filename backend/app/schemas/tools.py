from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ToolResponse


class ComboRequest(BaseModel):
    branch: str | None = Field(default=None, description="Optional branch filter.")
    top_n: int = Field(default=5, ge=1, le=20)
    min_support: float = Field(default=0.02, ge=0, le=1)


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
