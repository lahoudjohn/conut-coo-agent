from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to send to OpenClaw.")
    session_id: str | None = Field(
        default=None,
        description="Stable session identifier so repeated calls share the same OpenClaw session.",
    )


class AgentChatResponse(BaseModel):
    session_id: str
    assistant_message: str
    raw_gateway_response: dict[str, Any]
