import os
import threading
import time

import initialize
from helpers import dotenv, extension, runtime
from helpers.api import csrf_protect, requires_auth
from helpers.print_style import PrintStyle
from helpers.server_startup import run_uvicorn_with_retries
from helpers.ui_server import UiServerRuntime, configure_process_environment


def run():
    configure_process_environment()
    PrintStyle().print("Initializing Python framework...")
    PrintStyle().print("Checking for data migration...")
    run_migration_checks()

    PrintStyle().print("Preparing web server runtime...")
    server_runtime, host, port = prepare_web_runtime()

    PrintStyle().print("Scheduling Agent Zero background initialization...")
    schedule_background_init_a0(include_chats=True)

    PrintStyle().print("Starting UI/API server...")
    start_web_server(server_runtime, host, port)


def run_migration_checks() -> None:
    initialize.initialize_migration()


def prepare_web_runtime() -> tuple[UiServerRuntime, str, int]:
    host = (
        runtime.get_arg("host") or dotenv.get_dotenv_value("WEB_UI_HOST") or "localhost"
    )
    port = runtime.get_web_ui_port()
    server_runtime = UiServerRuntime.create()
    server_runtime.register_http_routes()
    server_runtime.register_transport_handlers()

    return server_runtime, host, port


def start_web_server(server_runtime: UiServerRuntime, host: str, port: int) -> None:
    run_uvicorn_with_retries(
        host=host,
        port=port,
        build_asgi_app=server_runtime.build_asgi_app,
        flush_callback=create_flush_callback(),
        access_log=server_runtime.access_log_enabled(),
        ws="wsproto",
    )


def create_flush_callback():
    def flush_and_shutdown_callback() -> None:
        """
        TODO(dev): add cleanup + flush-to-disk logic here.
        """
        return

    flush_ran = False

    def _run_flush(reason: str) -> None:
        nonlocal flush_ran
        if flush_ran:
            return
        flush_ran = True
        try:
            flush_and_shutdown_callback()
        except Exception as e:
            PrintStyle.warning(f"Shutdown flush failed ({reason}): {e}")

    return _run_flush


def initialize_required_a0_state() -> None:
    init_chats = initialize.initialize_chats()
    init_chats.result_sync()


def _background_init_delay_seconds() -> float:
    try:
        return max(0.0, float(os.getenv("A0_BACKGROUND_INIT_DELAY_SECONDS", "1.0")))
    except (TypeError, ValueError):
        return 1.0


_background_init_lock = threading.Lock()
_background_init_started = False


def schedule_background_init_a0(include_chats: bool = True) -> None:
    global _background_init_started
    with _background_init_lock:
        if _background_init_started:
            PrintStyle.hint("Background Agent Zero initialization already scheduled.")
            return
        _background_init_started = True

    def _run_background_init() -> None:
        delay = _background_init_delay_seconds()
        if delay > 0:
            time.sleep(delay)
        try:
            PrintStyle().print("Initializing Agent Zero background components...")
            init_a0(include_chats=include_chats)
            PrintStyle().print("Agent Zero background components initialized.")
        except BaseException as e:
            PrintStyle.error(
                f"Background Agent Zero initialization failed: {type(e).__name__}: {e}"
            )

    threading.Thread(
        target=_run_background_init,
        daemon=True,
        name="A0BackgroundInit",
    ).start()


@extension.extensible
def init_a0(include_chats: bool = True):
    if include_chats:
        initialize_required_a0_state()

    initialize.initialize_mcp()
    initialize.initialize_job_loop()
    initialize.initialize_preload()


if __name__ == "__main__":
    runtime.initialize()
    dotenv.load_dotenv()
    run()
