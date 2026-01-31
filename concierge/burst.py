from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Callable, Coroutine, Any

from .config import settings
from .models import Message, Burst


class BurstDetector:
    def __init__(
        self,
        on_burst: Callable[[Burst], Coroutine[Any, Any, None]],
        quiet_window: float | None = None,
        max_wait: float | None = None,
    ):
        self._on_burst = on_burst
        self._quiet_window = quiet_window or settings.quiet_window
        self._max_wait = max_wait or settings.max_wait
        self._buffer: list[Message] = []
        self._started_at: datetime | None = None
        self._quiet_timer: asyncio.TimerHandle | None = None
        self._max_timer: asyncio.TimerHandle | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def push(self, message: Message) -> None:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        if not self._buffer:
            self._started_at = datetime.now(UTC)
            self._max_timer = self._loop.call_later(
                self._max_wait, self._fire_sync
            )

        self._buffer.append(message)

        if self._quiet_timer is not None:
            self._quiet_timer.cancel()

        self._quiet_timer = self._loop.call_later(
            self._quiet_window, self._fire_sync
        )

    def _fire_sync(self) -> None:
        if self._loop is not None:
            self._loop.create_task(self._fire())

    async def _fire(self) -> None:
        if not self._buffer:
            return

        if self._quiet_timer is not None:
            self._quiet_timer.cancel()
            self._quiet_timer = None
        if self._max_timer is not None:
            self._max_timer.cancel()
            self._max_timer = None

        burst = Burst(
            messages=list(self._buffer),
            started_at=self._started_at or datetime.now(UTC),
            ended_at=datetime.now(UTC),
        )
        self._buffer.clear()
        self._started_at = None

        await self._on_burst(burst)
