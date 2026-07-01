# Telegram UI Topic Bridge

Use this skill when debugging or extending the bridge between Agent Zero UI chats and Telegram forum topics, especially the `chat_project_filter` button that creates a Telegram topic for the current UI chat.

## Files involved

- UI plugin API: `/a0/usr/plugins/chat_project_filter/api/telegram_topic.py`
- UI store/button logic: `/a0/usr/plugins/chat_project_filter/webui/project-filter-store.js`
- UI extension loader/cache buster: `/a0/usr/plugins/chat_project_filter/extensions/webui/sidebar-chats-list-start/project-filter.html`
- Telegram helper constants: `/a0/plugins/_telegram_integration/helpers/constants.py`
- Telegram routing and context mapping: `/a0/plugins/_telegram_integration/helpers/handler.py`
- Telegram send helpers: `/a0/plugins/_telegram_integration/helpers/telegram_client.py`
- Telegram state file path is defined by `STATE_FILE` in constants.

## Expected behavior

The UI button creates a Telegram forum topic named:

`<Agent Zero chat name> - <project name>`

The topic must be tied to the exact Agent Zero context id (`ctxid`) and routed using Telegram `message_thread_id` so replies inside that Telegram topic continue only that UI chat.

## Diagnostic sequence for Internal Server Error

1. Inspect recent Agent Zero logs with bounded commands; avoid grepping all large HTML logs:

```bash
cd /a0
tail -c 300000 logs/$(ls -t logs/*.html | head -1 | xargs basename) \
  | grep -a -n -C 8 'telegram_topic\|TelegramTopic\|Internal Server Error\|Traceback\|Exception' \
  | tail -220
```

2. Compile the endpoint and Telegram helpers:

```bash
cd /a0
python3 -m py_compile \
  usr/plugins/chat_project_filter/api/telegram_topic.py \
  plugins/_telegram_integration/helpers/handler.py \
  plugins/_telegram_integration/helpers/telegram_client.py
node --check usr/plugins/chat_project_filter/webui/project-filter-store.js
```

3. Check for missing imports/functions referenced by active extensions:

```bash
cd /a0
grep -RIn 'send_telegram_gen_to_project\|message_thread_id' \
  plugins/_telegram_integration usr/plugins/chat_project_filter 2>/dev/null
```

## Pitfalls discovered

### `send_telegram_gen_to_project` can disappear during handler merges

The active extension:

`/a0/plugins/_telegram_integration/extensions/python/response_stream_end/_45_telegram_gen_response_plan.py`

imports:

```python
from plugins._telegram_integration.helpers.handler import send_telegram_gen_to_project
```

If this function is missing from `handler.py`, logs show:

`ImportError: cannot import name 'send_telegram_gen_to_project'`

Restore the function and its helper dependencies from a recent backup such as:

- `/a0/plugins/_telegram_integration/helpers/handler.py.bak.thread-routing-fix-*`
- `/a0/plugins/_telegram_integration/helpers/handler.py.bak.pre-rich-merge-*`
- `/a0/plugins/_telegram_integration/helpers/handler.py.bak.git-restore-*`

The restored block may require imports/globals:

```python
import hashlib
import re

_GEN_PROJECT_REPLY_DEDUPE: dict[str, float] = {}
_GEN_PROJECT_REPLY_TTL = 90.0
```

### `telegram_client.send_text` must accept `message_thread_id`

If `telegram_topic.py` calls:

```python
await tc.send_text(..., message_thread_id=thread_id)
```

then `/a0/plugins/_telegram_integration/helpers/telegram_client.py` must include `message_thread_id` in `send_text(...)` and pass it to both `bot.send_message(...)` calls, including the fallback plain-text send.

Minimal expected signature:

```python
async def send_text(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_to_message_id: int | None = None,
    parse_mode: object = _UNSET,
    message_thread_id: int | None = None,
) -> int | None:
```

Then pass:

```python
message_thread_id=message_thread_id,
```

### API should return JSON errors, not HTML 500

For `telegram_topic.py`, wrap `process()` and move the implementation to `_process()` so the UI receives a structured payload:

```python
async def process(self, input: Input, request: Request) -> Output:
    try:
        return await self._process(input, request)
    except Exception as e:
        return {
            "success": False,
            "error": format_error(e),
            "message": str(e) or type(e).__name__,
        }
```

This lets the frontend show the real cause, such as missing bot token, no known Telegram group, not a forum-enabled supergroup, or missing Telegram rights.

## Telegram requirements

- The target chat must be a Telegram supergroup.
- Forum topics must be enabled.
- The bot must be in the group.
- The bot needs rights to manage/create topics.
- The integration must know the group `chat_id`; usually send at least one message from the target Telegram group first.
- If no numeric user id is configured in `allowed_users`, pass/provide a user id or add one.

## Verification after a fix

```bash
cd /a0
python3 -m py_compile \
  usr/plugins/chat_project_filter/api/telegram_topic.py \
  plugins/_telegram_integration/helpers/handler.py \
  plugins/_telegram_integration/helpers/telegram_client.py
node --check usr/plugins/chat_project_filter/webui/project-filter-store.js
grep -n 'message_thread_id\|send_telegram_gen_to_project' \
  plugins/_telegram_integration/helpers/telegram_client.py \
  plugins/_telegram_integration/helpers/handler.py \
  usr/plugins/chat_project_filter/api/telegram_topic.py
```

Restart Agent Zero or refresh plugins after changing backend API/helper code, then hard-refresh the UI/PWA so the updated JavaScript is loaded.
