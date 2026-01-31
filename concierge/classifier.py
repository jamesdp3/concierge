from __future__ import annotations

import logging

from .llm.base import LLMProvider
from .models import Burst, IntentClassification

logger = logging.getLogger("concierge")


class Classifier:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def classify(self, burst: Burst) -> list[IntentClassification]:
        try:
            intents = await self._provider.classify_intent(burst)
        except Exception as e:
            logger.error("Classification failed: %s", e)
            return []

        if not intents:
            logger.warning("No intents extracted from burst of %d messages", len(burst.messages))

        return intents
