"""Secret resolution and the Cloud Logging JSON shape. No live GCP calls."""

import json
import logging

import pytest

from app.config import Settings
from app.logging_setup import JsonLogFormatter, configure_logging
from app.prompts import DEFAULT_SYSTEM_PROMPT
from app.secrets import SecretManagerReader, resolve_system_prompt


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "model_backend": "local",
        "store_backend": "memory",
        "project_id": "demo-project",
        "location": "us-central1",
        "model_name": "gemini-2.5-flash",
        "firestore_database": "(default)",
        "prompt_secret": "agent-system-prompt",
        "secret_manager_enabled": False,
        "cloud_logging_client": False,
        "max_tool_rounds": 4,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class _Payload:
    def __init__(self, data: bytes) -> None:
        self.data = data


class _Response:
    def __init__(self, text: str) -> None:
        self.payload = _Payload(text.encode())


class FakeSecretClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.names: list[str] = []

    def access_secret_version(self, *, request: dict[str, str]) -> _Response:
        self.names.append(request["name"])
        return _Response(self.text)


class _Reader:
    def __init__(self, text: str) -> None:
        self.text = text
        self.secret_ids: list[str] = []

    def read(self, secret_id: str) -> str:
        self.secret_ids.append(secret_id)
        return self.text


def test_secret_manager_reader_requests_the_latest_version() -> None:
    client = FakeSecretClient("Answer in one sentence.")
    reader = SecretManagerReader(client, "demo-project")

    assert reader.read("agent-system-prompt") == "Answer in one sentence."
    assert client.names == ["projects/demo-project/secrets/agent-system-prompt/versions/latest"]


def test_env_prompt_wins_over_secret_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_SYSTEM_PROMPT", "from the environment")
    reader = _Reader("from the secret")

    resolved = resolve_system_prompt(_settings(secret_manager_enabled=True), reader)

    assert resolved == "from the environment"
    assert reader.secret_ids == []


def test_disabled_secret_manager_uses_the_default_prompt() -> None:
    reader = _Reader("unused")
    assert resolve_system_prompt(_settings(), reader) == DEFAULT_SYSTEM_PROMPT
    assert reader.secret_ids == []


def test_enabled_secret_manager_reads_the_configured_secret() -> None:
    reader = _Reader("  be brief  ")
    resolved = resolve_system_prompt(_settings(secret_manager_enabled=True), reader)
    assert resolved == "be brief"
    assert reader.secret_ids == ["agent-system-prompt"]


def test_empty_secret_and_missing_project_fail() -> None:
    with pytest.raises(RuntimeError, match="empty"):
        resolve_system_prompt(_settings(secret_manager_enabled=True), _Reader("  "))
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        resolve_system_prompt(_settings(secret_manager_enabled=True, project_id=""), None)


def test_json_formatter_uses_cloud_logging_severity() -> None:
    record = logging.LogRecord(
        name="northline",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="tool finished",
        args=(),
        exc_info=None,
    )
    record.extra_fields = {"tool": "search_catalog", "ok": True}

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["severity"] == "INFO"
    assert payload["message"] == "tool finished"
    assert payload["logger"] == "northline"
    assert payload["tool"] == "search_catalog"
    assert payload["ok"] is True
    assert payload["time"].endswith("Z")


def test_cloud_logging_client_is_attached_when_requested() -> None:
    class FakeCloudLog:
        def __init__(self) -> None:
            self.levels: list[int] = []

        def setup_logging(self, *, log_level: int) -> None:
            self.levels.append(log_level)

    client = FakeCloudLog()
    configure_logging(use_cloud_client=True, cloud_client=client)
    configure_logging(use_cloud_client=False)

    assert client.levels == [logging.INFO]
