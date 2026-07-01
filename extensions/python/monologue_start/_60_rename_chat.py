from __future__ import annotations

import asyncio

from agent import LoopData
from helpers import persist_chat, tokens
from helpers.extension import Extension
from helpers.print_style import PrintStyle
from helpers.state_monitor_integration import mark_dirty_all

MAX_AUTO_CHAT_NAME_LENGTH = 40

import json
import re

_MAX_AUTO_CHAT_NAME_WORDS = 8
_UI_DUMP_WORDS = {
    "menu",
    "home",
    "extension",
    "extensions",
    "settings",
    "refresh",
    "task details",
}
_UI_DUMP_WEAK_WORDS = {"chat", "chats"}


def _collapse_repeated_title_prefix(value: str) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if not compact:
        return ""

    lower = compact.lower()
    for size in range(3, len(compact) // 2 + 1):
        prefix = compact[:size]
        if not prefix.strip() or len(set(prefix.lower())) == 1:
            continue
        repeats = 0
        pos = 0
        while lower.startswith(prefix.lower(), pos):
            repeats += 1
            pos += size
        remainder = compact[pos:].strip()
        if repeats >= 2 and (not remainder or len(remainder) <= len(prefix)):
            return prefix.strip()
    return compact


def _fallback_auto_chat_name(history_text: str) -> str:
    """Best-effort local title when the utility model returns nothing usable."""
    if not isinstance(history_text, str) or not history_text.strip():
        return ""

    candidates: list[str] = []
    for line in history_text.splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith(("user:", "human:")):
            line = line.split(":", 1)[1].strip()
            candidates.append(line)
            continue

        try:
            parsed_line = json.loads(line)
        except Exception:
            parsed_line = None
        if isinstance(parsed_line, dict):
            for key in ("user_message", "message", "content", "text"):
                value = parsed_line.get(key)
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())
                    break
            continue

        if not lower.startswith(("assistant:", "tool_name:", "tool_result:")):
            candidates.append(line)

    for candidate in reversed(candidates):
        candidate = re.sub(r"^[#*\-:>\s]+", "", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip().strip('"`“”‘’.,;:')
        candidate = re.sub(r"\{.*?\}|\[.*?\]", "", candidate).strip()
        words = candidate.split()
        if 2 <= len(words) <= _MAX_AUTO_CHAT_NAME_WORDS:
            return _normalize_auto_chat_name(" ".join(words[:_MAX_AUTO_CHAT_NAME_WORDS]))
        if len(words) > _MAX_AUTO_CHAT_NAME_WORDS:
            return _normalize_auto_chat_name(" ".join(words[:_MAX_AUTO_CHAT_NAME_WORDS]))
    return ""


def _normalize_auto_chat_name(raw_name: object) -> str:
    if not isinstance(raw_name, str):
        return ""

    name = raw_name.strip().strip('"`“”‘’')
    if not name:
        return ""

    lower_initial = name.lower()
    if lower_initial.startswith(("thoughts:", "headline:", "tool_name:", "tool_args:")):
        return ""

    if name[0] in "[{":
        try:
            parsed = json.loads(name)
        except Exception:
            return ""
        if isinstance(parsed, dict):
            # Prefer explicit title fields, then tolerate framework JSON wrappers by
            # using their short headline. Never use tool names/args as titles.
            for key in ("title", "name", "headline"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    name = value.strip()
                    break
            else:
                return ""
        elif isinstance(parsed, str):
            name = parsed.strip()
        else:
            return ""
    else:
        try:
            parsed = json.loads(name)
            if isinstance(parsed, str):
                name = parsed.strip()
        except Exception:
            pass

    lines = [line.strip() for line in name.splitlines() if line.strip()]
    if len(lines) > 1:
        short_lines = [line for line in lines if len(line.split()) <= _MAX_AUTO_CHAT_NAME_WORDS]
        if len(lines) >= 4 or len(short_lines) != 1:
            return ""
        name = short_lines[0]

    name = re.sub(r"^[#*\-:>\s]+", "", name)
    name = re.sub(r"\s+", " ", name).strip().strip('"`“”‘’.,;:')
    name = _collapse_repeated_title_prefix(name)
    if not name:
        return ""

    lower = name.lower()
    words = set(re.findall(r"[a-zA-ZÀ-ÿ0-9_-]+", lower))
    has_strong_ui_dump_word = any(word in lower for word in _UI_DUMP_WORDS)
    has_weak_ui_dump_word = bool(words & _UI_DUMP_WEAK_WORDS)
    if has_strong_ui_dump_word and has_weak_ui_dump_word and len(name.split()) > 3:
        return ""
    if len(name.split()) > _MAX_AUTO_CHAT_NAME_WORDS:
        return ""
    if any(token in name for token in ("{", "}", "[", "]", '\":', "tool_name", "tool_args")):
        return ""

    if len(name) > MAX_AUTO_CHAT_NAME_LENGTH:
        name = name[:MAX_AUTO_CHAT_NAME_LENGTH].rstrip() + "..."
    return name


class RenameChat(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        asyncio.create_task(self.change_name())

    async def change_name(self, force: bool = False):
        if not self.agent:
            return
        if not force and self.agent.context.get_data("chat_rename_manual_lock"):
            return

        try:
            from plugins._model_config.helpers.model_config import get_utility_model_config

            util_cfg = get_utility_model_config(self.agent)
            history_text = self.agent.history.output_text()
            ctx_length = min(int(util_cfg.get("ctx_length", 128000) * 0.7), 5000)
            history_text = tokens.trim_to_tokens(history_text, ctx_length, "end")
            system = self.agent.read_prompt("fw.rename_chat.sys.md")
            current_name = self.agent.context.name
            message = self.agent.read_prompt(
                "fw.rename_chat.msg.md", current_name=current_name, history=history_text
            )
            raw_name = await asyncio.wait_for(
                self.agent.call_utility_model(
                    system=system, message=message, background=True
                ),
                timeout=15,
            )
            new_name = _normalize_auto_chat_name(raw_name)
            if not new_name:
                new_name = _fallback_auto_chat_name(history_text)
            if new_name:
                self.agent.context.name = new_name
                persist_chat.save_tmp_chat(self.agent.context)
                mark_dirty_all(reason="extensions.rename_chat.auto")
                return new_name
        except Exception as e:
            PrintStyle.error(f"Auto chat rename failed: {e}")
            try:
                history_text = self.agent.history.output_text()
                new_name = _fallback_auto_chat_name(history_text)
                if new_name:
                    self.agent.context.name = new_name
                    persist_chat.save_tmp_chat(self.agent.context)
                    mark_dirty_all(reason="extensions.rename_chat.auto.fallback")
                    return new_name
            except Exception as fallback_error:
                PrintStyle.error(f"Auto chat rename fallback failed: {fallback_error}")
        return ""
