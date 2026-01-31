import asyncio
from datetime import datetime

import pytest

from concierge.burst import BurstDetector
from concierge.models import Burst, Message


@pytest.fixture
def burst_results():
    return []


@pytest.fixture
def detector(burst_results):
    async def on_burst(burst: Burst):
        burst_results.append(burst)

    return BurstDetector(on_burst=on_burst, quiet_window=0.1, max_wait=0.5)


@pytest.mark.asyncio
async def test_single_message_fires_after_quiet_window(detector, burst_results):
    detector.push(Message(text="hello"))
    await asyncio.sleep(0.25)
    assert len(burst_results) == 1
    assert len(burst_results[0].messages) == 1
    assert burst_results[0].messages[0].text == "hello"


@pytest.mark.asyncio
async def test_rapid_messages_grouped_into_one_burst(detector, burst_results):
    detector.push(Message(text="one"))
    await asyncio.sleep(0.05)
    detector.push(Message(text="two"))
    await asyncio.sleep(0.05)
    detector.push(Message(text="three"))
    await asyncio.sleep(0.25)
    assert len(burst_results) == 1
    assert len(burst_results[0].messages) == 3


@pytest.mark.asyncio
async def test_max_wait_forces_burst(detector, burst_results):
    # Push messages every 80ms (under quiet_window of 100ms would reset),
    # but max_wait of 500ms should force fire
    for i in range(8):
        detector.push(Message(text=f"msg-{i}"))
        await asyncio.sleep(0.08)

    await asyncio.sleep(0.25)
    assert len(burst_results) >= 1
    total_messages = sum(len(b.messages) for b in burst_results)
    assert total_messages == 8


@pytest.mark.asyncio
async def test_separate_bursts_for_spaced_messages(detector, burst_results):
    detector.push(Message(text="first"))
    await asyncio.sleep(0.25)
    assert len(burst_results) == 1

    detector.push(Message(text="second"))
    await asyncio.sleep(0.25)
    assert len(burst_results) == 2
