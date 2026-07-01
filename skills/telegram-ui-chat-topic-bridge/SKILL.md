# Telegram UI chat topic bridge

Use this skill when adding, debugging, or extending a bridge between Agent Zero UI chats and Telegram forum topics.

## Goal

Allow a specific Agent Zero UI chat/context to be linked to a dedicated Telegram forum topic, so Telegram replies route to that exact context and Agent Zero replies are sent back into that same topic.

## Key files

- Core Telegram plugin:
  - `/a0/plugins/_telegram_integration/helpers/constants.py`
  - `/a0/plugins/_telegram_integration/helpers/handler.py`
  - `/a0/usr/plugins/_telegram_integration/config.json`
  - `/a0/usr/plugins/_telegram_integration/state.json`
- UI/filter plugin:
  - `/a0/usr/plugins/chat_project_filter/webui/project-filter-store.js`
  - `/a0/usr/plugins/chat_project_filter/extensions/webui/sidebar-chats-list-start/project-filter.html`
  - `/a0/usr/plugins/chat_project_filter/api/*.py`

## Implementation pattern

1. Add or verify a context data key for the Telegram topic/thread id, usually `CTX_TG_MESSAGE_THREAD_ID = "telegram_message_thread_id"`.
2. Make Telegram routing thread-aware:
   - include `message_thread_id` in the Telegram state map key;
   - preserve compatibility with older state keys that did not include a thread suffix;
   - store `CTX_TG_MESSAGE_THREAD_ID` on contexts created or linked from Telegram;
   - when sending replies, pass `message_thread_id` to all Telegram send helpers: text, keyboard text, photo, file, voice, and typing.
3. Add an API endpoint in the UI/plugin layer when a UI action must create or link a topic.
   - Subclass `ApiHandler`.
   - Select the enabled Telegram bot from plugin config.
   - Resolve `user_id` from `allowed_users` or explicit input.
   - Resolve the target Telegram forum `chat_id` from explicit input, `state.json` `gen_feed_chat_id`, or existing state keys.
   - Create a forum topic with `bot.create_forum_topic(chat_id=..., name=...)`.
   - Save the map entry from Telegram topic to the Agent Zero `ctxid`.
   - Update `context.data` with bot, chat id, user id, and `message_thread_id`.
4. Add a frontend button in `project-filter-store.js`.
   - Inject into `.chat-container`, ideally inside `.chat-list-button` near existing chat action buttons.
   - Use strict event handling: `preventDefault`, `stopPropagation`, and `stopImmediatePropagation`.
   - Call `window.sendJsonData('/plugins/chat_project_filter/<endpoint>', payload)`.
   - Include `ctxid` and, when available, `project_name`.
5. Bump the cache-buster in the extension HTML import for the JS store.
6. Validate before reporting success:
   - `python3 -m py_compile <changed python files>`
   - `node --check <changed js file>`
   - `grep` for expected methods, constants, route names, and `message_thread_id` handling.

## Pitfalls

- Avoid fragile one-line Perl patches when inserting JS/HTML containing quotes, backticks, or `<span>`; use a short Python file-edit script instead.
- Do not block on full Agent Zero runtime imports as a smoke test; importing runtime modules can hang. Prefer `py_compile` and targeted grep checks unless an actual runtime restart/test is intended.
- Aiogram `Bot` lifecycle is safest with explicit `try/finally: await bot.session.close()` when uncertain about context-manager support.
- If changing `_map_key`, keep legacy lookup for old state keys. Otherwise existing Telegram conversations can silently start new Agent Zero contexts.
- Telegram forum topic creation requires a supergroup with forum topics enabled and bot admin rights to manage topics.
