from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.tools.openclaw_chat import chat_with_openclaw

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(payload: AgentChatRequest) -> AgentChatResponse:
    try:
        return chat_with_openclaw(payload)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
