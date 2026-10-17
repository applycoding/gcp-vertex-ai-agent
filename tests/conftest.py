"""Keep the suite off live Google APIs even if the shell has project env vars."""

from __future__ import annotations

import os

os.environ["MODEL_BACKEND"] = "local"
os.environ["STORE_BACKEND"] = "memory"
os.environ["SECRET_MANAGER_ENABLED"] = "false"
os.environ["CLOUD_LOGGING_CLIENT"] = "false"
os.environ.pop("AGENT_SYSTEM_PROMPT", None)
