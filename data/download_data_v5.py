#!/usr/bin/env python3
"""
Chicago Crime Data - Production-Ready Downloader (SoQL + Token)
===============================================================

Modes:
  - full     : single $offset pagination (resumable by global chunk index)
  - monthly  : month-by-month windows (deterministic)
  - daily    : day-by-day windows (deterministic, backtesting-friendly)

New (v5):
  - --out-root, --out-format {csv,parquet}
  - per-window partitioning: out_root/<mode>/<window>/chunk_XXXX.{csv|parquet}
  - manifests: JSON sidecar per chunk with sha256, row_count, timings, params
  - column projection: --select "col1,col2,..." or --columns-file path.txt
  - structured logging; optional JSON logs; file + console
  - configurable HTTP: user-agent, timeout, retries, polite sleep
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import re
import calendar

# -----------------------
# Constants
# -----------------------

BASE_URL = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"  # SoQL JSON
DEFAULT_SLEEP = 1.0
DEFAULT_CHUNK = 50_000
DEFAULT_TIMEOUT = 300
DEFAULT_RETRIES = 4

# -----------------------
# Logging (console + file, optional JSON)
# -----------------------

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

def setup_logging(log_file: Optional[str], json_logs: bool):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    fmt = JsonFormatter() if json_logs else logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_file:
        # ensure parent dir exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

# -----------------------
# Config + State
# -----------------------

@dataclass
class HttpConfig:
    timeout: int = DEFAULT_TIMEOUT
    retries: int = DEFAULT_RETRIES
    sleep: float = DEFAULT_SLEEP
    user_agent: str = "crime-downloader/1.0 (+mlops)"

@dataclass
class RunConfig:
    mode: str
    out_root: Path
    out_format: str
    chunk_size: int
    max_chunks: Optional[int]
    start_date: Optional[str]
    end_date: Optional[str]
    select: Optional[str]
    columns_file: Optional[Path]
    layout: str = "nested"        # NEW: selected layout
    no_preflight: bool = False    # NEW: skip daily count probe


stop_requested = False
def _sigint_handler(signum, frame):
    global stop_requested
    stop_requested = True
    logging.warning("CTRL-C received; will stop after current chunk.")

signal.signal(signal.SIGINT, _sigint_handler)

# -----------------------
# Utils
# -----------------------

def headers_with_token(http: HttpConfig) -> Dict[str, str]:
    token = os.getenv("SOC_APP_TOKEN") or os.getenv("SOCRATA_APP_TOKEN")
    headers = {"User-Agent": http.user_agent}
    if token:
        headers["X-App-Token"] = token
        logging.info("🔑 Using App Token for higher rate limits.")
    else:
        logging.warning("⚠️  No App Token found. Set SOC_APP_TOKEN for better performance.")
    return headers

def load_select(select: Optional[str], columns_file: Optional[Path]) -> Optional[str]:
    if columns_file:
        cols = [ln.strip() for ln in columns_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if cols:
            return ",".join(cols)
    if select:
        return ",".join([c.strip() for c in select.split(",") if c.strip()])
    return None

def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _last_day_of_month(y: int, m: int) -> int:
    return calendar.monthrange(y, m)[1]


def parse_date(d: Optional[str], *, role: str = "date") -> Optional[date]:
    """
    Parse YYYY-MM-DD robustly.
    - If day is out of range (e.g., 2020-04-31), coerce to last day (2020-04-30) and WARN.
    - If None, return None.
    """
    if not d:
        return None

    # Strict pattern check
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        raise ValueError(f"Invalid {role!r} format {d!r}. Expected YYYY-MM-DD.")

    y, m, day = map(int, d.split("-"))
    last = _last_day_of_month(y, m)
    if day > last:
        logging.warning(f"⚠️  {role} {d} is out of range; using {y:04d}-{m:02d}-{last:02d} instead.")
        day = last
    return date(y, m, day)
def month_windows(start: date, end: date) -> List[Tuple[date, date, str]]:
    wins = []
    cur = date(start.year, start.month, 1)
    # clamp end to last day of its month
    next_m = (date(end.year, end.month, 1) + timedelta(days=32)).replace(day=1)
    last_end = next_m - timedelta(days=1)
    while cur <= last_end:
        nm = (cur + timedelta(days=32)).replace(day=1)
        cur_end = nm - timedelta(days=1)
        if cur_end > end: cur_end = end
        win_id = f"{cur.year:04d}-{cur.month:02d}"
        win_start = max(cur, start)
        wins.append((win_start, cur_end, win_id))
        cur = nm
    return wins

def day_windows(start: date, end: date) -> List[Tuple[date, date, str]]:
    days = []
    cur = start
    while cur <= end:
        dstr = cur.strftime("%Y-%m-%d")
        days.append((cur, cur, dstr))
        cur += timedelta(days=1)
    return days
def week_windows(start: date, end: date) -> List[Tuple[date, date, str]]:
    """
    Build a list of (start_date, end_date, window_id) tuples per week.
    Weeks run Monday–Sunday (ISO week). The final window may be partial.
    """
    wins = []
    cur = start - timedelta(days=start.weekday())  # align to Monday
    while cur <= end:
        week_start = cur
        week_end = min(cur + timedelta(days=6), end)
        wid = f"{week_start:%Y}-W{week_start.isocalendar().week:02d}"
        wins.append((week_start, week_end, wid))
        cur += timedelta(days=7)
    return wins

def _utc_day_bounds(d: date) -> tuple[str, str]:
    """Return ISO8601 UTC bounds for a calendar day as a half-open interval."""
    start = f"{d:%Y-%m-%d}T00:00:00.000Z"
    # next day 00:00Z
    next_day = (d + timedelta(days=1))
    end_excl = f"{next_day:%Y-%m-%d}T00:00:00.000Z"
    return start, end_excl

def _soql_day_bounds(d: date) -> tuple[str, str]:
    """
    Return ISO8601 strings WITHOUT timezone for a half-open day window.
    SoQL on this dataset rejects 'Z' suffix; literals should be naive.
    """
    start = f"{d:%Y-%m-%d}T00:00:00.000"
    end_next = f"{(d + timedelta(days=1)):%Y-%m-%d}T00:00:00.000"
    return start, end_next

def _split_wid(wid: str):
    # wid is "YYYY-MM" (monthly) or "YYYY-MM-DD" (daily)
    parts = wid.split("-")
    year, month = parts[0], parts[1]
    day = parts[2] if len(parts) == 3 else None
    return year, month, day

def make_paths(cfg, mode_label: str, wid: str, chunk_no: int):
    year, month, day = _split_wid(wid)

    if cfg.layout == "nested":
        base_dir = cfg.out_root / mode_label / wid
        fname = f"{wid}_chunk_{chunk_no:04d}.{cfg.out_format}"
    elif cfg.layout == "mode-flat":
        base_dir = cfg.out_root / mode_label
        fname = f"{wid}_chunk_{chunk_no:04d}.{cfg.out_format}"
    elif cfg.layout == "flat":
        base_dir = cfg.out_root
        fname = f"{mode_label}_{wid}_chunk_{chunk_no:04d}.{cfg.out_format}"
    elif cfg.layout == "ymd":
        # monthly: YYYY/MM ; daily: YYYY/MM/DD
        if day:
            base_dir = cfg.out_root / mode_label / year / month / day
        else:
            base_dir = cfg.out_root / mode_label / year / month
        fname = f"{wid}_chunk_{chunk_no:04d}.{cfg.out_format}"
    else:
        # fallback to nested
        base_dir = cfg.out_root / mode_label / wid
        fname = f"{wid}_chunk_{chunk_no:04d}.{cfg.out_format}"

    data_path = base_dir / fname
    manifest_path = base_dir / (fname.replace(f".{cfg.out_format}", ".manifest.json"))
    return base_dir, data_path, manifest_path

# -----------------------
# HTTP
# -----------------------

def safe_request(params: Dict[str, str], headers: Dict[str, str], http: HttpConfig):
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
            return r.json()
        except requests.RequestException as e:
            logging.warning(f"Attempt {attempt}/{http.retries} failed: {e}")
            if attempt == http.retries:
                raise
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
    return []

# AFTER (robust)
def probe_count_for_day(d: date, headers: Dict[str, str], http: Optional[HttpConfig] = None) -> int:
    s = f"{d:%Y-%m-%d}T00:00:00.000"
    e = f"{(d + timedelta(days=1)):%Y-%m-%d}T00:00:00.000"
    params = {"$select": "count(1)", "$where": f"date >= '{s}' AND date < '{e}'"}

    try:
        # Reuse retry/backoff; if http is None, make a small default
        hc = http or HttpConfig()
        j = safe_request(params, headers, hc)  # returns [] on failure after retries
        if not j or not isinstance(j, list) or not j:
            return 0
        row = j[0] if isinstance(j[0], dict) else {}
        # Be lenient about the field name
        val = row.get("count_1") or row.get("count") or 0
        return int(val)
    except Exception:
        # Fail closed: assume 0 so we skip the day rather than crash the job
        return 0




# -----------------------
# SoQL Parameters
# -----------------------

def soql_params(offset: int, limit: int,
                start_date: Optional[str], end_date: Optional[str],
                select: Optional[str]) -> Dict[str, str]:
    params = {"$limit": str(limit), "$offset": str(offset), "$order": "date desc"}
    if select:
        params["$select"] = select

    if start_date and end_date:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        s_iso, _ = _soql_day_bounds(sd)
        e_next_iso = f"{(ed + timedelta(days=1)):%Y-%m-%d}T00:00:00.000"
        params["$where"] = f"date >= '{s_iso}' AND date < '{e_next_iso}'"
    elif start_date:
        sd = datetime.strptime(start_date, "%Y-%m-%d").date()
        s_iso, _ = _soql_day_bounds(sd)
        params["$where"] = f"date >= '{s_iso}'"
    elif end_date:
        ed = datetime.strptime(end_date, "%Y-%m-%d").date()
        e_next_iso = f"{(ed + timedelta(days=1)):%Y-%m-%d}T00:00:00.000"
        params["$where"] = f"date < '{e_next_iso}'"

    return params



def soql_params_window(offset: int, limit: int, start_d: date, end_d: date,
                       select: Optional[str]) -> Dict[str, str]:
    s_iso, _ = _soql_day_bounds(start_d)
    # end bound is the next day after end_d
    _, e_next_iso = _soql_day_bounds(end_d)
    e_next_iso = f"{(end_d + timedelta(days=1)):%Y-%m-%d}T00:00:00.000"

    params = {
        "$limit": str(limit),
        "$offset": str(offset),
        "$order": "date desc",
        "$where": f"date >= '{s_iso}' AND date < '{e_next_iso}'",
    }
    if select:
        params["$select"] = select
    return params


# -----------------------
# IO
# -----------------------
def _parquet_engine() -> Optional[str]:
    try:
        import pyarrow  # noqa: F401
        return "pyarrow"
    except Exception:
        try:
            import fastparquet  # noqa: F401
            return "fastparquet"
        except Exception:
            return None
def write_frame(df: pd.DataFrame, path: Path, out_format: str) -> Path:
    """
    Write dataframe. If parquet requested but no engine is available,
    transparently fall back to CSV and return the path actually written.
    """
    if out_format == "parquet":
        eng = _parquet_engine()
        if eng:
            df.to_parquet(path, index=False, engine=eng)
            return path
        else:
            logging.warning("Parquet engine not found (install pyarrow or fastparquet). "
                            "Falling back to CSV for this chunk: %s", path.with_suffix(".csv"))
            csv_path = path.with_suffix(".csv")
            df.to_csv(csv_path, index=False)
            return csv_path
    else:
        df.to_csv(path, index=False)
        return path

def write_manifest(manifest_path: Path, *, data_path: Path, params: Dict[str, str],
                   rows: int, started: float, finished: float):
    manifest = {
        "data_file": str(data_path),
        "rows": rows,
        "sha256": sha256_of_file(data_path) if data_path.exists() else None,
        "params": params,
        "started_at": datetime.fromtimestamp(started).isoformat(),
        "finished_at": datetime.fromtimestamp(finished).isoformat(),
        "duration_seconds": round(finished - started, 3),
        "endpoint": BASE_URL,
        "version": 5,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

# -----------------------
# Runners
# -----------------------

def resume_index(dir_: Path, prefix: Optional[str] = None) -> int:
    """
    Count existing chunk files to resume.
    - full mode uses filenames: chunk_XXXX.*
    - windowed modes use filenames: <prefix>_chunk_XXXX.*
    """
    patterns = []
    if prefix:
        patterns = [f"{prefix}_chunk_*.parquet", f"{prefix}_chunk_*.csv"]
    else:
        patterns = ["chunk_*.parquet", "chunk_*.csv"]

    files: List[Path] = []
    for pat in patterns:
        files += list(dir_.glob(pat))
    files.sort()
    return len(files)

def resume_index_for_layout(base_dir: Path, wid: str, mode_label: str, out_format: str, layout: str) -> int:
    if layout in ("nested", "ymd"):
        patt = f"*chunk_*.{out_format}"
    elif layout == "mode-flat":
        patt = f"{wid}_chunk_*.{out_format}"
    elif layout == "flat":
        patt = f"{mode_label}_{wid}_chunk_*.{out_format}"
    else:
        patt = f"*chunk_*.{out_format}"
    files = sorted(base_dir.glob(patt))
    return len(files)

def run_offset_mode(cfg: RunConfig, http: HttpConfig, headers: Dict[str, str], select: Optional[str]):
    window_id = "all" if not (cfg.start_date or cfg.end_date) else f"{(cfg.start_date or '0000-00-00')}_to_{(cfg.end_date or '9999-12-31')}"
    base_dir = cfg.out_root / "full" / window_id
    ensure_dir(base_dir)

    start_idx = resume_index(base_dir, prefix=None)  # count chunk_XXXX.* files
    offset = start_idx * cfg.chunk_size
    chunk_no = start_idx + 1

    logging.info(f"🔍 Resume: found {start_idx} existing chunk(s).")
    if cfg.start_date or cfg.end_date:
        logging.info(f"📅 Filter: start={cfg.start_date or 'NONE'} end={cfg.end_date or 'NONE'}")

    while True:
        if stop_requested:
            logging.warning("Stopping gracefully.")
            break
        if cfg.max_chunks and chunk_no > cfg.max_chunks:
            logging.info(f"🛑 Reached max chunks ({cfg.max_chunks}).")
            break

        data_path = base_dir / f"chunk_{chunk_no:04d}.{cfg.out_format}"
        manifest_path = base_dir / f"chunk_{chunk_no:04d}.manifest.json"
        if data_path.exists() and manifest_path.exists():
            logging.info(f"⏩ Skipping existing: {data_path.name}")
            offset += cfg.chunk_size
            chunk_no += 1
            continue

        params = soql_params(offset, cfg.chunk_size, cfg.start_date, cfg.end_date, select)
        logging.info(f"📦 Fetching offset={offset:,} limit={cfg.chunk_size:,}")
        t0 = time.time()
        try:
            data = safe_request(params, headers, http)
        except Exception as e:
            logging.error(f"❌ Error at offset {offset}: {e}")
            break
        if not data:
            logging.info("✅ No more data (done).")
            break

        df = pd.DataFrame(data)
        write_frame(df, data_path, cfg.out_format)
        t1 = time.time()
        write_manifest(manifest_path, data_path=data_path, params=params, rows=len(df), started=t0, finished=t1)
        logging.info(f"💾 Saved {len(df):,} rows → {data_path.name}")

        if len(df) < cfg.chunk_size:
            logging.info("✅ Last partial chunk received (done).")
            break

        offset += cfg.chunk_size
        chunk_no += 1
        time.sleep(http.sleep)

def run_windowed_mode(cfg: RunConfig, http: HttpConfig, headers: Dict[str, str],
                      select: Optional[str], windows: List[Tuple[date, date, str]], mode_label: str):
    """
    Windowed downloads (monthly/daily) with lazy directory creation and configurable layout.
    We only create the directory right before the first successful write for the window,
    so we never leave empty folders behind.
    """
    for s, e, wid in windows:
        if stop_requested:
            logging.warning("Stopping gracefully.")
            break

        # Preflight only for daily mode unless explicitly disabled
        do_preflight = (mode_label == "daily") and getattr(cfg, "preflight", False)
        if do_preflight:
            cnt = probe_count_for_day(s, headers, http)
            logging.info(f"📊 [{wid}] Published rows: {cnt:,}")
            if cnt == 0:
                logging.info(f"⏭️  [{wid}] Skipping fetch (0 rows published yet).")
                continue

        # Determine the base directory for this window given the selected layout
        # Use chunk_no=1 just to compute the base_dir for existence/resume checks
        base_dir, _, _ = make_paths(cfg, mode_label, wid, 1)
        base_dir_existed = base_dir.exists()
        wrote_any = False
        created_this_run = False

        # Resume index pattern depends on layout (file name patterns differ)
        start_idx = resume_index_for_layout(
            base_dir, wid, mode_label, cfg.out_format, cfg.layout
        ) if base_dir_existed else 0

        offset = start_idx * cfg.chunk_size
        chunk_no = start_idx + 1

        logging.info(f"\n🗂️  Window {wid}: {s} → {e} | existing chunks: {start_idx}")

        while True:
            if stop_requested:
                logging.warning("Stopping gracefully.")
                return

            # Compute paths for this exact chunk using the chosen layout
            base_dir, data_path, manifest_path = make_paths(cfg, mode_label, wid, chunk_no)

            # Skip if both artifacts already present (resumable)
            if data_path.exists() and manifest_path.exists():
                logging.info(f"⏩ Skipping existing: {data_path.name}")
                offset += cfg.chunk_size
                chunk_no += 1
                continue

            params = soql_params_window(offset, cfg.chunk_size, s, e, select)
            logging.info(f"📦 [{wid}] Fetching offset={offset:,} limit={cfg.chunk_size:,}")
            t0 = time.time()
            try:
                data = safe_request(params, headers, http)
            except Exception as ex:
                logging.error(f"❌ [{wid}] Error at offset {offset}: {ex}")
                # If we created the dir but wrote nothing and it's empty, prune it
                if created_this_run and not wrote_any:
                    try:
                        if base_dir.exists() and not any(base_dir.iterdir()):
                            base_dir.rmdir()
                            logging.info(f"🧹 Removed empty dir: {base_dir}")
                    except Exception:
                        pass
                break

            if not data:
                logging.info(f"✅ [{wid}] No more data for this window.")
                break

            # Ensure directory exists right before the first write
            if not base_dir.exists():
                ensure_dir(base_dir)
                created_this_run = True

            df = pd.DataFrame(data)
            actual_path = write_frame(df, data_path, cfg.out_format)  # supports parquet fallback
            t1 = time.time()
            write_manifest(manifest_path, data_path=actual_path, params=params,
                           rows=len(df), started=t0, finished=t1)
            logging.info(f"💾 [{wid}] Saved {len(df):,} rows → {actual_path.name}")
            wrote_any = True

            if len(df) < cfg.chunk_size:
                logging.info(f"✅ [{wid}] Last partial chunk (window complete).")
                break

            offset += cfg.chunk_size
            chunk_no += 1
            time.sleep(http.sleep)

        # Final cleanup if nothing got written and the directory is empty
        if created_this_run and not wrote_any:
            try:
                if base_dir.exists() and not any(base_dir.iterdir()):
                    base_dir.rmdir()
                    logging.info(f"🧹 Removed empty dir: {base_dir}")
            except Exception:
                pass


# -----------------------
# CLI
# -----------------------

def main():
    ap = argparse.ArgumentParser(description="Resumable Chicago Crime downloader (SoQL + Token) — v5.")
    ap.add_argument("--mode", choices=["full", "monthly", "weekly", "daily"], default="full",
                    help="full: single $offset run; monthly: per-month windows; weekly: per-week windows; daily: per-day windows.")

    ap.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK, help="Rows per chunk.")
    ap.add_argument("--max-chunks", type=int, default=None, help="[full mode] Optional cap on chunks this run.")
    ap.add_argument("--start-date", type=str, default=None, help="YYYY-MM-DD (optional)")
    ap.add_argument("--end-date", type=str, default=None, help="YYYY-MM-DD (optional)")

    ap.add_argument("--out-root", type=Path, default=Path("data/raw"), help="Root output directory.")
    ap.add_argument("--out-format", choices=["csv", "parquet"], default="csv", help="Output file format.")

    ap.add_argument("--select", type=str, default=None, help="Comma-separated columns to project at source.")
    ap.add_argument("--columns-file", type=Path, default=None, help="Text file with one column name per line.")

    ap.add_argument("--http-timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout seconds.")
    ap.add_argument("--max-retries", type=int, default=DEFAULT_RETRIES, help="HTTP retries on failure.")
    ap.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="Sleep seconds between successful chunks.")
    ap.add_argument("--user-agent", type=str, default="crime-downloader/1.0 (+mlops)")

    ap.add_argument("--log-file", type=str, default=None, help="Optional log file path.")
    ap.add_argument("--log-json", action="store_true", help="Emit JSON logs.")

    ap.add_argument(
        "--preflight",
        action="store_true",
        help="Enable a daily preflight 'count(1)' check and skip days with 0 published rows."
    )

    # Make layout truly optional: infer if user didn’t specify it
    ap.add_argument(
        "--layout",
        choices=["nested", "mode-flat", "flat", "ymd"],
        default=None,
        help=("Optional output layout. "
              "nested=<root>/<mode>/<window>, "
              "mode-flat=<root>/<mode>, "
              "flat=<root>, "
              "ymd=<root>/<mode>/<yyyy>/<mm>/<dd>.")
    )
    args = ap.parse_args()

    # logging (auto-create parent dir for log file)
    setup_logging(args.log_file, args.log_json)

    # Build HTTP config (argparse turns dashes into underscores)
    http = HttpConfig(
        timeout=args.http_timeout,
        retries=args.max_retries,
        sleep=args.sleep,
        user_agent=args.user_agent
    )

    # Infer layout when not provided:
    # - If out_root’s name ends with the mode (e.g. raw_daily & mode=daily), prefer "mode-flat"
    # - Otherwise default to "nested"
    if args.layout is None:
        root_name = args.out_root.name.lower()
        inferred_layout = "mode-flat" if root_name.endswith(args.mode) else "nested"
    else:
        inferred_layout = args.layout

    select = load_select(args.select, args.columns_file)

    cfg = RunConfig(
        mode=args.mode,
        out_root=args.out_root,
        out_format=args.out_format,
        chunk_size=args.chunk_size,
        max_chunks=args.max_chunks,
        start_date=args.start_date,
        end_date=args.end_date,
        select=select,
        columns_file=args.columns_file,
    )
    # attach optional flags/derived settings as attributes
    cfg.preflight = args.preflight
    cfg.layout = inferred_layout

    headers = headers_with_token(http)

    if cfg.mode == "full":
        run_offset_mode(cfg, http, headers, select)
    else:
        start_d = parse_date(cfg.start_date, role="start-date") or date(2001, 1, 1)
        end_d = parse_date(cfg.end_date, role="end-date") or date.today()

        if start_d > end_d:
            logging.error("start-date is after end-date.")
            sys.exit(2)

        if cfg.mode == "monthly":
            wins = month_windows(start_d, end_d)
            run_windowed_mode(cfg, http, headers, select, wins, "monthly")
        elif cfg.mode == "weekly":
            wins = week_windows(start_d, end_d)
            run_windowed_mode(cfg, http, headers, select, wins, "weekly")
        else:
            wins = day_windows(start_d, end_d)
            run_windowed_mode(cfg, http, headers, select, wins, "daily")


if __name__ == "__main__":
    main()
