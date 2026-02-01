from __future__ import annotations

import logging
from typing import Any

from .llm.base import LLMProvider
from .models import IntentClassification, IntentType

logger = logging.getLogger("concierge")

PRIORITY_LABELS = {"A": "!!!", "B": "!!", "C": "!", "D": ""}


def _task_summary(intent: IntentClassification) -> str:
    parts = []
    if intent.heading:
        parts.append(intent.heading)
    if intent.priority:
        parts.append(f"[#{intent.priority}]")
    if intent.deadline:
        parts.append(f"due {intent.deadline}")
    if intent.scheduled:
        parts.append(f"scheduled {intent.scheduled}")
    if intent.tags:
        parts.append(" ".join(f":{t}:" for t in intent.tags))
    return " ".join(parts) if parts else intent.raw_text[:40]


def _format_task_list(result) -> str:
    tasks = result if isinstance(result, list) else result.get("tasks", [])
    if not tasks:
        return "No tasks found."

    lines = [f"You have {len(tasks)} task(s):"]
    for t in tasks:
        state = t.get("state", "TODO")
        heading = t.get("heading", "???")
        pri = t.get("priority", "")
        pri_mark = PRIORITY_LABELS.get(pri, "")

        parts = [f"  {state} {pri_mark} {heading}".rstrip()]
        deadline = t.get("deadline")
        scheduled = t.get("scheduled")
        if deadline:
            parts.append(f"due {deadline}")
        if scheduled:
            parts.append(f"@ {scheduled}")

        lines.append(" — ".join(parts))

    return "\n".join(lines)


class Acknowledger:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def acknowledge(
        self,
        intents: list[IntentClassification],
        results: list[dict[str, Any]],
    ) -> str:
        # Chat passthrough
        chat_responses = [r["chat"] for r in results if "chat" in r]
        non_chat = [(i, r) for i, r in zip(intents, results) if "chat" not in r]

        if chat_responses and not non_chat:
            return chat_responses[0]

        # Check for errors
        errors = [r for _, r in non_chat if "error" in r]
        if errors and len(errors) == len(non_chat):
            messages = [r["error"] for r in errors]
            return "; ".join(messages)

        # Clarification passthrough
        clarifications = [r["clarification"] for _, r in non_chat if "clarification" in r]
        if clarifications and len(clarifications) == len(non_chat):
            return clarifications[0]

        # Status query — format task list directly, no LLM call
        if len(non_chat) == 1:
            intent, result = non_chat[0]
            if intent.intent == IntentType.STATUS_QUERY and "error" not in result:
                formatted = _format_task_list(result)
                if chat_responses:
                    return f"{chat_responses[0]}\n\n{formatted}"
                return formatted

        # Single task operations — use template, no LLM call
        if len(non_chat) == 1:
            intent, result = non_chat[0]
            if intent.intent == IntentType.NEW_TASK and "error" not in result:
                return f"Added: {_task_summary(intent)}"
            if intent.intent == IntentType.CANCEL_TASK and "error" not in result:
                return f"Cancelled: {_task_summary(intent)}"
            if intent.intent == IntentType.PRIORITY_CHANGE and "error" not in result:
                return f"Priority updated: {_task_summary(intent)}"
            if intent.intent == IntentType.MODIFY_TASK and "error" not in result:
                return f"Updated: {_task_summary(intent)}"

        # Multi-intent or complex: use LLM
        try:
            ack = await self._provider.generate_acknowledgement(
                [i for i, _ in non_chat],
                [r for _, r in non_chat],
            )
        except Exception as e:
            logger.error("Acknowledgement generation failed: %s", e)
            count = len(non_chat) - len(errors)
            ack = f"Done — processed {count} action(s)"

        if chat_responses:
            return f"{chat_responses[0]}\n\n{ack}"

        return ack
