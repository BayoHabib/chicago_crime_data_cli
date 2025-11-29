"""IO helpers: parquet fallback, manifests, resume index, path helpers."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pandas as pd

from .config import RunConfig


def _data_suffix(out_format: str, compression: str | None) -> str:
    """Return file suffix (including dot) for desired format/compression."""
    if out_format == "csv":
        return ".csv.gz" if compression == "gzip" else ".csv"
    return ".parquet"


def _suffix_candidates(out_format: str, compression: str | None) -> list[str]:
    """Ordered list of suffixes to look for when resuming writes."""
    primary = _data_suffix(out_format, compression)
    extras: set[str]
    if out_format == "csv":
        extras = {".csv", ".csv.gz"}
    else:
        extras = {".parquet"}
    ordered = [primary]
    for extra in sorted(extras):
        if extra != primary:
            ordered.append(extra)
    return ordered


def _parquet_engine() -> str | None:
    """Detect available parquet engine (pyarrow or fastparquet)."""
    try:
        import pyarrow  # noqa: F401

        return "pyarrow"
    except Exception:
        try:
            import fastparquet  # noqa: F401

            return "fastparquet"
        except Exception:
            return None


def write_frame(
    df: pd.DataFrame, path: Path, out_format: str, compression: str | None = None
) -> Path:
    """Write dataframe to disk, honoring compression and parquet fallback."""
    if out_format == "parquet":
        eng = _parquet_engine()
        if eng:
            kwargs: dict[str, str] = {}
            if compression:
                kwargs["compression"] = compression
            df.to_parquet(path, index=False, engine=eng, **kwargs)  # type: ignore[call-overload]
            return path
        else:
            logging.warning(
                "Parquet engine not found (install pyarrow or fastparquet). "
                "Falling back to CSV for this chunk: %s",
                path.with_suffix(".csv"),
            )
            csv_path = path.with_suffix(".csv")
            if compression == "gzip":
                csv_path = csv_path.with_suffix(".csv.gz")
                df.to_csv(csv_path, index=False, compression="gzip")
            else:
                df.to_csv(csv_path, index=False)
            return csv_path
    else:
        if compression == "gzip":
            df.to_csv(path, index=False, compression="gzip")
        else:
            df.to_csv(path, index=False)
        return path


def sha256_of_file(path: Path) -> str:
    """Compute SHA256 of file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(
    manifest_path: Path,
    *,
    data_path: Path,
    params: dict[str, str],
    rows: int,
    started: float,
    finished: float,
    compression: str | None = None,
) -> None:
    """Write JSON manifest for a chunk."""
    from datetime import datetime

    from .config import BASE_URL

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
        "compression": compression or "none",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def ensure_dir(p: Path) -> None:
    """Create directory (with parents)."""
    p.mkdir(parents=True, exist_ok=True)


def _split_wid(wid: str) -> tuple[str, str, str | None]:
    """Split window ID into year, month, day components."""
    parts = wid.split("-")
    year, month = parts[0], parts[1]
    day = parts[2] if len(parts) == 3 else None
    return year, month, day


def make_paths(
    cfg: RunConfig, mode_label: str, wid: str, chunk_no: int
) -> tuple[Path, Path, Path]:
    """Compute base_dir, data_path, manifest_path based on layout."""
    year, month, day = _split_wid(wid)
    compression = getattr(cfg, "compression", None)
    suffix = _data_suffix(cfg.out_format, compression)

    if cfg.layout == "nested":
        base_dir = cfg.out_root / mode_label / wid
        base_name = f"{wid}_chunk_{chunk_no:04d}"
    elif cfg.layout == "mode-flat":
        base_dir = cfg.out_root / mode_label
        base_name = f"{wid}_chunk_{chunk_no:04d}"
    elif cfg.layout == "flat":
        base_dir = cfg.out_root
        base_name = f"{mode_label}_{wid}_chunk_{chunk_no:04d}"
    elif cfg.layout == "ymd":
        if day:
            base_dir = cfg.out_root / mode_label / year / month / day
        else:
            base_dir = cfg.out_root / mode_label / year / month
        base_name = f"{wid}_chunk_{chunk_no:04d}"
    else:
        base_dir = cfg.out_root / mode_label / wid
        base_name = f"{wid}_chunk_{chunk_no:04d}"

    data_path = base_dir / f"{base_name}{suffix}"
    manifest_path = base_dir / f"{base_name}.manifest.json"
    return base_dir, data_path, manifest_path


def resume_index_for_layout(
    base_dir: Path,
    wid: str,
    mode_label: str,
    out_format: str,
    layout: str,
    compression: str | None = None,
) -> int:
    """Count existing chunk files for a window, accounting for layout."""
    suffixes = _suffix_candidates(out_format, compression)
    patterns: list[str] = []
    for suffix in suffixes:
        if layout in ("nested", "ymd"):
            patt = f"*chunk_*{suffix}"
        elif layout == "mode-flat":
            patt = f"{wid}_chunk_*{suffix}"
        elif layout == "flat":
            patt = f"{mode_label}_{wid}_chunk_*{suffix}"
        else:
            patt = f"*chunk_*{suffix}"
        patterns.append(patt)

    files: list[Path] = []
    if base_dir.exists():
        for patt in patterns:
            files.extend(base_dir.glob(patt))
    files.sort()
    return len(files)


def resume_index(
    dir_: Path,
    prefix: str | None = None,
    *,
    out_format: str | None = None,
    compression: str | None = None,
) -> int:
    """Count existing chunk files, optionally constrained by format/compression."""
    if out_format is None:
        suffixes = [".parquet", ".csv", ".csv.gz"]
    else:
        suffixes = _suffix_candidates(out_format, compression)

    files: list[Path] = []
    if prefix:
        for suffix in suffixes:
            files.extend(dir_.glob(f"{prefix}_chunk_*{suffix}"))
    else:
        for suffix in suffixes:
            files.extend(dir_.glob(f"chunk_*{suffix}"))

    files.sort()
    return len(files)
