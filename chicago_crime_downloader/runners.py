"""Run modes: offset (full) and windowed (daily/monthly/weekly)."""
from __future__ import annotations
import logging
import time
from typing import List, Tuple, Optional, Dict
from datetime import date

import pandas as pd

from .config import RunConfig, HttpConfig
from .http_client import safe_request, probe_count_for_day
from .io_utils import (
    make_paths,
    ensure_dir,
    write_frame,
    write_manifest,
    resume_index,
    resume_index_for_layout,
)
from .soql import soql_params, soql_params_window

stop_requested = False


def run_offset_mode(
    cfg: RunConfig, http: HttpConfig, headers: Dict[str, str], select: Optional[str]
) -> None:
    """Download using single $offset pagination (full mode)."""
    window_id = (
        "all"
        if not (cfg.start_date or cfg.end_date)
        else f"{(cfg.start_date or '0000-00-00')}_to_{(cfg.end_date or '9999-12-31')}"
    )
    base_dir = cfg.out_root / "full" / window_id
    ensure_dir(base_dir)

    start_idx = resume_index(base_dir, prefix=None)
    offset = start_idx * cfg.chunk_size
    chunk_no = start_idx + 1

    logging.info(f"🔍 Resume: found {start_idx} existing chunk(s).")
    if cfg.start_date or cfg.end_date:
        logging.info(f"📅 Filter: start={cfg.start_date or 'NONE'} end={cfg.end_date or 'NONE'}")

    while True:
        global stop_requested
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
        write_manifest(
            manifest_path, data_path=data_path, params=params, rows=len(df), started=t0, finished=t1
        )
        logging.info(f"💾 Saved {len(df):,} rows → {data_path.name}")

        if len(df) < cfg.chunk_size:
            logging.info("✅ Last partial chunk received (done).")
            break

        offset += cfg.chunk_size
        chunk_no += 1
        time.sleep(http.sleep)


def run_windowed_mode(
    cfg: RunConfig,
    http: HttpConfig,
    headers: Dict[str, str],
    select: Optional[str],
    windows: List[Tuple[date, date, str]],
    mode_label: str,
) -> None:
    """Download using windowed queries (monthly/weekly/daily)."""
    for s, e, wid in windows:
        global stop_requested
        if stop_requested:
            logging.warning("Stopping gracefully.")
            break

        # Preflight only for daily mode if enabled
        do_preflight = (mode_label == "daily") and getattr(cfg, "preflight", False)
        if do_preflight:
            cnt = probe_count_for_day(s, headers, http)
            logging.info(f"📊 [{wid}] Published rows: {cnt:,}")
            if cnt == 0:
                logging.info(f"⏭️  [{wid}] Skipping fetch (0 rows published yet).")
                continue

        base_dir, _, _ = make_paths(cfg, mode_label, wid, 1)
        base_dir_existed = base_dir.exists()
        wrote_any = False
        created_this_run = False

        start_idx = (
            resume_index_for_layout(base_dir, wid, mode_label, cfg.out_format, cfg.layout)
            if base_dir_existed
            else 0
        )

        offset = start_idx * cfg.chunk_size
        chunk_no = start_idx + 1

        logging.info(f"\n🗂️  Window {wid}: {s} → {e} | existing chunks: {start_idx}")

        while True:
            if stop_requested:
                logging.warning("Stopping gracefully.")
                return

            base_dir, data_path, manifest_path = make_paths(cfg, mode_label, wid, chunk_no)

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

            if not base_dir.exists():
                ensure_dir(base_dir)
                created_this_run = True

            df = pd.DataFrame(data)
            actual_path = write_frame(df, data_path, cfg.out_format)
            t1 = time.time()
            write_manifest(
                manifest_path,
                data_path=actual_path,
                params=params,
                rows=len(df),
                started=t0,
                finished=t1,
            )
            logging.info(f"💾 [{wid}] Saved {len(df):,} rows → {actual_path.name}")
            wrote_any = True

            if len(df) < cfg.chunk_size:
                logging.info(f"✅ [{wid}] Last partial chunk (window complete).")
                break

            offset += cfg.chunk_size
            chunk_no += 1
            time.sleep(http.sleep)

        if created_this_run and not wrote_any:
            try:
                if base_dir.exists() and not any(base_dir.iterdir()):
                    base_dir.rmdir()
                    logging.info(f"🧹 Removed empty dir: {base_dir}")
            except Exception:
                pass
