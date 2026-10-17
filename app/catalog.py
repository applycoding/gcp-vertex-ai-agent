"""Seed catalog and the small in-process search used by both stores."""

from __future__ import annotations

import re

from app.domain import Product

# Words that show up in customer sentences and are not product terms.
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "in",
        "of",
        "for",
        "do",
        "you",
        "your",
        "have",
        "has",
        "stock",
        "stocks",
        "please",
        "me",
        "my",
        "and",
        "or",
        "to",
        "on",
        "it",
        "this",
        "that",
        "with",
        "about",
        "open",
        "create",
        "file",
        "case",
        "support",
        "restock",
        "want",
        "wanted",
        "need",
        "needs",
        "when",
        "how",
        "many",
        "available",
        "availability",
        "i",
        "we",
        "us",
        "our",
        "from",
        "if",
        "not",
        "out",
        "email",
        "address",
        "share",
        "check",
        "looking",
        "look",
        "show",
        "tell",
        "into",
        "can",
        "could",
        "would",
        "what",
        "which",
        "any",
        "some",
        "there",
        "thanks",
        "thank",
        "hi",
        "hello",
        "hey",
        "help",
        "just",
        "item",
        "product",
        "products",
        "catalog",
        "find",
    }
)

_TOKEN = re.compile(r"[a-z0-9-]+")
_RESULT_LIMIT = 8


def seed_products() -> list[Product]:
    """Five catalog rows used by the in-memory store and by tests."""

    return [
        Product(
            sku="TB-100",
            name="Trailblazer Softshell Jacket",
            description="Wind-resistant hooded jacket for wet ridgelines.",
            tags=["jacket", "outerwear"],
            price_cents=18900,
            stock=0,
        ),
        Product(
            sku="LN-220",
            name="Lumen Camp Lantern",
            description="Rechargeable lantern with a warm low mode.",
            tags=["light", "camp"],
            price_cents=6400,
            stock=24,
        ),
        Product(
            sku="PK-14",
            name="Packable Daypack",
            description="18-liter pack that stuffs into its own pocket.",
            tags=["pack", "hike"],
            price_cents=7200,
            stock=11,
        ),
        Product(
            sku="BT-88",
            name="Basecamp Two-Person Tent",
            description="Freestanding tent with a full-coverage rainfly.",
            tags=["tent", "camp"],
            price_cents=24900,
            stock=4,
        ),
        Product(
            sku="CP-3",
            name="Copper Camp Mug",
            description="Double-wall mug that stays cool at the rim.",
            tags=["camp", "mug"],
            price_cents=2800,
            stock=40,
        ),
    ]


def search_products(products: list[Product], query: str) -> list[Product]:
    """Match every meaningful token, then fall back to any token.

    Firestore has no full-text index in this demo, so both stores filter
    the catalog in process. That is fine for a few dozen products.
    """

    tokens = [token for token in _TOKEN.findall(query.lower()) if token not in STOPWORDS and len(token) > 1]
    if not tokens:
        return []
    ranked = [(product, _haystack(product)) for product in products]
    all_hits = [product for product, haystack in ranked if all(token in haystack for token in tokens)]
    if all_hits:
        return all_hits[:_RESULT_LIMIT]
    any_hits = [product for product, haystack in ranked if any(token in haystack for token in tokens)]
    return any_hits[:_RESULT_LIMIT]


def _haystack(product: Product) -> str:
    tags = " ".join(product.tags)
    return f"{product.sku} {product.name} {product.description} {tags}".lower()
