from datetime import UTC, datetime

import pytest

from concierge.classifier import Classifier
from concierge.models import Burst, IntentClassification, IntentType, Message


class FakeProvider:
    def __init__(self, intents=None):
        self._intents = intents or []

    async def classify_intent(self, burst):
        return self._intents

    async def generate_acknowledgement(self, intents, results):
        return "done"


@pytest.mark.asyncio
async def test_classify_returns_provider_intents():
    intent = IntentClassification(
        intent=IntentType.NEW_TASK,
        heading="Buy milk",
        raw_text="add task buy milk",
    )
    classifier = Classifier(FakeProvider(intents=[intent]))
    burst = Burst(
        messages=[Message(text="add task buy milk")],
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
    )
    result = await classifier.classify(burst)
    assert len(result) == 1
    assert result[0].heading == "Buy milk"


@pytest.mark.asyncio
async def test_classify_handles_provider_error():
    class ErrorProvider(FakeProvider):
        async def classify_intent(self, burst):
            raise RuntimeError("API down")

    classifier = Classifier(ErrorProvider())
    burst = Burst(
        messages=[Message(text="anything")],
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
    )
    result = await classifier.classify(burst)
    assert result == []
