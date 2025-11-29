import importlib
import sys
import time
from types import ModuleType

import pytest

# --- Helpers used by integration tests ---

class FakeResp:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self._payload = [] if payload is None else payload
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"{self.status_code} Client Error")

    def json(self):
        return self._payload

def run_cli(monkeypatch, module_path: str, argv):
    """
    Import the target module fresh and invoke its main() with argv.

    Args:
        monkeypatch: pytest's monkeypatch fixture.
        module_path: e.g. 'chicago_crime_downloader.cli' or 'data.download_data_v5'.
        argv: list[str] as if from the CLI (without program name).

    """
    # Ensure a fresh import each time (module holds globals)
    if module_path in sys.modules:
        del sys.modules[module_path]

    mod: ModuleType = importlib.import_module(module_path)

    # Reset global stop flag if present
    if hasattr(mod, "stop_requested"):
        setattr(mod, "stop_requested", False)

    # Call main() with argv directly (not via sys.argv)
    mod.main(argv=argv)
    return mod

# Capture sleeps without actually sleeping (useful for backoff tests)
@pytest.fixture
def fake_sleep(monkeypatch):
    calls = []
    monkeypatch.setattr(time, "sleep", lambda s: calls.append(s))
    return calls
