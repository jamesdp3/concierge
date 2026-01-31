from __future__ import annotations

import json
import logging

import httpx

from ..config import settings
from ..models import Burst, IntentClassification
from .base import LLMProvider

logger = logging.getLogger("concierge")

CLASSIFY_SYSTEM = """\
You are an intent classifier for a task management system.
Given one or more user messages, extract every task management intent.

Return a JSON array of objects. Each object has these fields:
- intent: one of "new_task", "modify_task", "priority_change", "cancel_task", "clarification", "general_note", "status_query"
- heading: task title (for new_task) or reference text (for existing tasks), or null
- task_id: known task ID if user mentions one, or null
- priority: "A", "B", "C", or "D" if mentioned, or null
- deadline: date string if mentioned (e.g. "2025-01-15", "tomorrow"), or null
- scheduled: date string if mentioned, or null
- tags: array of tag strings (without colons), or []
- state: "TODO", "NEXT", "WAITING", "DONE", or "CANCELLED" if a state change is requested, or null
- note: freeform note text if relevant, or null
- raw_text: the original user text this intent was extracted from

Return ONLY the JSON array, no markdown fences, no explanation.\
"""

ACK_SYSTEM = """\
You are a terse assistant confirming task operations.
Given a list of actions that were performed, write a short acknowledgement (under 80 characters).
Be factual and specific. No emoji. No pleasantries.\
"""


class OllamaProvider:
    def __init__(self):
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._client = httpx.AsyncClient(timeout=60.0)

    async def _chat(self, system: str, user: str, max_tokens: int = 1024) -> str:
        response = await self._client.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()

    async def classify_intent(self, burst: Burst) -> list[IntentClassification]:
        combined = "\n".join(
            f"[{m.timestamp.strftime('%H:%M:%S')}] {m.text}" for m in burst.messages
        )

        raw = await self._chat(CLASSIFY_SYSTEM, combined)

        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Ollama returned invalid JSON for classification: %s", raw)
            return []

        intents = []
        for item in data:
            try:
                intents.append(IntentClassification(**item))
            except Exception as e:
                logger.warning("Skipping malformed intent: %s (%s)", item, e)

        return intents

    async def generate_acknowledgement(
        self, intents: list[IntentClassification], results: list[dict]
    ) -> str:
        summary = json.dumps(
            [
                {"intent": i.intent.value, "heading": i.heading, "result": r}
                for i, r in zip(intents, results)
            ],
            indent=2,
        )

        return await self._chat(ACK_SYSTEM, summary, max_tokens=128)
