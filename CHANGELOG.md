# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2025-11-09

### Major Refactoring ✨

This release represents a complete modularization of the chicago-crime-downloader codebase.

#### Added

- **Modular Architecture**: Extracted monolithic script into 9 clean, reusable modules:
  - `config.py`: HttpConfig and RunConfig dataclasses
  - `http_client.py`: HTTP requests with exponential backoff
  - `soql.py`: Query building and date window logic
  - `io_utils.py`: File I/O and path inference
  - `runners.py`: Orchestration for offset and windowed modes
  - `cli.py`: Argument parsing and layout inference
  - `logging_utils.py`: Structured JSON logging
  - `version.py`: Version management
  - `__init__.py`: Public API exports

- **Type Hints**: Full Python 3.11+ type annotations throughout codebase
- **CI/CD Workflows**: GitHub Actions for testing and releasing
  - `test.yml`: Matrix testing (3 OS × 2 Python versions)
  - `release.yml`: Automated PyPI publishing with trusted OIDC
  
- **Comprehensive Testing**:
  - 18 unit tests covering all major functions
  - 5 integration tests for end-to-end validation
  - All tests passing on GitHub Actions matrix

- **Documentation**:
  - `ARCHITECTURE.md`: Detailed module design and execution flow
  - `API.md`: Complete public API reference with examples
  - `CONTRIBUTING.md`: Developer setup and contribution guidelines
  - Improved `README.md` with better structure and examples

- **Layout Strategies**: Four output directory layouts
  - `nested`: `mode/date/YYYY-MM-DD_chunk_NNNN.csv` (default)
  - `mode-flat`: `YYYY-MM-DD_chunk_NNNN.csv`
  - `flat`: `root_mode_YYYY-MM-DD_chunk_NNNN.csv`
  - `ymd`: `mode/YYYY/MM/DD/YYYY-MM-DD_chunk_NNNN.csv`

- **Smart Preflight**: Skip zero-row days with `count(1)` API query
- **Resume Capability**: Automatic chunk tracking and resume on interruption
- **Structured Logging**: JSON manifests with SHA256, timing, and metadata
- **Better Error Handling**: Exponential backoff with configurable retries
- **Backward Compatibility**: Legacy `data/download_data_v5.py` shim script

#### Changed

- Minimum Python version: **3.11+** (required for union types `X | None`)
- Console script renamed: `crime-dl` → `chicago-crime-dl`
- Default output root: `crime_data/` → `data/raw`
- Chunk size default: 100,000 → 50,000 (better for memory)
- HTTP timeout: 60s → 30s (configurable)

#### Fixed

- HTTP 429 rate limiting: Now uses exponential backoff with configurable retries
- Date parsing: Auto-clamps invalid dates (e.g., April 31 → April 30)
- Empty directories: No longer created for zero-row dates (with `--preflight`)
- Memory leaks: Proper resource cleanup in DataFrame operations

#### Removed

- Legacy monolithic `download_data.py` (replaced by modular approach)
- Hard-coded file paths (now layout-configurable)
- Manual date window logic (now automatic via generators)

#### Internal

- Linting with ruff (E, F, W, I, UP, D rules)
- Type checking with mypy (`ignore-missing-imports`, `disable-error-code=import-untyped`)
- 100% test coverage of public API
- Zero type: ignore pragmas except for known pandas/requests limitations

---

## [0.4.0] - 2024-XX-XX

### Previous Release

Earlier versions prior to complete modularization. See git history for details.

---

## Unreleased

### Planned Features

- Parallel window downloads (async/ThreadPoolExecutor)
- Streaming NDJSON output for real-time consumption
- Incremental snapshot detection
- S3/GCS direct upload
- Dask/Ray integration for 10+ year datasets
- Web UI dashboard for progress tracking
- dbt integration for data transformation pipelines

---

## Release Notes

### How to Upgrade

```bash
# From PyPI
pip install --upgrade chicago-crime-downloader

# From source
git clone https://github.com/BayoHabib/chicago_crime_data_cli.git
cd chicago_crime_data_cli
pip install -e ".[dev]"
```

### Breaking Changes

- **Python 3.11+ required** (was 3.8+)
- **Console script renamed**: Use `chicago-crime-dl` instead of `crime-dl`
- **Default output path changed**: Now `data/raw` (was `crime_data/`)
- **Column selection syntax unchanged**: Still `--select id,date,primary_type`

### Migration Guide

For existing users with custom scripts:

**Before (v0.4.0)**:
```bash
python data/download_data.py --mode daily --start-date 2020-01-01
```

**After (v0.5.0)**:
```bash
chicago-crime-dl --mode daily --start-date 2020-01-01
```

For programmatic use:

**Before**:
```python
import data.download_data_v5 as downloader
downloader.download(...)
```

**After**:
```python
from chicago_crime_downloader import main, HttpConfig, RunConfig

main(["--mode", "daily", "--start-date", "2020-01-01"])
```

---

## Contributors

- **Habib Bayo** — Original author and maintainer

---

## Resources

- **GitHub**: https://github.com/BayoHabib/chicago_crime_data_cli
- **PyPI**: https://pypi.org/project/chicago-crime-downloader/
- **API Docs**: https://data.cityofchicago.org/api/views/ijzp-q8t2
- **Issues**: https://github.com/BayoHabib/chicago_crime_data_cli/issues
