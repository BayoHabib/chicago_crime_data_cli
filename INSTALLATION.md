# Installation Guide

Complete guide to installing and setting up chicago-crime-downloader.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation Methods](#installation-methods)
3. [Verification](#verification)
4. [Configuration](#configuration)
5. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements

- **Python**: 3.11 or higher
- **pip**: Latest version (≥23.0)
- **OS**: Windows, macOS, or Linux
- **Disk Space**: 500 MB (for package + dependencies)

### Optional Requirements

- **Parquet Engine**: Either `pyarrow` or `fastparquet` for `.parquet` export
- **API Token**: Socrata account for higher rate limits (recommended)

### Verify Python Version

```bash
python --version
# Output: Python 3.11.4

python3 --version  # On macOS/Linux
# Output: Python 3.11.4
```

If you have multiple Python versions, ensure `python3.11+` is in your PATH.

---

## Installation Methods

### Method 1: PyPI (Recommended)

Fastest installation from Python Package Index.

```bash
pip install chicago-crime-downloader
```

**Verify**:
```bash
chicago-crime-dl --version
# Output: 0.5.0
```

### Method 2: From Source (Development)

Clone repository for development or latest changes.

```bash
# Clone repository
git clone https://github.com/BayoHabib/chicago_crime_data_cli.git
cd chicago_crime_data_cli

# Install in editable mode
pip install -e .
```

### Method 3: From Source with Development Dependencies

Install with testing, linting, and documentation tools.

```bash
git clone https://github.com/BayoHabib/chicago_crime_data_cli.git
cd chicago_crime_data_cli

# Install with dev, test, and doc extras
pip install -e ".[dev]"

# Verify all tools installed
pytest --version
ruff --version
mypy --version
```

### Method 4: Virtual Environment (Recommended for Projects)

Isolate the package in a virtual environment to avoid conflicts.

```bash
# Create virtual environment
python -m venv crime_env
source crime_env/bin/activate  # On Windows: crime_env\Scripts\activate

# Install package
pip install chicago-crime-downloader

# Verify
chicago-crime-dl --help
```

### Method 5: Docker

Run in a Docker container (no local Python needed).

```dockerfile
FROM python:3.11-slim

RUN pip install chicago-crime-downloader

ENTRYPOINT ["chicago-crime-dl"]
```

Build and run:
```bash
docker build -t chicago-crime-downloader:0.5.0 .
docker run chicago-crime-downloader:0.5.0 --help
```

---

## Verification

### Basic Verification

```bash
# Check installation
chicago-crime-dl --version
# Output: 0.5.0

# Show help
chicago-crime-dl --help
```

### Full Verification

```bash
# Test with a small download
chicago-crime-dl \
  --mode daily \
  --start-date 2020-01-10 \
  --end-date 2020-01-10 \
  --max-chunks 1 \
  --out-root ./test_output

# Check output
ls -la test_output/
# Should contain: daily/2020-01-10/
```

### Run Tests (If Development Install)

```bash
# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests (requires API access)
pytest tests/integration/ -v

# All tests
pytest -v
```

---

## Configuration

### Environment Variables

#### API Token (Optional but Recommended)

Socrata tokens increase rate limits 10x. Get a free token: https://data.cityofchicago.org/account/login

```bash
# Linux/macOS
export SOC_APP_TOKEN="your_app_token_here"

# Windows (Command Prompt)
set SOC_APP_TOKEN=your_app_token_here

# Windows (PowerShell)
$env:SOC_APP_TOKEN="your_app_token_here"
```

**Alternative**: Use `SOCRATA_APP_TOKEN` instead:
```bash
export SOCRATA_APP_TOKEN="your_app_token_here"
```

#### Verify Token Setup

```bash
chicago-crime-dl --help
# If token is set, you'll get faster downloads
```

### Python Dependencies

#### Required

- `requests` — HTTP client
- `pandas` — DataFrame handling
- `python-dateutil` — Date parsing

**Installed automatically** with `pip install`.

#### Optional

For Parquet support (recommended):

```bash
# Option 1: PyArrow (recommended, faster)
pip install pyarrow

# Option 2: Fastparquet (alternative)
pip install fastparquet

# Verify
python -c "import pyarrow; print(pyarrow.__version__)"
```

### Configuration File (Advanced)

Create a `~/.crime_downloader.ini` for persistent settings (future feature):

```ini
[http]
timeout = 60
retries = 10
sleep = 0.5

[output]
root = ~/data/chicago_crime
format = parquet
layout = mode-flat
```

> **Note**: Configuration files are not yet supported (planned for v0.6.0).

---

## Troubleshooting

### Installation Issues

#### Error: `command not found: chicago-crime-dl`

**Cause**: Python script not in PATH or different Python version.

**Solutions**:

```bash
# Check which Python has the package
which python
python -m chicago_crime_downloader.cli --help

# Add to PATH (on Linux/macOS)
export PATH="$(python -m site --user-base)/bin:$PATH"

# Upgrade pip
pip install --upgrade pip

# Reinstall
pip install --force-reinstall chicago-crime-downloader
```

#### Error: `ModuleNotFoundError: No module named 'chicago_crime_downloader'`

**Cause**: Package not installed or installed in different environment.

**Solutions**:

```bash
# Check installation
pip list | grep chicago-crime

# Verify Python version
python --version  # Should be 3.11+

# Reinstall
pip uninstall chicago-crime-downloader
pip install chicago-crime-downloader

# Check installation location
python -c "import chicago_crime_downloader; print(chicago_crime_downloader.__file__)"
```

#### Error: `Python version not supported`

**Cause**: Python < 3.11 installed.

**Solutions**:

```bash
# Install Python 3.11+
# Ubuntu/Debian
sudo apt-get install python3.11

# macOS (with Homebrew)
brew install python@3.11

# Windows: Download from https://www.python.org/

# Verify new version
python3.11 --version

# Install with correct Python
python3.11 -m pip install chicago-crime-downloader
```

### Runtime Issues

#### Error: `429 Too Many Requests`

**Cause**: Rate limit exceeded (too many API requests).

**Solutions**:

```bash
# 1. Set API token (10x faster)
export SOC_APP_TOKEN="your_token"
chicago-crime-dl --mode daily --start-date 2020-01-01 --end-date 2020-01-31

# 2. Increase backoff
chicago-crime-dl --mode monthly ...  # Larger windows = fewer requests

# 3. Use preflight to skip zero-row days
chicago-crime-dl --preflight --mode daily ...

# 4. Reduce chunk size (optional)
chicago-crime-dl --chunk-size 25000 ...  # Smaller chunks
```

#### Error: `ConnectionError` or `Timeout`

**Cause**: Network issue or API server down.

**Solutions**:

```bash
# Check internet connection
ping data.cityofchicago.org

# Try with longer timeout
chicago-crime-dl \
  --mode daily \
  --start-date 2020-01-01 \
  --end-date 2020-01-31
# (timeout is configurable via API, default 30s)

# Resume from last successful chunk
chicago-crime-dl \
  --mode daily \
  --start-date 2020-01-01 \
  --end-date 2020-01-31 \
  --out-root data/raw  # Same output root to resume
```

#### Error: `Parquet not written` / `Engine not found`

**Cause**: Parquet engine not installed.

**Solutions**:

```bash
# Install pyarrow (recommended)
pip install pyarrow

# Or fastparquet
pip install fastparquet

# Verify
python -c "import pyarrow; print('PyArrow OK')"

# Fall back to CSV if needed
chicago-crime-dl --out-format csv ...
```

### Output Issues

#### Error: `Permission denied` writing files

**Cause**: Output directory not writable.

**Solutions**:

```bash
# Check permissions
ls -la data/

# Create output directory with write permissions
mkdir -p data/raw
chmod 755 data/raw

# Use different output path
chicago-crime-dl --out-root ~/Downloads/crime_data ...

# Use relative path
chicago-crime-dl --out-root ./output ...
```

#### Output directory empty or missing

**Cause**: Process interrupted or zero-row download.

**Solutions**:

```bash
# Enable preflight to skip zero-row days
chicago-crime-dl --preflight --mode daily ...

# Check if data exists for date range
chicago-crime-dl --preflight --mode daily --start-date 2099-01-01 ...
# Likely no data for future dates

# Check logs
chicago-crime-dl --log-file logs/download.log ...
tail -f logs/download.log
```

### Development Issues

#### Tests Failing

**Cause**: Missing development dependencies or Python version issue.

**Solutions**:

```bash
# Reinstall with dev extras
pip install -e ".[dev]"

# Run specific test
pytest tests/unit/test_parse_date.py -v

# Check Python version
python --version  # Should be 3.11+

# Clear caches
rm -rf .pytest_cache/ .mypy_cache/ __pycache__/
pytest -v
```

#### Type Checking Errors (mypy)

**Cause**: Type hint incompatibilities.

**Solutions**:

```bash
# Run mypy with same flags as CI
mypy chicago_crime_downloader/ \
  --ignore-missing-imports \
  --disable-error-code=import-untyped

# Check specific file
mypy chicago_crime_downloader/config.py -v
```

#### Linting Errors (ruff)

**Cause**: Code style violations.

**Solutions**:

```bash
# Check all issues
ruff check chicago_crime_downloader/

# Auto-fix fixable issues
ruff check --fix chicago_crime_downloader/

# Check specific rule
ruff check --select E501 chicago_crime_downloader/
```

---

## Upgrade Guide

### From v0.4.x to v0.5.0

**Breaking Changes**:
- Requires Python 3.11+ (was 3.8+)
- Console script: `crime-dl` → `chicago-crime-dl`
- Default output: `crime_data/` → `data/raw`

**Upgrade Steps**:

```bash
# Backup old data
mv crime_data/ crime_data_backup/

# Upgrade package
pip install --upgrade chicago-crime-downloader

# Update scripts
# OLD: crime-dl --mode daily ...
# NEW: chicago-crime-dl --mode daily ...

# Rerun with new output path
chicago-crime-dl \
  --mode daily \
  --start-date 2020-01-01 \
  --end-date 2020-01-31 \
  --out-root data/raw
```

---

## Next Steps

After successful installation:

1. **Read the README**: https://github.com/BayoHabib/chicago_crime_data_cli
2. **Try Quick Start**: `chicago-crime-dl --help`
3. **Set API Token**: `export SOC_APP_TOKEN="your_token"`
4. **Download Data**: See examples in `README.md`
5. **Enable Logging**: `--log-file logs/download.log` for debugging

---

## Support

- **Issues**: https://github.com/BayoHabib/chicago_crime_data_cli/issues
- **Discussions**: https://github.com/BayoHabib/chicago_crime_data_cli/discussions
- **Documentation**: https://github.com/BayoHabib/chicago_crime_data_cli/blob/main/README.md
