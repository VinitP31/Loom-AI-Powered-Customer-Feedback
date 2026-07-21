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
    batch_size: int
    max_concurrency: int
    long_ticket_word_limit: int
    request_timeout: float
    summary_model: str
    log_level: str


def load_config() -> Config:
    llm_model = os.environ["LLM_MODEL"]
    return Config(
        llm_model=llm_model,
        api_key=os.environ["API_KEY"],
        batch_size=int(os.environ.get("BATCH_SIZE", 10)),
        max_concurrency=int(os.environ.get("MAX_CONCURRENCY", 5)),
        long_ticket_word_limit=int(os.environ.get("LONG_TICKET_WORD_LIMIT", 300)),
        request_timeout=float(os.environ.get("REQUEST_TIMEOUT", 30)),
        summary_model=os.environ.get("SUMMARY_MODEL") or llm_model,
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
