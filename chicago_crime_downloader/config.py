"""Configuration dataclasses et constantes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BASE_URL = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"
DEFAULT_SLEEP = 1.0
DEFAULT_CHUNK = 50_000
DEFAULT_TIMEOUT = 300
DEFAULT_RETRIES = 4


@dataclass
class HttpConfig:
    """HTTP client configuration."""

    timeout: int = DEFAULT_TIMEOUT
    retries: int = DEFAULT_RETRIES
    sleep: float = DEFAULT_SLEEP
    user_agent: str = "crime-downloader/1.0 (+mlops)"


@dataclass
class RunConfig:
    """Download run configuration."""

    mode: str
    out_root: Path
    out_format: str
    chunk_size: int
    max_chunks: int | None
    start_date: str | None
    end_date: str | None
    select: str | None
    columns_file: Path | None
    layout: str = "nested"
    preflight: bool = False
