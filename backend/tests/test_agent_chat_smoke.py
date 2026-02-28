from fastapi.testclient import TestClient

from app.main import app
from app.schemas.agent import AgentChatResponse

client = TestClient(app)


def test_agent_chat_route(monkeypatch) -> None:
    from app.api.routes import agent as agent_routes

    def fake_chat_with_openclaw(payload):
        return AgentChatResponse(
            session_id=payload.session_id or "test-session",
            assistant_message="Proxy ok",
            raw_gateway_response={"choices": [{"message": {"content": "Proxy ok"}}]},
        )

    monkeypatch.setattr(agent_routes, "chat_with_openclaw", fake_chat_with_openclaw)

    response = client.post(
        "/agent/chat",
        json={"message": "hello", "session_id": "abc-123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "abc-123"
    assert body["assistant_message"] == "Proxy ok"
    assert "raw_gateway_response" in body
