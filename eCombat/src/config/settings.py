"""
Application settings — all values are read from environment variables.

Load order:
  1. eCombat/.env  (loaded automatically by load_dotenv at import time)
  2. Actual shell environment variables (always override .env values)

Never hard-code secrets, URLs, or tokens in source code.
Add new variables here and document them in .env.example.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Bootstrap: load the .env file that lives inside the eCombat package dir
# ---------------------------------------------------------------------------
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=False)


# ---------------------------------------------------------------------------
# LLM / OpenRouter
# ---------------------------------------------------------------------------

OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
"""OpenRouter API key.  Get one at https://openrouter.ai/keys"""

SUPPORT_MODEL: str = "openrouter/google/gemini-2.5-flash"
PRODUCT_MODEL: str = "openrouter/microsoft/gpt-4-turbo-16k"
SALES_MODEL: str = "openrouter/anthropic/claude-sonnet-5"

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

POSTGRES_HOST: str = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT: int = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "ecombat")
POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD: str = os.environ.get("POSTGRES_PASSWORD", "postgres")


def postgres_dsn() -> str:
    """Return a libpq-compatible DSN string built from environment variables.

    Example return value::

        postgresql://postgres:secret@localhost:5432/ecombat
    """
    return (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )


# ---------------------------------------------------------------------------
# Redis (optional — only required when session caching is enabled)
# ---------------------------------------------------------------------------

REDIS_HOST: str = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB: int = int(os.environ.get("REDIS_DB", "0"))
REDIS_PASSWORD: str = os.environ.get("REDIS_PASSWORD", "redis")


def redis_url() -> str:
    """Return a Redis URL built from environment variables.

    Example return value::

        redis://:secret@localhost:6379/0
    """
    auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
    return f"redis://{auth}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"