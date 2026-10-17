"""Small extractors shared by the local router and the tool layer."""

from __future__ import annotations

import re

from app.catalog import STOPWORDS

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SKU_RE = re.compile(r"\b[A-Za-z]{2,3}-\d{1,4}\b")
_TOKEN = re.compile(r"[a-z0-9-]+")


def extract_email(text: str) -> str | None:
    match = EMAIL_RE.search(text)
    if match is None:
        return None
    return match.group(0)


def extract_sku(text: str) -> str | None:
    match = SKU_RE.search(text)
    if match is None:
        return None
    return match.group(0).upper()


def valid_email(value: str) -> bool:
    return EMAIL_RE.fullmatch(value) is not None


def content_tokens(text: str) -> list[str]:
    cleaned = EMAIL_RE.sub(" ", text)
    return [
        token
        for token in _TOKEN.findall(cleaned.lower())
        if token not in STOPWORDS and len(token) > 1
    ]


def strip_email(text: str) -> str:
    cleaned = EMAIL_RE.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def catalog_query(text: str) -> str:
    """Search text made of product words, without the customer's email."""

    tokens = content_tokens(text)
    if tokens:
        return " ".join(tokens)
    sku = extract_sku(text)
    if sku:
        return sku
    return strip_email(text)
