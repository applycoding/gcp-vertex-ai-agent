"""Vertex client translation: scripted SDK responses, no network."""

import pytest

from app.config import Settings
from app.conversation import ChatMessage, ToolCall, ToolResult
from app.errors import ModelError
from app.prompts import DEFAULT_SYSTEM_PROMPT
from app.tools import TOOL_SPECS
from app.vertex import VertexGeminiClient, build_vertex_client, parse_model_response


class _FunctionCall:
    def __init__(self, name: str, args: dict[str, object]) -> None:
        self.name = name
        self.args = args


class _Part:
    def __init__(self, text: str | None) -> None:
        self.text = text
        self.function_call = None


class _Content:
    def __init__(self, parts: list[_Part]) -> None:
        self.parts = parts


class _Candidate:
    def __init__(self, content: _Content) -> None:
        self.content = content


class _Response:
    def __init__(self, function_calls: list[_FunctionCall], text: str | None) -> None:
        self.function_calls = function_calls
        parts = [_Part(text)] if text else []
        self.candidates = [_Candidate(_Content(parts))]


class _Models:
    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def generate_content(self, *, model: str, contents: list, config: object) -> object:
        self.calls.append({"model": model, "contents": contents, "config": config})
        if not self._responses:
            raise RuntimeError("sdk down")
        return self._responses.pop(0)


class _Client:
    def __init__(self, responses: list[object]) -> None:
        self.models = _Models(responses)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "model_backend": "vertex",
        "store_backend": "firestore",
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


def test_parser_reads_function_calls_and_text() -> None:
    parsed = parse_model_response(_Response([_FunctionCall("check_stock", {"sku": "LN-220"})], None))
    assert parsed.text is None
    assert parsed.tool_calls == [ToolCall("check_stock", {"sku": "LN-220"})]

    text_only = parse_model_response(_Response([], "All set."))
    assert text_only.text == "All set."
    assert text_only.tool_calls == []


def test_parser_rejects_an_empty_response() -> None:
    with pytest.raises(ModelError):
        parse_model_response(_Response([], None))


def test_client_disables_automatic_function_calling_and_replays_tool_results() -> None:
    client = _Client([_Response([], "The lantern has 24 in stock.")])
    model = VertexGeminiClient(client, model="gemini-2.5-flash", system_prompt="be brief")
    messages = [
        ChatMessage(role="user", text="find lanterns"),
        ChatMessage(role="model", tool_calls=[ToolCall("search_catalog", {"query": "lantern"})]),
        ChatMessage(
            role="tool",
            tool_results=[ToolResult("search_catalog", {"products": [{"sku": "LN-220"}]})],
        ),
    ]

    parsed = model.complete(messages, TOOL_SPECS)

    assert parsed.text == "The lantern has 24 in stock."
    call = client.models.calls[0]
    assert call["model"] == "gemini-2.5-flash"
    config = call["config"]
    assert config.temperature == 0
    assert config.system_instruction == "be brief"
    assert config.automatic_function_calling.disable is True
    names = [item.name for item in config.tools[0].function_declarations]
    assert names == ["search_catalog", "check_stock", "create_support_case"]
    contents = call["contents"]
    assert [item.role for item in contents] == ["user", "model", "tool"]
    assert contents[1].parts[0].function_call.name == "search_catalog"
    assert contents[1].parts[0].function_call.args["query"] == "lantern"
    assert contents[2].parts[0].function_response.name == "search_catalog"
    assert contents[2].parts[0].function_response.response["products"][0]["sku"] == "LN-220"


def test_sdk_failure_becomes_model_error() -> None:
    model = VertexGeminiClient(_Client([]), model="gemini-2.5-flash", system_prompt="be brief")
    with pytest.raises(ModelError, match="vertex generate_content failed"):
        model.complete([ChatMessage(role="user", text="hi")], TOOL_SPECS)


def test_build_requires_a_project() -> None:
    with pytest.raises(ModelError, match="GOOGLE_CLOUD_PROJECT"):
        build_vertex_client(_settings(project_id=""), DEFAULT_SYSTEM_PROMPT)
