import json
import re
import time
from helpers.extension import Extension
from helpers.print_style import PrintStyle
from plugins._telegram_integration.helpers.constants import CTX_TG_BOT

_LAST_SENT: dict[str, str] = {}
_LAST_TIME: dict[str, float] = {}
_MIN_INTERVAL = 0.8


def _extract_json(raw: str) -> dict | None:
    raw = (raw or "").strip()
    if not raw or len(raw) > 12000:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _format_thoughts(data: dict) -> str:
    thoughts = data.get("thoughts") or []
    if isinstance(thoughts, str):
        thoughts = [thoughts]
    if not isinstance(thoughts, list):
        return ""
    parts: list[str] = []
    for item in thoughts[:6]:
        text = str(item or "").strip()
        if not text or (text.startswith("{") and text.endswith("}")):
            continue
        parts.append(text[:420])
    if not parts:
        return ""
    return "\n\n".join(parts)


class TelegramGenToolProgress(Extension):
    async def execute(self, tool_name: str = "", tool_args: dict | None = None, **kwargs):
        if not self.agent or self.agent.number != 0:
            return
        context = self.agent.context
        if not context.data.get(CTX_TG_BOT):
            return
        if not tool_name or tool_name == "response":
            return

        raw = ""
        try:
            raw = str(getattr(self.agent.loop_data.current_tool, "message", "") or "").strip()
        except Exception as e:
            PrintStyle.error(f"Telegram GEN voice hook could not read current_tool.message: {type(e).__name__}: {e}")

        data = _extract_json(raw)
        if data:
            text = _format_thoughts(data)
        else:
            if raw.startswith("{") or raw.startswith("["):
                return
            text = raw[:220] if raw else f"Action : {tool_name}"

        if not text:
            return
        now = time.time()
        if text == _LAST_SENT.get(context.id) and now - _LAST_TIME.get(context.id, 0) < 10:
            return
        if now - _LAST_TIME.get(context.id, 0) < _MIN_INTERVAL:
            return
        _LAST_SENT[context.id] = text
        _LAST_TIME[context.id] = now

        try:
            PrintStyle.info(f"Telegram GEN voice hook sending context={context.id} tool={tool_name} chars={len(text)}")
            from plugins._telegram_integration.helpers.handler import send_telegram_reply
            await send_telegram_reply(context, text, None, None, voice=True)
        except Exception as e:
            PrintStyle.error(f"Telegram GEN voice hook failed: {type(e).__name__}: {e}")
