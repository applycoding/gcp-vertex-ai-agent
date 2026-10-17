"""Firestore-backed catalog. The client is injected so tests can pass a fake."""

from __future__ import annotations

from typing import Any, Protocol

from google.cloud import firestore

from app.catalog import search_products
from app.domain import (
    CaseDraft,
    Product,
    SupportCase,
    case_from_mapping,
    new_case,
    product_from_mapping,
)

PRODUCTS_COLLECTION = "products"
CASES_COLLECTION = "support_cases"


class _Snapshot(Protocol):
    exists: bool
    id: str

    def to_dict(self) -> dict[str, Any] | None:
        """Return the document body."""


class _DocumentRef(Protocol):
    def get(self) -> _Snapshot:
        """Fetch the document."""

    def set(self, data: dict[str, Any]) -> None:
        """Write the document."""


class _Collection(Protocol):
    def stream(self) -> Any:
        """Yield document snapshots."""

    def document(self, document_id: str) -> _DocumentRef:
        """Return a document reference."""


class _FirestoreClient(Protocol):
    def collection(self, name: str) -> _Collection:
        """Return a collection reference."""


class FirestoreCatalogStore:
    """Reads products and writes support cases in Firestore.

    Search still filters in process. A production catalog would use a search
    index; this demo keeps the query next to the documents.
    """

    def __init__(
        self,
        client: _FirestoreClient,
        *,
        products_collection: str = PRODUCTS_COLLECTION,
        cases_collection: str = CASES_COLLECTION,
    ) -> None:
        self._client = client
        self._products_collection = products_collection
        self._cases_collection = cases_collection

    def search(self, query: str) -> list[Product]:
        return search_products(self.list_products(), query)

    def get_product(self, sku: str) -> Product | None:
        clean = sku.strip().upper()
        if not clean:
            return None
        snapshot = self._products().document(clean).get()
        if not snapshot.exists:
            return None
        return _product_from_snapshot(snapshot)

    def list_products(self) -> list[Product]:
        products: list[Product] = []
        for snapshot in self._products().stream():
            products.append(_product_from_snapshot(snapshot))
        return products

    def create_case(self, draft: CaseDraft) -> SupportCase:
        case = new_case(draft)
        self._cases().document(case.case_id).set(case.to_dict())
        return case

    def get_case(self, case_id: str) -> SupportCase | None:
        snapshot = self._cases().document(case_id).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        data.setdefault("case_id", snapshot.id)
        return case_from_mapping(data)

    def list_cases(self) -> list[SupportCase]:
        cases: list[SupportCase] = []
        for snapshot in self._cases().stream():
            data = snapshot.to_dict() or {}
            data.setdefault("case_id", snapshot.id)
            cases.append(case_from_mapping(data))
        return cases

    def _products(self) -> _Collection:
        return self._client.collection(self._products_collection)

    def _cases(self) -> _Collection:
        return self._client.collection(self._cases_collection)


def build_firestore_store(project_id: str, database: str) -> FirestoreCatalogStore:
    client = firestore.Client(project=project_id, database=database)
    return FirestoreCatalogStore(client)


def _product_from_snapshot(snapshot: _Snapshot) -> Product:
    data = snapshot.to_dict() or {}
    return product_from_mapping(data, sku=snapshot.id)
