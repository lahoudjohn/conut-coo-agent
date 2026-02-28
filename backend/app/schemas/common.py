from typing import Any

from pydantic import BaseModel, Field


class ToolResponse(BaseModel):
    tool_name: str
    result: dict[str, Any] = Field(default_factory=dict)
    key_evidence_metrics: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    data_coverage_notes: list[str] = Field(default_factory=list)
