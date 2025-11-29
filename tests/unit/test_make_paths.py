import pytest

from chicago_crime_downloader.config import RunConfig
from chicago_crime_downloader.io_utils import make_paths, resume_index_for_layout


@pytest.mark.unit
@pytest.mark.parametrize(
    "layout, wid, mode_label, expected_base, expected_fname",
    [
        ("nested", "2024-01-02", "daily", "daily/2024-01-02", "2024-01-02_chunk_0001.csv"),
        ("mode-flat", "2024-01-02", "daily", "daily", "2024-01-02_chunk_0001.csv"),
        ("flat", "2024-01-02", "daily", ".", "daily_2024-01-02_chunk_0001.csv"),
        ("ymd", "2024-01-02", "daily", "daily/2024/01/02", "2024-01-02_chunk_0001.csv"),
        (
            "ymd",
            "2024-W05",
            "weekly",
            "weekly/2024/W05",
            "2024-W05_chunk_0001.csv",
        ),
    ],
)
def test_make_paths_variants(tmp_path, layout, wid, mode_label, expected_base, expected_fname):
    cfg = RunConfig(
        mode=mode_label,
        out_root=tmp_path,
        out_format="csv",
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
    assert manifest_path == base_dir / expected_fname.replace(".csv", ".manifest.json")


@pytest.mark.unit
@pytest.mark.parametrize(
    "layout, wid, mode_label, filenames, expected",
    [
        ("nested", "2024-01-02", "daily", ["2024-01-02_chunk_0001.csv"], 1),
        ("mode-flat", "2024-01-02", "daily", ["2024-01-02_chunk_0001.csv"], 1),
        (
            "flat",
            "2024-01-02",
            "daily",
            ["daily_2024-01-02_chunk_0001.csv", "daily_2024-01-02_chunk_0002.csv"],
            2,
        ),
        ("ymd", "2024-W05", "weekly", ["2024-W05_chunk_0001.csv"], 1),
    ],
)
def test_resume_index_for_layout(tmp_path, layout, wid, mode_label, filenames, expected):
    cfg = RunConfig(
        mode=mode_label,
        out_root=tmp_path,
        out_format="csv",
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

    count = resume_index_for_layout(base_dir, wid, mode_label, "csv", layout)
    assert count == expected
