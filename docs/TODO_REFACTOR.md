# ✅ TODO — Refactor / Modularize Chicago Crime Downloader

**Branch:** `refactor/etl-modularization`  
**Scope:** Make the downloader maintainable, testable, and ready for future stages of the ETL (without changing current CLI behavior or outputs unless explicitly stated).

> **Definition of Done (overall):**
> - Code split into clear modules with type hints + docstrings.
> - Unit + integration tests pass on Windows/macOS/Linux (Python ≥3.11).
> - CLI flags and outputs remain backward-compatible.
> - README and docs updated; contributors can extend without fear.

---

## Phase 0 — Repo hygiene (setup once) ✅
- [x] Create `docs/TODO_REFACTOR.md` (this file) and keep it as the single source of truth.
- [x] Move docs to `docs/architecture/`.
- [x] Ensure project tree:
  ```
  repo_root/
  ├── data/                      # (scripts & datasets ignored by git as needed)
  ├── chicago_crime_downloader/  # NEW: package root
  ├── tests/
  │   ├── unit/
  │   └── integration/
  ├── docs/
  │   ├── TODO_REFACTOR.md
  │   └── architecture/
  ├── pyproject.toml
  ├── README.md
  └── LICENSE
  ```
- [x] Ensure `.gitignore` excludes `data/raw*`, caches, `.venv/`, and temp artifacts.
- [ ] Add lightweight `CONTRIBUTING.md` with local dev instructions and test policy.

**Accept:** `pytest` runs; contributors can follow docs to set up env and run tests.

---

## Phase 1 — Extract modules (no behavior change) ✅
### 1.1 Package skeleton
- [x] Create package folder `chicago_crime_downloader/` with:
  ```
  chicago_crime_downloader/
  ├── __init__.py           # exports all public symbols
  ├── cli.py                # argparse + main()
  ├── config.py             # HttpConfig, RunConfig
  ├── logging_utils.py      # setup_logging, JsonFormatter
  ├── http_client.py        # safe_request, headers_with_token, probe_count_for_day
  ├── soql.py               # parse_date, windows, soql_params
  ├── io_utils.py           # write_frame, write_manifest, path helpers
  ├── runners.py            # run_offset_mode, run_windowed_mode
  └── version.py            # version info
  ```
- [x] Move `download_data_v5.py` logic into these modules; keep a thin `data/download_data_v5.py` as a CLI shim that calls `chicago_crime_downloader.cli:main()`.

**Accept:** Running the old script still works the same (`python data/download_data_v5.py …`).

---

## Phase 2 — Tests (update + expand)
- [ ] Add and update all unit + integration tests.
- [ ] Ensure `pytest -m unit` and `pytest -m integration` both pass.
- [ ] Fix path layout expectations if needed.

---

## Phase 3 — CLI & UX polish
- [ ] Keep layout inference logic backward compatible.
- [ ] Validate weekly mode.
- [ ] Update help text and examples.

---

## Phase 4 — Documentation
- [ ] Update `README.md`, add `USAGE.md`, `DEVELOPER_NOTES.md`.
- [ ] Show layout examples and token instructions.

---

## Phase 5 — Code quality
- [ ] Add type hints; run `mypy`.
- [ ] Lint with `ruff` or `flake8`.
- [ ] Ensure graceful SIGINT handling.

---

## Phase 6 — Packaging polish
- [ ] Add console script entrypoint in `pyproject.toml`:
  ```toml
  [project.scripts]
  chicago-crime-dl = "chicago_crime_downloader.cli:main"
  ```
- [ ] Deprecate legacy script with notice.

---

## Quick PR Plan
- [ ] PR1: skeleton + logging/config ✅
- [ ] PR2: HTTP + SoQL + windows
- [ ] PR3: IO + runners
- [ ] PR4: CLI + packaging
- [ ] PR5: polish + docs

---

## Local Commands
```bash
pytest -m unit -q
pytest -m integration -q
pip install -e .
chicago-crime-dl --mode daily --start-date 2020-01-10 --end-date 2020-01-10 --out-root data/raw_daily --out-format csv
```
