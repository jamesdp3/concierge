from __future__ import annotations

from typing import Callable, Coroutine, Any

from .models import SystemStatus, WSOutgoing, ws_system_status


class StatusMachine:
    def __init__(self, send: Callable[[WSOutgoing], Coroutine[Any, Any, None]]):
        self._send = send
        self._current = SystemStatus.IDLE

    @property
    def current(self) -> SystemStatus:
        return self._current

    async def set(self, status: SystemStatus) -> None:
        if status != self._current:
            self._current = status
            await self._send(ws_system_status(status))
