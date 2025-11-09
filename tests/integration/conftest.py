import importlib, sys, time
import pytest

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

def run_cli(monkeypatch, module_path, argv):
    if module_path in sys.modules:
        del sys.modules[module_path]
    monkeypatch.setattr(sys, "argv", argv)
    mod = importlib.import_module(module_path)
    if hasattr(mod, "stop_requested"):
        mod.stop_requested = False
    mod.main()
    return mod

@pytest.fixture
def fake_sleep(monkeypatch):
    calls = []
    monkeypatch.setattr(time, "sleep", lambda s: calls.append(s))
    return calls
