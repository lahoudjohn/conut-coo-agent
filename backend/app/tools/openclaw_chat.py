from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import httpx

from app.core.config import settings
from app.schemas.agent import AgentChatRequest, AgentChatResponse


def _normalize_gateway_url() -> str:
    return settings.openclaw_gateway_url.rstrip("/")


def _load_gateway_token() -> str:
    if settings.openclaw_gateway_token:
        return settings.openclaw_gateway_token

    config_path: Path = settings.openclaw_config_path
    if not config_path.exists():
        raise ValueError(
            f"OpenClaw config not found at {config_path}. Set CONUT_OPENCLAW_GATEWAY_TOKEN or run OpenClaw onboard first."
        )

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive config read
        raise ValueError(f"Failed to read OpenClaw config at {config_path}: {exc}") from exc

    token = (
        payload.get("gateway", {})
        .get("auth", {})
        .get("token")
    )
    if not token:
        raise ValueError(
            "OpenClaw gateway token is missing. Set gateway.auth.token in ~/.openclaw/openclaw.json "
            "or provide CONUT_OPENCLAW_GATEWAY_TOKEN."
        )
    return str(token)


def _extract_assistant_message(raw_response: dict) -> str:
    choices = raw_response.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    content = message.get("content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
                elif isinstance(part.get("content"), str):
                    text_parts.append(part["content"])
            elif isinstance(part, str):
                text_parts.append(part)
        return "\n".join(part for part in text_parts if part).strip()

    return str(content)


def chat_with_openclaw(payload: AgentChatRequest) -> AgentChatResponse:
    session_id = payload.session_id or str(uuid4())
    gateway_token = _load_gateway_token()
    gateway_url = _normalize_gateway_url()

    request_body = {
        "model": f"openclaw:{settings.openclaw_agent_id}",
        "user": session_id,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the Conut COO Agent. For Conut operational questions, prefer using the "
                    "available Conut tools instead of answering from general knowledge. Use tools for "
                    "combo optimization, demand forecasting, expansion feasibility, shift staffing, "
                    "and coffee or milkshake growth strategy whenever relevant. Base answers on tool "
                    "outputs and cite evidence from the tool results."
                ),
            },
            {
                "role": "user",
                "content": payload.message,
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {gateway_token}",
        "Content-Type": "application/json",
        "x-openclaw-agent-id": settings.openclaw_agent_id,
    }

    try:
        response = httpx.post(
            f"{gateway_url}/v1/chat/completions",
            json=request_body,
            headers=headers,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise ValueError(f"Failed to reach OpenClaw gateway at {gateway_url}: {exc}") from exc

    try:
        raw_payload = response.json()
    except ValueError:
        raw_payload = {"raw": response.text}

    if response.status_code >= 400:
        raise ValueError(
            f"OpenClaw gateway returned {response.status_code}: {raw_payload}"
        )

    assistant_message = _extract_assistant_message(raw_payload)
    if not assistant_message:
        assistant_message = "OpenClaw returned an empty response."

    return AgentChatResponse(
        session_id=session_id,
        assistant_message=assistant_message,
        raw_gateway_response=raw_payload,
    )
