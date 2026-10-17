"""HTTP API with a scripted model and with the default local demo wiring."""

from fastapi.testclient import TestClient

from app.agent import ModelError
from app.conversation import ModelResponse
from app.main import create_app
from app.store import MemoryStore
from tests.fakes import ScriptedModel


def test_health_catalog_and_default_chat() -> None:
    client = TestClient(create_app())

    health = client.get("/health")
    catalog = client.get("/v1/catalog")
    chat = client.post("/v1/chat", json={"message": "Is the Lumen lantern in stock?"})

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert catalog.status_code == 200
    assert len(catalog.json()["products"]) == 5
    assert chat.status_code == 200
    body = chat.json()
    assert "24" in body["reply"]
    assert [item["name"] for item in body["tool_calls"]] == ["search_catalog", "check_stock"]
    assert body["session_id"]


def test_scripted_session_keeps_history() -> None:
    model = ScriptedModel(
        [
            ModelResponse(text="The lantern has 24 in stock."),
            ModelResponse(text="I already checked the lantern."),
        ]
    )
    client = TestClient(create_app(model=model, store=MemoryStore()))

    first = client.post("/v1/chat", json={"message": "lantern stock"})
    session_id = first.json()["session_id"]
    second = client.post("/v1/chat", json={"message": "and the mug?", "session_id": session_id})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["reply"] == "I already checked the lantern."
    transcript = [(message.role, message.text) for message in model.seen[1]]
    assert transcript == [
        ("user", "lantern stock"),
        ("model", "The lantern has 24 in stock."),
        ("user", "and the mug?"),
    ]


def test_blank_message_and_bad_session_are_rejected() -> None:
    client = TestClient(create_app(model=ScriptedModel([]), store=MemoryStore()))

    blank = client.post("/v1/chat", json={"message": ""})
    bad_session = client.post("/v1/chat", json={"message": "hello", "session_id": "has spaces"})

    assert blank.status_code == 422
    assert bad_session.status_code == 422


def test_model_failure_is_a_502() -> None:
    class Boom:
        def complete(self, messages: list, tool_specs: list) -> None:
            raise ModelError("backend unavailable")

    client = TestClient(create_app(model=Boom(), store=MemoryStore()))
    response = client.post("/v1/chat", json={"message": "lantern"})

    assert response.status_code == 502
    assert response.json() == {"detail": "The model call failed."}
