"""IO helpers: parquet fallback, manifests, resume index, path helpers."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pandas as pd

from .config import RunConfig


def data_extension(out_format: str, compression: str | None) -> str:
    """Return file extension (without leading dot) for format + compression."""

    if out_format == "csv":
        return "csv.gz" if compression == "gzip" else "csv"
    return "parquet"


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


def write_frame(df: pd.DataFrame, path: Path, out_format: str, *, compression: str | None) -> Path:
    """Write dataframe to file, with parquet fallback to CSV."""

    if out_format == "parquet":
        eng = _parquet_engine()
        if eng:
            df.to_parquet(path, index=False, engine=eng, compression=compression)  # type: ignore[call-overload]
            return path

        logging.warning(
            "Parquet engine not found (install pyarrow or fastparquet). "
            "Falling back to CSV for this chunk: %s",
            path.with_name(f"{path.stem}.{data_extension('csv', compression)}"),
        )
        csv_name = f"{path.stem}.{data_extension('csv', compression)}"
        csv_path = path.with_name(csv_name)
        df.to_csv(csv_path, index=False, compression=compression)
        return csv_path

    df.to_csv(path, index=False, compression=compression)
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


def make_paths(cfg: RunConfig, mode_label: str, wid: str, chunk_no: int) -> tuple[Path, Path, Path]:
    """Compute base_dir, data_path, manifest_path based on layout."""
    year, month, day = _split_wid(wid)
    data_ext = data_extension(cfg.out_format, cfg.compression)

    if cfg.layout == "nested":
        base_dir = cfg.out_root / mode_label / wid
        fname = f"{wid}_chunk_{chunk_no:04d}.{data_ext}"
    elif cfg.layout == "mode-flat":
        base_dir = cfg.out_root / mode_label
        fname = f"{wid}_chunk_{chunk_no:04d}.{data_ext}"
    elif cfg.layout == "flat":
        base_dir = cfg.out_root
        fname = f"{mode_label}_{wid}_chunk_{chunk_no:04d}.{data_ext}"
    elif cfg.layout == "ymd":
        if day:
            base_dir = cfg.out_root / mode_label / year / month / day
        else:
            base_dir = cfg.out_root / mode_label / year / month
        fname = f"{wid}_chunk_{chunk_no:04d}.{data_ext}"
    else:
        base_dir = cfg.out_root / mode_label / wid
        fname = f"{wid}_chunk_{chunk_no:04d}.{data_ext}"

    data_path = base_dir / fname
    suffix = f".{data_ext}"
    manifest_base = fname[: -len(suffix)] if fname.endswith(suffix) else fname
    manifest_path = base_dir / f"{manifest_base}.manifest.json"
    return base_dir, data_path, manifest_path


def resume_index_for_layout(
    base_dir: Path,
    wid: str,
    mode_label: str,
    out_format: str,
    layout: str,
    compression: str | None,
) -> int:
    """Count existing chunk files for a window, accounting for layout.

    If ``out_format`` is ``"parquet"`` we also consider ``*.csv`` files to
    support environments without a parquet engine, where ``write_frame`` falls
    back to CSV but the run configuration still advertises parquet output.
    """

    def _patterns(ext: str) -> str:
        if layout in ("nested", "ymd"):
            return f"*chunk_*.{ext}"
        if layout == "mode-flat":
            return f"{wid}_chunk_*.{ext}"
        if layout == "flat":
            return f"{mode_label}_{wid}_chunk_*.{ext}"
        return f"*chunk_*.{ext}"

    primary_ext = data_extension(out_format, compression)
    patterns = [_patterns(primary_ext)]
    if out_format == "parquet":
        patterns.append(_patterns(data_extension("csv", compression)))

    if not base_dir.exists():
        return 0

    files: list[Path] = []
    for patt in patterns:
        files.extend(base_dir.glob(patt))
    files.sort()
    return len(files)


def resume_index(dir_: Path, prefix: str | None, *, out_format: str, compression: str | None) -> int:
    """Count existing chunk files for full mode."""

    primary_ext = data_extension(out_format, compression)
    csv_ext = data_extension("csv", compression)

    patterns = []
    if prefix:
        patterns = [f"{prefix}_chunk_*.{primary_ext}"]
    else:
        patterns = [f"chunk_*.{primary_ext}"]

    if out_format == "parquet":
        patterns.append(f"{prefix + '_' if prefix else ''}chunk_*.{csv_ext}")

    files: list[Path] = []
    for pat in patterns:
        files += list(dir_.glob(pat))
    files.sort()
    return len(files)
