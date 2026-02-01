from __future__ import annotations

import logging
from typing import Any

from .models import IntentClassification, IntentType
from .spacecadet_client import SpacecadetClient

logger = logging.getLogger("concierge")


class Reconciler:
    def __init__(self, client: SpacecadetClient):
        self._client = client

    async def reconcile(
        self, intents: list[IntentClassification]
    ) -> list[dict[str, Any]]:
        results = []
        for intent in intents:
            try:
                result = await self._dispatch(intent)
            except Exception as e:
                logger.error("Reconcile failed for %s: %s", intent.intent, e)
                result = {"error": str(e)}
            results.append(result)
        return results

    async def _dispatch(self, intent: IntentClassification) -> dict:
        match intent.intent:
            case IntentType.NEW_TASK:
                return await self._new_task(intent)
            case IntentType.MODIFY_TASK:
                return await self._modify_task(intent)
            case IntentType.PRIORITY_CHANGE:
                return await self._modify_task(intent)
            case IntentType.CANCEL_TASK:
                return await self._cancel_task(intent)
            case IntentType.STATUS_QUERY:
                return await self._status_query(intent)
            case IntentType.GENERAL_NOTE:
                return await self._new_task(intent)
            case IntentType.CHAT:
                return {"chat": intent.note or intent.raw_text}
            case IntentType.CLARIFICATION:
                return {"clarification": intent.note or intent.raw_text}
            case _:
                return {"error": f"Unknown intent: {intent.intent}"}

    async def _new_task(self, intent: IntentClassification) -> dict:
        args: dict[str, Any] = {}
        if intent.heading:
            args["heading"] = intent.heading
        else:
            args["heading"] = intent.raw_text[:80]

        if intent.priority:
            args["priority"] = intent.priority
        if intent.deadline:
            args["deadline"] = intent.deadline
        if intent.scheduled:
            args["scheduled"] = intent.scheduled
        if intent.tags:
            args["tags"] = intent.tags

        return await self._client.add_task(**args)

    async def _modify_task(self, intent: IntentClassification) -> dict:
        target = await self._resolve_task(intent)
        if "error" in target:
            return target

        args: dict[str, Any] = {"id": target["id"]}
        if intent.state:
            args["state"] = intent.state
        if intent.priority:
            args["priority"] = intent.priority
        if intent.deadline:
            args["deadline"] = intent.deadline

        return await self._client.update_task(**args)

    async def _cancel_task(self, intent: IntentClassification) -> dict:
        target = await self._resolve_task(intent)
        if "error" in target:
            return target

        return await self._client.update_task(id=target["id"], state="CANCELLED")

    async def _status_query(self, intent: IntentClassification) -> dict:
        if intent.task_id:
            return await self._client.get_task(id=intent.task_id)

        result = await self._client.list_tasks()
        return result

    async def _resolve_task(self, intent: IntentClassification) -> dict:
        if intent.task_id:
            return {"id": intent.task_id}

        if not intent.heading:
            return {"error": "Cannot identify task — no ID or heading provided"}

        # Search existing tasks by heading
        result = await self._client.list_tasks()
        tasks = result if isinstance(result, list) else result.get("tasks", [])

        query = intent.heading.lower()
        matches = [
            t for t in tasks
            if query in t.get("heading", "").lower()
        ]

        if len(matches) == 1:
            return {"id": matches[0]["id"]}
        elif len(matches) == 0:
            return {"error": f"No task found matching '{intent.heading}'"}
        else:
            headings = [m.get("heading", "") for m in matches[:5]]
            return {
                "error": f"Multiple tasks match '{intent.heading}': {headings}"
            }
