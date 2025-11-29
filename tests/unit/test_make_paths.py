import pytest

from chicago_crime_downloader.config import RunConfig
from chicago_crime_downloader.io_utils import make_paths, resume_index_for_layout


@pytest.mark.unit
@pytest.mark.parametrize(
    "layout, wid, mode_label, compression, expected_base, expected_fname, expected_manifest",
    [
        (
            "nested",
            "2024-01-02",
            "daily",
            None,
            "daily/2024-01-02",
            "2024-01-02_chunk_0001.csv",
            "2024-01-02_chunk_0001.manifest.json",
        ),
        (
            "mode-flat",
            "2024-01-02",
            "daily",
            None,
            "daily",
            "2024-01-02_chunk_0001.csv",
            "2024-01-02_chunk_0001.manifest.json",
        ),
        (
            "flat",
            "2024-01-02",
            "daily",
            None,
            ".",
            "daily_2024-01-02_chunk_0001.csv",
            "daily_2024-01-02_chunk_0001.manifest.json",
        ),
        (
            "ymd",
            "2024-01-02",
            "daily",
            None,
            "daily/2024/01/02",
            "2024-01-02_chunk_0001.csv",
            "2024-01-02_chunk_0001.manifest.json",
        ),
        (
            "ymd",
            "2024-W05",
            "weekly",
            None,
            "weekly/2024/W05",
            "2024-W05_chunk_0001.csv",
            "2024-W05_chunk_0001.manifest.json",
        ),
        (
            "nested",
            "2024-01-02",
            "daily",
            "gzip",
            "daily/2024-01-02",
            "2024-01-02_chunk_0001.csv.gz",
            "2024-01-02_chunk_0001.manifest.json",
        ),
    ],
)
def test_make_paths_variants(
    tmp_path, layout, wid, mode_label, compression, expected_base, expected_fname, expected_manifest
):
    cfg = RunConfig(
        mode=mode_label,
        out_root=tmp_path,
        out_format="csv",
        compression=compression,
        chunk_size=10,
        max_chunks=None,
        start_date=None,
        end_date=None,
        select=None,
        columns_file=None,
    )
    cfg.layout = layout

    base_dir, data_path, manifest_path = make_paths(cfg, mode_label, wid, 1)

    assert base_dir == tmp_path / expected_base
    assert data_path == base_dir / expected_fname
    assert manifest_path == base_dir / expected_manifest


@pytest.mark.unit
@pytest.mark.parametrize(
    "layout, wid, mode_label, filenames, out_format, compression, expected",
    [
        ("nested", "2024-01-02", "daily", ["2024-01-02_chunk_0001.csv"], "csv", None, 1),
        (
            "mode-flat",
            "2024-01-02",
            "daily",
            ["2024-01-02_chunk_0001.csv.gz"],
            "csv",
            "gzip",
            1,
        ),
        (
            "flat",
            "2024-01-02",
            "daily",
            ["daily_2024-01-02_chunk_0001.csv", "daily_2024-01-02_chunk_0002.csv"],
            "csv",
            None,
            2,
        ),
        ("ymd", "2024-W05", "weekly", ["2024-W05_chunk_0001.csv"], "csv", None, 1),
        (
            "nested",
            "2024-01-02",
            "daily",
            ["2024-01-02_chunk_0001.parquet", "2024-01-02_chunk_0002.csv"],
            "parquet",
            None,
            2,
        ),
    ],
)
def test_resume_index_for_layout(
    tmp_path, layout, wid, mode_label, filenames, out_format, compression, expected
):
    cfg = RunConfig(
        mode=mode_label,
        out_root=tmp_path,
        out_format=out_format,
        compression=compression,
        chunk_size=10,
        max_chunks=None,
        start_date=None,
        end_date=None,
        select=None,
        columns_file=None,
    )
    cfg.layout = layout

    base_dir, _, _ = make_paths(cfg, mode_label, wid, 1)
    base_dir.mkdir(parents=True, exist_ok=True)
    for fname in filenames:
        (base_dir / fname).write_text("dummy")
    # add a manifest to ensure it is ignored
    (base_dir / "ignored.manifest.json").write_text("{}")

    count = resume_index_for_layout(
        base_dir, wid, mode_label, out_format, layout, compression
    )
    assert count == expected
