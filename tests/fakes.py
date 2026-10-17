"""Scripted model client and an in-memory Firestore stand-in."""

from __future__ import annotations

from typing import Any

from app.agent import ModelError
from app.catalog import seed_products
from app.conversation import ChatMessage, ModelResponse
from app.tools import ToolSpec


class ScriptedModel:
    """Returns a fixed sequence of model turns and records the transcripts it saw."""

    def __init__(self, script: list[ModelResponse]) -> None:
        self.script = list(script)
        self.seen: list[list[ChatMessage]] = []
        self.specs: list[list[ToolSpec]] = []

    def complete(self, messages: list[ChatMessage], tool_specs: list[ToolSpec]) -> ModelResponse:
        self.seen.append(list(messages))
        self.specs.append(list(tool_specs))
        if not self.script:
            raise ModelError("scripted model has no responses left")
        return self.script.pop(0)


class FakeSnapshot:
    def __init__(self, doc_id: str, data: dict[str, Any] | None, exists: bool) -> None:
        self.id = doc_id
        self._data = data
        self.exists = exists

    def to_dict(self) -> dict[str, Any] | None:
        if self._data is None:
            return None
        return dict(self._data)


class FakeDocument:
    def __init__(self, docs: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._docs = docs
        self._doc_id = doc_id

    def get(self) -> FakeSnapshot:
        if self._doc_id not in self._docs:
            return FakeSnapshot(self._doc_id, None, False)
        return FakeSnapshot(self._doc_id, self._docs[self._doc_id], True)

    def set(self, data: dict[str, Any]) -> None:
        self._docs[self._doc_id] = dict(data)


class FakeCollection:
    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self.docs = docs

    def stream(self) -> list[FakeSnapshot]:
        return [FakeSnapshot(doc_id, data, True) for doc_id, data in self.docs.items()]

    def document(self, document_id: str) -> FakeDocument:
        return FakeDocument(self.docs, document_id)


class FakeFirestore:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> FakeCollection:
        self.collections.setdefault(name, {})
        return FakeCollection(self.collections[name])


def seeded_firestore() -> FakeFirestore:
    client = FakeFirestore()
    products = client.collection("products")
    for product in seed_products():
        products.document(product.sku).set(product.to_dict())
    return client
