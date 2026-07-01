import json
import re
import time
from helpers.extension import Extension
from helpers.print_style import PrintStyle

_LAST_SENT: dict[str, tuple[str, float]] = {}
_GEN_TTL_SECONDS = 90


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


def _strip_gen_header(text: str) -> str:
    """Remove the visual GEN header from Telegram-facing progress text."""
    return re.sub(r"^\s*GEN\s*🔵\s*\n+", "", text or "", count=1).strip()


def format_thoughts_message(data: dict) -> str:
    thoughts = data.get("thoughts") or []
    if isinstance(thoughts, str):
        thoughts = [thoughts]
    if not isinstance(thoughts, list):
        return ""
    parts: list[str] = []
    for item in thoughts[:8]:
        text = str(item or "").strip()
        if not text:
            continue
        if text.startswith("{") and text.endswith("}"):
            nested = _extract_json(text)
            if nested:
                nested_text = _strip_gen_header(format_thoughts_message(nested))
                if nested_text:
                    parts.append(nested_text[:500])
            continue
        parts.append(text[:500])
    if not parts:
        return ""
    return "\n\n".join(parts)


class TelegramGenResponsePlan(Extension):
    async def execute(self, stream: str = "", loop_data=None, **kwargs):
        if not self.agent or self.agent.number != 0:
            return
        context = self.agent.context
        raw_stream = stream or getattr(loop_data, "last_response", "") or getattr(self.agent.loop_data, "last_response", "") or ""
        data = _extract_json(raw_stream)
        if not data:
            return
        tool = str(data.get("tool_name") or "").strip()
        if not tool or tool == "response":
            return
        text = format_thoughts_message(data)
        if not text:
            return
        now = time.monotonic()
        key_id = getattr(context, "id", "") or "global"
        last_text, last_ts = _LAST_SENT.get(key_id, ("", 0.0))
        if last_text == text and now - last_ts < _GEN_TTL_SECONDS:
            return
        _LAST_SENT[key_id] = (text, now)
        context.data["_telegram_last_gen_text"] = text
        context.data["_telegram_last_gen_ts"] = time.time()
        try:
            PrintStyle.info(f"Telegram GEN project feed context={context.id} chars={len(text)}")
            from plugins._telegram_integration.helpers.handler import send_telegram_gen_to_project
            error = await send_telegram_gen_to_project(context, text)
            if error:
                PrintStyle.error(f"Telegram GEN project feed skipped/failed: {error}")
        except Exception as e:
            PrintStyle.error(f"Telegram GEN project hook failed: {type(e).__name__}: {e}")
