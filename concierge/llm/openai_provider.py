from __future__ import annotations

import json
import logging
import re

import httpx

from ..config import settings
from ..models import Burst, IntentClassification

logger = logging.getLogger("concierge")

CLASSIFY_SYSTEM = """\
You are an intent classifier for a task management system called concierge.
You have FULL ACCESS to the user's task database. You CAN create, list, modify, cancel, and query tasks.
Given one or more user messages, extract every intent.

Today's date is {today}.

Return a JSON array of objects. Each object has these fields:
- intent: one of "new_task", "modify_task", "priority_change", "cancel_task", "clarification", "general_note", "status_query", "chat"
- heading: task title (for new_task) or reference text (for existing tasks), or null
- task_id: known task ID if user mentions one, or null
- priority: "A" (highest), "B" (high), "C" (default), or "D" (low) if mentioned or implied, or null
- deadline: absolute date string in YYYY-MM-DD format (resolve "tomorrow", "next friday", etc. relative to today), or null
- scheduled: absolute date/time string in YYYY-MM-DD or YYYY-MM-DD HH:MM format (resolve relative references), or null
- tags: array of tag strings (without colons), or []
- state: "TODO", "NEXT", "WAITING", "DONE", or "CANCELLED" if a state change is requested, or null
- note: freeform note text or the chat response text, or null
- raw_text: the original user text this intent was extracted from

Rules:
- Use "status_query" whenever the user asks to see, list, show, check, or review their tasks, agenda, or schedule. You HAVE this capability — always classify these as "status_query", never as "chat".
- Use "chat" ONLY for greetings, off-topic questions, or conversation that has nothing to do with tasks.
- For "chat" intents, put a helpful short response in the "note" field.
- Always resolve relative dates ("tomorrow", "next monday", "in 3 days") to absolute YYYY-MM-DD using today's date.
- If the user says a time like "at 4pm", put it in scheduled as "YYYY-MM-DD HH:MM".
- If the user implies urgency ("urgent", "important", "high priority", "asap"), set priority accordingly.

Return ONLY the JSON array, no markdown fences, no explanation.\
"""

ACK_SYSTEM = """\
You are a terse assistant confirming task operations.
Given a list of actions that were performed, write a short acknowledgement (under 120 characters).
Be factual and specific. Mention key details like deadlines, priorities, and times that were set.
No emoji. No pleasantries.\
"""


class OpenAIProvider:
    def __init__(self):
        self._api_key = settings.openai_api_key
        self._model = settings.openai_model
        self._base_url = settings.openai_base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=60.0)

    async def _chat(self, system: str, user: str, max_tokens: int = 1024) -> str:
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    async def classify_intent(self, burst: Burst) -> list[IntentClassification]:
        from datetime import UTC, datetime

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        system = CLASSIFY_SYSTEM.format(today=today)

        combined = "\n".join(
            f"[{m.timestamp.strftime('%H:%M:%S')}] {m.text}" for m in burst.messages
        )

        raw = await self._chat(system, combined)
        logger.info("OpenAI raw classification response: %s", raw)

        # Strip markdown fences if present
        if "```" in raw:
            match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("OpenAI returned invalid JSON for classification: %s", raw)
            return []

        if isinstance(data, dict):
            data = [data]

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
                {
                    "intent": i.intent.value,
                    "heading": i.heading,
                    "priority": i.priority,
                    "deadline": i.deadline,
                    "scheduled": i.scheduled,
                    "tags": i.tags,
                    "result": r,
                }
                for i, r in zip(intents, results)
            ],
            indent=2,
        )

        return await self._chat(ACK_SYSTEM, summary, max_tokens=128)
