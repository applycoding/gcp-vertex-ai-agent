"""FastAPI service for the Northline Outfitters agent."""

from __future__ import annotations

import re
import threading
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import __version__
from app.agent import Agent, ModelClient, ModelError
from app.config import Settings, load_settings
from app.conversation import ChatMessage
from app.firestore_store import build_firestore_store
from app.local_router import LocalToolRouter
from app.logging_setup import configure_logging, get_logger, log_event
from app.secrets import SecretReader, resolve_system_prompt
from app.store import CatalogStore, MemoryStore
from app.vertex import build_vertex_client

logger = get_logger()

_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_HISTORY_LIMIT = 20


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"message": "Is the Lumen lantern in stock?"}]}
    )

    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None

    @field_validator("session_id")
    @classmethod
    def session_id_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _SESSION_RE.fullmatch(value) is None:
            raise ValueError("session_id must be 1-64 characters of letters, numbers, underscore, or hyphen")
        return value


class ToolCallRecord(BaseModel):
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tool_calls: list[ToolCallRecord]


class ProductRecord(BaseModel):
    sku: str
    name: str
    description: str
    tags: list[str]
    price_cents: int
    stock: int


class CatalogResponse(BaseModel):
    products: list[ProductRecord]


class SessionMemory:
    def __init__(self, limit: int = _HISTORY_LIMIT) -> None:
        self._limit = limit
        self._items: dict[str, list[ChatMessage]] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> list[ChatMessage]:
        with self._lock:
            return list(self._items.get(session_id, []))

    def save(self, session_id: str, messages: list[ChatMessage]) -> None:
        with self._lock:
            self._items[session_id] = list(messages[-self._limit :])


def build_store(settings: Settings) -> CatalogStore:
    if settings.store_backend == "memory":
        return MemoryStore()
    if settings.store_backend == "firestore":
        if not settings.project_id:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is required when STORE_BACKEND=firestore")
        return build_firestore_store(settings.project_id, settings.firestore_database)
    raise RuntimeError(f"Unknown STORE_BACKEND: {settings.store_backend}")


def build_model(settings: Settings, system_prompt: str) -> ModelClient:
    if settings.model_backend == "local":
        return LocalToolRouter()
    if settings.model_backend == "vertex":
        return build_vertex_client(settings, system_prompt)
    raise RuntimeError(f"Unknown MODEL_BACKEND: {settings.model_backend}")


def create_app(
    *,
    settings: Settings | None = None,
    store: CatalogStore | None = None,
    model: ModelClient | None = None,
    system_prompt: str | None = None,
    secret_reader: SecretReader | None = None,
    cloud_log_client: Any | None = None,
) -> FastAPI:
    active_settings = settings or load_settings()
    configure_logging(
        use_cloud_client=active_settings.cloud_logging_client,
        cloud_client=cloud_log_client,
    )
    prompt = (
        system_prompt
        if system_prompt is not None
        else resolve_system_prompt(active_settings, secret_reader)
    )
    active_store = store if store is not None else build_store(active_settings)
    active_model = model if model is not None else build_model(active_settings, prompt)
    agent = Agent(active_model, active_store, max_tool_rounds=active_settings.max_tool_rounds)
    sessions = SessionMemory()

    app = FastAPI(
        title="Northline Outfitters agent",
        version=__version__,
        summary="Catalog, stock, and support tools in front of Gemini on Vertex AI.",
        description=(
            "Portfolio demo. The default process uses an in-memory catalog and a "
            "deterministic local router so it runs without Google credentials. "
            "Set MODEL_BACKEND=vertex and STORE_BACKEND=firestore to use Vertex AI and Firestore."
        ),
    )
    app.state.store = active_store

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "northline-outfitters-agent",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/catalog", response_model=CatalogResponse)
    def catalog() -> CatalogResponse:
        products = [ProductRecord.model_validate(product.to_dict()) for product in active_store.list_products()]
        return CatalogResponse(products=products)

    @app.post("/v1/chat", response_model=ChatResponse)
    def chat(body: ChatRequest) -> ChatResponse:
        session_id = body.session_id or uuid4().hex
        history = sessions.get(session_id)
        try:
            result = agent.run(body.message, history=history)
        except ModelError:
            logger.warning("model error", exc_info=True)
            raise HTTPException(status_code=502, detail="The model call failed.") from None
        sessions.save(session_id, result.messages)
        log_event(
            logger,
            "chat finished",
            session_id=session_id,
            tools=[item.name for item in result.trace],
        )
        return ChatResponse(
            reply=result.reply,
            session_id=session_id,
            tool_calls=[
                ToolCallRecord(name=item.name, args=item.args, result=item.result) for item in result.trace
            ],
        )

    return app


app = create_app()
