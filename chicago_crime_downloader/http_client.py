"""HTTP helpers: safe_request (with retries/backoff), headers helper, probe_count_for_day."""
from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from typing import Any

import requests

from .config import BASE_URL, HttpConfig


def headers_with_token(http: HttpConfig) -> dict[str, str]:
    """Build HTTP headers with optional App Token."""
    token = os.getenv("SOC_APP_TOKEN") or os.getenv("SOCRATA_APP_TOKEN")
    headers = {"User-Agent": http.user_agent}
    if token:
        headers["X-App-Token"] = token
        logging.info("🔑 Using App Token for higher rate limits.")
    else:
        logging.warning("⚠️  No App Token found. Set SOC_APP_TOKEN for better performance.")
    return headers


def safe_request(
    params: dict[str, str], headers: dict[str, str], http: HttpConfig
) -> list[dict[str, Any]]:
    """Execute HTTP GET with retry logic and backoff."""
    backoff = 2
    for attempt in range(1, http.retries + 1):
        try:
            r = requests.get(BASE_URL, params=params, headers=headers, timeout=http.timeout)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", backoff))
                logging.warning(f"⏳ 429 Rate limited. Sleeping {wait}s…")
                time.sleep(wait)
                backoff = min(backoff * 2, 60)
                continue
            r.raise_for_status()
            return r.json()  # type: ignore[no-any-return]
        except requests.RequestException as e:
            logging.warning(f"Attempt {attempt}/{http.retries} failed: {e}")
            if attempt == http.retries:
                raise
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
    return []


def probe_count_for_day(
    d: date, headers: dict[str, str], http: HttpConfig | None = None
) -> int:
    """Get row count published for a given day via SoQL count query."""
    s = f"{d:%Y-%m-%d}T00:00:00.000"
    e = f"{(d + timedelta(days=1)):%Y-%m-%d}T00:00:00.000"
    params = {"$select": "count(1)", "$where": f"date >= '{s}' AND date < '{e}'"}

    try:
        hc = http or HttpConfig()
        j = safe_request(params, headers, hc)
        if not j or not isinstance(j, list) or not j:
            return 0
        row = j[0] if isinstance(j[0], dict) else {}
        val = row.get("count_1") or row.get("count") or 0
        return int(val)
    except Exception:
        return 0
