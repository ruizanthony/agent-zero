import sys
from pathlib import Path
from types import ModuleType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_model_config_stub = ModuleType("plugins._model_config.helpers.model_config")
setattr(_model_config_stub, "get_presets", lambda: [])
setattr(_model_config_stub, "get_preset_by_name", lambda name: None)
setattr(_model_config_stub, "get_chat_model_config", lambda agent=None: {})
sys.modules.setdefault("plugins._model_config.helpers.model_config", _model_config_stub)


def test_run_schedules_background_init_before_server(monkeypatch):
    import run_ui

    calls = []

    monkeypatch.setattr(run_ui, "configure_process_environment", lambda: calls.append("configure"))
    monkeypatch.setattr(run_ui, "run_migration_checks", lambda: calls.append("migration"))

    def fake_prepare_web_runtime():
        calls.append("prepare")
        return "runtime", "127.0.0.1", 5000

    monkeypatch.setattr(run_ui, "prepare_web_runtime", fake_prepare_web_runtime)
    monkeypatch.setattr(
        run_ui,
        "schedule_background_init_a0",
        lambda include_chats=True: calls.append(("schedule_background", include_chats)),
    )
    monkeypatch.setattr(
        run_ui,
        "start_web_server",
        lambda runtime, host, port: calls.append(("start_server", runtime, host, port)),
    )

    run_ui.run()

    assert calls == [
        "configure",
        "migration",
        "prepare",
        ("schedule_background", True),
        ("start_server", "runtime", "127.0.0.1", 5000),
    ]


def test_schedule_background_init_delays_then_initializes_with_requested_chat_mode(monkeypatch):
    import run_ui

    calls = []
    threads = []

    monkeypatch.setattr(run_ui, "_background_init_started", False)
    monkeypatch.setenv("A0_BACKGROUND_INIT_DELAY_SECONDS", "0.25")
    monkeypatch.setattr(run_ui.time, "sleep", lambda seconds: calls.append(("sleep", seconds)))
    monkeypatch.setattr(
        run_ui,
        "init_a0",
        lambda include_chats=True: calls.append(("init_a0", include_chats)),
    )

    class FakeThread:
        def __init__(self, *, target, daemon, name):
            calls.append(("thread", daemon, name))
            self.target = target
            threads.append(self)

        def start(self):
            calls.append(("start",))

    monkeypatch.setattr(run_ui.threading, "Thread", FakeThread)

    run_ui.schedule_background_init_a0(include_chats=True)

    assert calls == [("thread", True, "A0BackgroundInit"), ("start",)]

    threads[0].target()

    assert calls == [
        ("thread", True, "A0BackgroundInit"),
        ("start",),
        ("sleep", 0.25),
        ("init_a0", True),
    ]

    calls.clear()
    threads.clear()
    monkeypatch.setattr(run_ui, "_background_init_started", False)

    run_ui.schedule_background_init_a0(include_chats=False)
    threads[0].target()

    assert calls == [
        ("thread", True, "A0BackgroundInit"),
        ("start",),
        ("sleep", 0.25),
        ("init_a0", False),
    ]


def test_init_a0_can_skip_chats_for_background_start(monkeypatch):
    import run_ui

    calls = []

    class FakeTask:
        def result_sync(self):
            calls.append("chats_result")

    monkeypatch.setattr(
        run_ui.initialize,
        "initialize_chats",
        lambda: calls.append("chats") or FakeTask(),
    )
    monkeypatch.setattr(run_ui.initialize, "initialize_mcp", lambda: calls.append("mcp"))
    monkeypatch.setattr(run_ui.initialize, "initialize_job_loop", lambda: calls.append("job_loop"))
    monkeypatch.setattr(run_ui.initialize, "initialize_preload", lambda: calls.append("preload"))

    raw_init_a0 = getattr(run_ui.init_a0, "__wrapped__")

    raw_init_a0(include_chats=False)

    assert calls == ["mcp", "job_loop", "preload"]

    calls.clear()
    raw_init_a0(include_chats=True)

    assert calls == ["chats", "chats_result", "mcp", "job_loop", "preload"]
