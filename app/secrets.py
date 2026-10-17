"""System prompt from the environment, or from Secret Manager when enabled."""

from __future__ import annotations

import os
from typing import Protocol

from google.cloud import secretmanager

from app.config import Settings
from app.prompts import DEFAULT_SYSTEM_PROMPT


class SecretReader(Protocol):
    def read(self, secret_id: str) -> str:
        """Return the latest payload for secret_id."""


class _SecretPayload:
    data: bytes


class _SecretResponse:
    payload: _SecretPayload


class SecretVersionClient(Protocol):
    def access_secret_version(self, *, request: dict[str, str]) -> _SecretResponse:
        """Fetch one secret version. Matches the Secret Manager client call."""


class SecretManagerReader:
    """Reads the latest enabled version of one secret."""

    def __init__(self, client: SecretVersionClient, project_id: str) -> None:
        self._client = client
        self._project_id = project_id

    def read(self, secret_id: str) -> str:
        name = f"projects/{self._project_id}/secrets/{secret_id}/versions/latest"
        response = self._client.access_secret_version(request={"name": name})
        return response.payload.data.decode("utf-8")


def build_secret_reader(project_id: str) -> SecretManagerReader:
    client = secretmanager.SecretManagerServiceClient()
    return SecretManagerReader(client, project_id)


def resolve_system_prompt(settings: Settings, reader: SecretReader | None = None) -> str:
    override = os.getenv("AGENT_SYSTEM_PROMPT", "").strip()
    if override:
        return override
    if not settings.secret_manager_enabled:
        return DEFAULT_SYSTEM_PROMPT
    if not settings.project_id:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is required when SECRET_MANAGER_ENABLED=true")
    active = reader if reader is not None else build_secret_reader(settings.project_id)
    value = active.read(settings.prompt_secret).strip()
    if not value:
        raise RuntimeError(f"Secret {settings.prompt_secret} is empty")
    return value
