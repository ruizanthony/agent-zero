import threading
import time

from helpers.api import ApiHandler, Request, Response

from helpers import process

class Restart(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        def delayed_reload():
            # chat_project_filter_ui_restart_patch
            # Let the HTTP response flush to the browser before the server process
            # is stopped/re-executed. Without this delay the Web UI can be left
            # waiting forever on a request whose connection was cut mid-flight.
            time.sleep(0.35)
            process.reload()

        threading.Thread(
            target=delayed_reload,
            daemon=True,
            name="UiRestartExit",
        ).start()
        return {"success": True, "message": "Restart scheduled."}
