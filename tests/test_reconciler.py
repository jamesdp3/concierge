import pytest

from concierge.models import IntentClassification, IntentType
from concierge.reconciler import Reconciler


class FakeSpacecadetClient:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return {"status": "ok", "id": "abc123"}

    async def add_task(self, **kwargs):
        self.calls.append(("add_task", kwargs))
        return {"status": "ok", "id": "abc123", "heading": kwargs.get("heading")}

    async def update_task(self, **kwargs):
        self.calls.append(("update_task", kwargs))
        return {"status": "ok"}

    async def delete_task(self, **kwargs):
        self.calls.append(("delete_task", kwargs))
        return {"status": "ok"}

    async def list_tasks(self, **kwargs):
        return {"tasks": [{"id": "abc123", "heading": "Buy milk", "state": "TODO"}]}

    async def get_task(self, **kwargs):
        return {"id": "abc123", "heading": "Buy milk", "state": "TODO"}


@pytest.mark.asyncio
async def test_new_task_intent():
    client = FakeSpacecadetClient()
    reconciler = Reconciler(client)

    intent = IntentClassification(
        intent=IntentType.NEW_TASK,
        heading="Buy groceries",
        priority="A",
        raw_text="add task buy groceries priority A",
    )
    results = await reconciler.reconcile([intent])
    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert ("add_task", {"heading": "Buy groceries", "priority": "A"}) in client.calls


@pytest.mark.asyncio
async def test_cancel_task_by_heading():
    client = FakeSpacecadetClient()
    reconciler = Reconciler(client)

    intent = IntentClassification(
        intent=IntentType.CANCEL_TASK,
        heading="Buy milk",
        raw_text="cancel buy milk",
    )
    results = await reconciler.reconcile([intent])
    assert len(results) == 1
    assert ("update_task", {"id": "abc123", "state": "CANCELLED"}) in client.calls


@pytest.mark.asyncio
async def test_status_query():
    client = FakeSpacecadetClient()
    reconciler = Reconciler(client)

    intent = IntentClassification(
        intent=IntentType.STATUS_QUERY,
        raw_text="what are my tasks",
    )
    results = await reconciler.reconcile([intent])
    assert "tasks" in results[0]


@pytest.mark.asyncio
async def test_clarification_passthrough():
    client = FakeSpacecadetClient()
    reconciler = Reconciler(client)

    intent = IntentClassification(
        intent=IntentType.CLARIFICATION,
        note="Which task do you mean?",
        raw_text="update the thing",
    )
    results = await reconciler.reconcile([intent])
    assert results[0]["clarification"] == "Which task do you mean?"
