from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from pydantic import BaseModel

_MAX_EVENTS = 50
_EVENTS: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_LOCK = Lock()
_SEQUENCE = 0


def _compact_value(value: Any, *, max_dict_items: int = 8, max_list_items: int = 5) -> Any:
    if isinstance(value, BaseModel):
        return _compact_value(value.model_dump(), max_dict_items=max_dict_items, max_list_items=max_list_items)
    if isinstance(value, dict):
        return {
            str(key): _compact_value(item, max_dict_items=max_dict_items, max_list_items=max_list_items)
            for key, item in list(value.items())[:max_dict_items]
        }
    if isinstance(value, list):
        return [_compact_value(item, max_dict_items=max_dict_items, max_list_items=max_list_items) for item in value[:max_list_items]]
    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized if len(normalized) <= 120 else f"{normalized[:117]}..."
    return value


def record_tool_activity(
    *,
    tool_name: str,
    path: str,
    source: str,
    payload: Any,
    result_preview: dict[str, Any] | None = None,
    raw_output: Any = None,
    agent_tool: str | None = None,
) -> None:
    global _SEQUENCE

    with _LOCK:
        _SEQUENCE += 1
        _EVENTS.appendleft(
            {
                "event_id": _SEQUENCE,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool_name": tool_name,
                "path": path,
                "source": source,
                "agent_tool": agent_tool,
                "payload": _compact_value(payload),
                "result_preview": _compact_value(result_preview or {}),
                "raw_output": _compact_value(raw_output or {}, max_dict_items=20, max_list_items=10),
            }
        )


def list_tool_activity(limit: int = 25) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, _MAX_EVENTS))
    with _LOCK:
        return list(_EVENTS)[:safe_limit]
