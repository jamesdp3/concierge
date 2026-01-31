from __future__ import annotations

import logging
from typing import Any

from .llm.base import LLMProvider
from .models import IntentClassification, IntentType

logger = logging.getLogger("concierge")

# Simple template responses for single-intent operations
TEMPLATES = {
    IntentType.NEW_TASK: "Added: {heading}",
    IntentType.CANCEL_TASK: "Cancelled: {heading}",
    IntentType.PRIORITY_CHANGE: "Priority updated: {heading}",
}


class Acknowledger:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def acknowledge(
        self,
        intents: list[IntentClassification],
        results: list[dict[str, Any]],
    ) -> str:
        # Check for errors
        errors = [r for r in results if "error" in r]
        if errors and len(errors) == len(results):
            messages = [r["error"] for r in errors]
            return "; ".join(messages)

        # Clarification passthrough
        clarifications = [
            r["clarification"] for r in results if "clarification" in r
        ]
        if clarifications and len(clarifications) == len(results):
            return clarifications[0]

        # Single intent with template
        if len(intents) == 1 and intents[0].intent in TEMPLATES and not errors:
            heading = intents[0].heading or intents[0].raw_text[:40]
            return TEMPLATES[intents[0].intent].format(heading=heading)

        # Multi-intent or complex: use LLM
        try:
            return await self._provider.generate_acknowledgement(intents, results)
        except Exception as e:
            logger.error("Acknowledgement generation failed: %s", e)
            count = len(intents) - len(errors)
            return f"Done — processed {count} action(s)"
