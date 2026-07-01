# process.py DOX

## Purpose

- Own the `process.py` helper module.
- This module manages process reload, restart, exit, and server references.
- Keep this file-level DOX profile synchronized with `process.py` because this directory is intentionally flat.

## Ownership

- `process.py` owns the runtime implementation.
- `process.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Top-level functions:
- `set_server(server)`
- `get_server(server)`
- `stop_server()`
- `reload()`
- `is_systemd_managed()`
- `restart_process()`
- `exit_process()`

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: subprocess/runtime control.
- Imported dependency areas include: `helpers`, `helpers.print_style`, `os`, `sys`, `threading`.
- `reload()` is idempotent for the current process: a lock and `_reloading` guard ignore duplicate restart requests after the first one starts.
- In Dockerized or systemd-managed runtimes, `reload()` stops the server reference and exits the whole process with `os._exit(0)` so the external supervisor can restart it.
- In non-Docker, non-systemd local development, `reload()` still re-execs the current Python process with `os.execv(...)`.

## Key Concepts

- Important called helpers/classes observed in the source: `stop_server`, `runtime.is_dockerized`, `is_systemd_managed`, `PrintStyle.standard`, `PrintStyle.hint`, `os.execv`, `os._exit`, `_server.shutdown`, `exit_process`, `restart_process`.
- `is_systemd_managed()` treats `INVOCATION_ID`, `NOTIFY_SOCKET`, or `JOURNAL_STREAM` as evidence that the process is running under systemd.
- Do not call `sys.exit()` from a reload worker thread; it only exits that thread and can leave `agent-zero.service` active/running without a listening UI process.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- Related tests observed by source search:
  - `tests/test_api_chat_lifetime.py`
  - `tests/test_browser_agent_regressions.py`
  - `tests/test_docker_release_plan.py`
  - `tests/test_document_query_plugin.py`
  - `tests/test_download_toast_regressions.py`
  - `tests/test_git_version_label.py`
  - `tests/test_image_get_security.py`
  - `tests/test_model_config_project_presets.py`

## Child DOX Index

No child DOX files.
