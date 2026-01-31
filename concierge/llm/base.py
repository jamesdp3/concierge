from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import Burst, IntentClassification


@runtime_checkable
class LLMProvider(Protocol):
    async def classify_intent(self, burst: Burst) -> list[IntentClassification]:
        ...

    async def generate_acknowledgement(
        self, intents: list[IntentClassification], results: list[dict]
    ) -> str:
        ...
