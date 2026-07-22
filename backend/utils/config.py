"""Single place environment configuration is read. LLM_MODEL and API_KEY
are required with no hardcoded default; everything else falls back to the
defaults documented in CLAUDE.md.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    llm_model: str
    api_key: str
    max_concurrency: int
    long_ticket_word_limit: int
    max_upload_size: int
    request_timeout: float
    summary_model: str
    log_level: str


def _env(name: str, default: str) -> str:
    """os.environ.get(name, default) only falls back on a MISSING key; an
    empty string (e.g. `MAX_UPLOAD_SIZE=` in .env.example) would otherwise
    fail int()/float() conversion instead of using the default."""
    return os.environ.get(name) or default


def load_config() -> Config:
    llm_model = os.environ["LLM_MODEL"]
    return Config(
        llm_model=llm_model,
        api_key=os.environ["API_KEY"],
        max_concurrency=int(_env("MAX_CONCURRENCY", "5")),
        long_ticket_word_limit=int(_env("LONG_TICKET_WORD_LIMIT", "300")),
        # 5 MB default — CLAUDE.md leaves this implementation-defined.
        max_upload_size=int(_env("MAX_UPLOAD_SIZE", "5000000")),
        request_timeout=float(_env("REQUEST_TIMEOUT", "30")),
        summary_model=os.environ.get("SUMMARY_MODEL") or llm_model,
        log_level=_env("LOG_LEVEL", "INFO"),
    )
