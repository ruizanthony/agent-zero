from __future__ import annotations

from agent import AgentContext
from helpers.api import ApiHandler, Request, Response
from helpers.persist_chat import save_tmp_chat
from helpers.state_monitor_integration import mark_dirty_all, mark_dirty_for_context


MANUAL_LOCK_KEY = "chat_rename_manual_lock"


def _clean_manual_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    name = " ".join(value.strip().split())
    return name[:120]


class RenameChat(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        context_id = str(input.get("context_id") or input.get("context") or "").strip()
        mode = str(input.get("mode") or "manual").strip().lower()

        if not context_id:
            return Response(status=400, response="Missing context_id")

        context = AgentContext.get(context_id)
        if not context:
            return Response(status=404, response="Context not found")

        if mode == "auto":
            context.name = None
            context.data.pop(MANUAL_LOCK_KEY, None)
            save_tmp_chat(context)
            mark_dirty_for_context(context.id, reason="chat_rename.reset_auto")
            mark_dirty_all(reason="chat_rename.reset_auto")

            new_name = ""
            if context.agent0:
                from extensions.python.monologue_start._60_rename_chat import RenameChat as AutoRenameChat

                new_name = await AutoRenameChat(agent=context.agent0).change_name(force=True)

            return {"ok": True, "name": new_name or context.name, "manual_lock": False}

        name = _clean_manual_name(input.get("name"))
        if not name:
            return Response(status=400, response="Missing name")

        context.name = name
        context.data[MANUAL_LOCK_KEY] = True
        save_tmp_chat(context)
        mark_dirty_for_context(context.id, reason="chat_rename.manual")
        mark_dirty_all(reason="chat_rename.manual")
        return {"ok": True, "name": context.name, "manual_lock": True}
