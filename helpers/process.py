import os
import sys
import threading
from helpers import runtime
from helpers.print_style import PrintStyle

_server = None
_reload_lock = threading.Lock()
_reloading = False

def set_server(server):
    global _server
    _server = server

def get_server(server):
    global _server
    return _server

def stop_server():
    global _server
    if _server:
        _server.shutdown()
        _server = None

def reload():
    # chat_project_filter_ui_restart_patch
    global _reloading
    with _reload_lock:
        if _reloading:
            PrintStyle.hint("Reload already in progress; ignoring duplicate request.")
            return
        _reloading = True

    stop_server()
    if runtime.is_dockerized() or is_systemd_managed():
        exit_process()
    else:
        restart_process()


def is_systemd_managed():
    # systemd sets these environment variables for service processes. When one
    # is present, exit the whole process and let systemd restart the unit
    # instead of execv-ing from a request thread.
    return any(
        os.environ.get(name)
        for name in ("INVOCATION_ID", "NOTIFY_SOCKET", "JOURNAL_STREAM")
    )


def restart_process():
    PrintStyle.standard("Restarting process...")
    python = sys.executable
    os.execv(python, [python] + sys.argv)

def exit_process():
    PrintStyle.standard("Exiting process...")
    os._exit(0)
