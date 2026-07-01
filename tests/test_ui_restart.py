import threading

import pytest

from api.restart import Restart
from helpers import process


@pytest.fixture(autouse=True)
def reset_reload_state():
    process._reloading = False
    yield
    process._reloading = False


@pytest.mark.anyio
async def test_restart_api_returns_before_running_reload(monkeypatch):
    calls = []
    threads = []

    class FakeThread:
        def __init__(self, *, target, daemon, name):
            calls.append(("init", daemon, name))
            self.target = target
            threads.append(self)

        def start(self):
            calls.append(("start",))

    monkeypatch.setattr("api.restart.threading.Thread", FakeThread)
    monkeypatch.setattr("api.restart.time.sleep", lambda seconds: calls.append(("sleep", seconds)))
    monkeypatch.setattr("api.restart.process.reload", lambda: calls.append(("reload",)))

    result = await Restart(app=None, thread_lock=threading.RLock()).process({}, None)

    assert result == {"success": True, "message": "Restart scheduled."}
    assert calls == [("init", True, "UiRestartExit"), ("start",)]

    threads[0].target()

    assert calls == [
        ("init", True, "UiRestartExit"),
        ("start",),
        ("sleep", 0.35),
        ("reload",),
    ]


def test_process_reload_exits_whole_process_when_dockerized(monkeypatch):
    calls = []

    def fake_exit(code):
        calls.append(("exit", code))
        raise SystemExit(code)

    monkeypatch.setattr(process.runtime, "is_dockerized", lambda: True)
    monkeypatch.setattr(process, "stop_server", lambda: calls.append(("stop",)))
    monkeypatch.setattr(process.os, "_exit", fake_exit)

    with pytest.raises(SystemExit) as exc_info:
        process.reload()

    assert exc_info.value.code == 0
    assert calls == [("stop",), ("exit", 0)]


def test_process_reload_exits_whole_process_when_systemd_managed(monkeypatch):
    calls = []

    def fake_exit(code):
        calls.append(("exit", code))
        raise SystemExit(code)

    monkeypatch.setattr(process.runtime, "is_dockerized", lambda: False)
    monkeypatch.setattr(process, "stop_server", lambda: calls.append(("stop",)))
    monkeypatch.setattr(process.os, "_exit", fake_exit)
    monkeypatch.setenv("INVOCATION_ID", "test-invocation")

    with pytest.raises(SystemExit) as exc_info:
        process.reload()

    assert exc_info.value.code == 0
    assert calls == [("stop",), ("exit", 0)]


def test_process_reload_ignores_duplicate_requests(monkeypatch):
    process._reloading = True
    calls = []

    monkeypatch.setattr(process.runtime, "is_dockerized", lambda: True)
    monkeypatch.setattr(process, "stop_server", lambda: calls.append(("stop",)))
    monkeypatch.setattr(process.os, "_exit", lambda code: calls.append(("exit", code)))

    process.reload()

    assert calls == []
