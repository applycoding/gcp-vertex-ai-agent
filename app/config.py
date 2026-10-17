"""Process settings. Defaults run the demo with no Google credentials."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    model_backend: str
    store_backend: str
    project_id: str
    location: str
    model_name: str
    firestore_database: str
    prompt_secret: str
    secret_manager_enabled: bool
    cloud_logging_client: bool
    max_tool_rounds: int


def load_settings() -> Settings:
    raw_rounds = os.getenv("MAX_TOOL_ROUNDS", "4")
    try:
        max_tool_rounds = int(raw_rounds)
    except ValueError as exc:
        raise RuntimeError("MAX_TOOL_ROUNDS must be an integer") from exc
    if max_tool_rounds < 1:
        raise RuntimeError("MAX_TOOL_ROUNDS must be at least 1")
    return Settings(
        model_backend=os.getenv("MODEL_BACKEND", "local").strip().lower(),
        store_backend=os.getenv("STORE_BACKEND", "memory").strip().lower(),
        project_id=os.getenv("GOOGLE_CLOUD_PROJECT", "").strip(),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip(),
        model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        firestore_database=os.getenv("FIRESTORE_DATABASE", "(default)").strip() or "(default)",
        prompt_secret=os.getenv("AGENT_PROMPT_SECRET", "agent-system-prompt").strip(),
        secret_manager_enabled=_flag("SECRET_MANAGER_ENABLED"),
        cloud_logging_client=_flag("CLOUD_LOGGING_CLIENT"),
        max_tool_rounds=max_tool_rounds,
    )
