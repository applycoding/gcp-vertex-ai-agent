"""Catalog store interface and the in-memory implementation."""

from __future__ import annotations

import threading
from typing import Protocol

from app.catalog import search_products, seed_products
from app.domain import CaseDraft, Product, SupportCase, new_case


class CatalogStore(Protocol):
    def search(self, query: str) -> list[Product]:
        """Return products that match query."""

    def get_product(self, sku: str) -> Product | None:
        """Return one product, or None when the SKU is unknown."""

    def list_products(self) -> list[Product]:
        """Return the whole catalog."""

    def create_case(self, draft: CaseDraft) -> SupportCase:
        """Persist a new open support case."""

    def get_case(self, case_id: str) -> SupportCase | None:
        """Return a support case, or None when the id is unknown."""

    def list_cases(self) -> list[SupportCase]:
        """Return support cases this store knows about."""


class MemoryStore:
    """Process-local catalog. The default backend for the demo and the tests."""

    def __init__(self, products: list[Product] | None = None) -> None:
        items = seed_products() if products is None else products
        self._products = {product.sku.upper(): product for product in items}
        self._cases: dict[str, SupportCase] = {}
        self._lock = threading.Lock()

    def search(self, query: str) -> list[Product]:
        return search_products(self.list_products(), query)

    def get_product(self, sku: str) -> Product | None:
        return self._products.get(sku.strip().upper())

    def list_products(self) -> list[Product]:
        return list(self._products.values())

    def create_case(self, draft: CaseDraft) -> SupportCase:
        case = new_case(draft)
        with self._lock:
            self._cases[case.case_id] = case
        return case

    def get_case(self, case_id: str) -> SupportCase | None:
        with self._lock:
            return self._cases.get(case_id)

    def list_cases(self) -> list[SupportCase]:
        with self._lock:
            return list(self._cases.values())
