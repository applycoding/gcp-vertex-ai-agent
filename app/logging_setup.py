"""Structured logs. Cloud Run ingests stdout JSON into Cloud Logging.

Set CLOUD_LOGGING_CLIENT=true to also attach the Cloud Logging client library.
That path is for processes that are not already captured by the platform.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from google.cloud import logging as cloud_logging

LOGGER_NAME = "northline"


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line, with the severity field Cloud Logging parses."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "time": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key not in payload:
                    payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def configure_logging(*, use_cloud_client: bool = False, cloud_client: Any | None = None) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    if use_cloud_client:
        logger.propagate = True
        client = cloud_client if cloud_client is not None else cloud_logging.Client()
        client.setup_logging(log_level=logging.INFO)
        return
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    logger.info(message, extra={"extra_fields": fields})
