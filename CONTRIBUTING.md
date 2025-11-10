# Contributing to Chicago Crime Data CLI

Thank you for your interest in contributing! This document provides guidelines for local development, testing, and best practices.

## Local Setup

### Prerequisites
- Python 3.11 or later
- pip/venv

### Installation for Development

```bash
# Clone the repository
git clone https://github.com/BayoHabib/chicago_crime_data_cli.git
cd chicago_crime_data_cli

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (editable mode for development)
pip install -r requirements-dev.txt
pip install -e .
```

## Running Tests

Tests are split into unit and integration tests.

```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit -q

# Run only integration tests (slower, makes real API calls)
pytest -m integration -q

# Run with coverage
pytest --cov=chicago_crime_downloader --cov=tests

# Run specific test
pytest tests/unit/test_parse_date.py::test_parse_date
```

## Code Quality

### Type Checking

```bash
mypy chicago_crime_downloader
```

### Linting

```bash
ruff check chicago_crime_downloader tests
ruff format chicago_crime_downloader tests
```

## Workflow

### Feature Branches

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and run tests frequently:
   ```bash
   pytest -m unit -q && ruff check . && mypy chicago_crime_downloader
   ```

3. Commit with clear messages:
   ```bash
   git commit -m "feat: Add new feature description"
   ```

4. Push and create a Pull Request.

### Pull Request Checklist

- [ ] Tests pass (`pytest -q`)
- [ ] Linting passes (`ruff check .`)
- [ ] Type hints added (`mypy chicago_crime_downloader`)
- [ ] Docstrings added to new functions
- [ ] Backward compatibility maintained
- [ ] No breaking changes to CLI unless documented

## Architecture Overview

The codebase is organized into modular layers:

- **`config.py`**: Configuration dataclasses (HttpConfig, RunConfig)
- **`logging_utils.py`**: Logging setup (console, file, optional JSON)
- **`http_client.py`**: HTTP operations (requests, retries, token handling)
- **`soql.py`**: SoQL query building and date/window handling
- **`io_utils.py`**: File I/O (CSV/Parquet, manifests, resume logic)
- **`runners.py`**: Download execution (offset mode, windowed modes)
- **`cli.py`**: Command-line interface and argument parsing

See `docs/TODO_REFACTOR.md` for detailed refactoring roadmap.

## Testing Guidelines

### Unit Tests
Located in `tests/unit/`, these test individual functions with mocked dependencies.

```python
# Example: test a SoQL parameter builder
def test_soql_params_with_dates():
    params = soql_params(0, 100, "2020-01-01", "2020-01-31", None)
    assert params["$offset"] == "0"
    assert "$where" in params
```

### Integration Tests
Located in `tests/integration/`, these test end-to-end workflows (may hit real API).

```python
# Example: test full download workflow
def test_integration_daily_one_chunk():
    result = run_full_download(mode="daily", ...)
    assert result.success
```

## Environment Variables

For integration tests and API calls:

```bash
# Set Socrata app token (optional, improves rate limits)
export SOC_APP_TOKEN="your_token_here"
# OR
export SOCRATA_APP_TOKEN="your_token_here"
```

## Documentation

When adding features:

1. Add docstrings to all public functions
2. Update relevant module docs
3. Update `README.md` if changing CLI behavior
4. Add test cases demonstrating usage

## Issues and Discussions

- Report bugs via GitHub Issues
- Discuss design changes in Discussions before submitting large PRs
- Reference related issues in commit messages: `Fixes #42`

## Code Style

- Follow PEP 8
- Use type hints for all function parameters and returns
- Write descriptive docstrings (Google or NumPy style)
- Keep lines under 100 characters where possible
- Use meaningful variable names

## Getting Help

- Check existing tests for usage examples
- Review `docs/TODO_REFACTOR.md` for architecture details
- Ask in GitHub Issues or Discussions

---

Thank you for making this project better! 🙏
