from __future__ import annotations

import json
import logging
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from .config import settings

logger = logging.getLogger("concierge")


class SpacecadetClient:
    def __init__(self, server_path: str | None = None):
        self._server_path = server_path or settings.spacecadet_path
        self._session: ClientSession | None = None
        self._cm = None
        self._cm2 = None

    async def connect(self) -> None:
        if not self._server_path:
            raise ValueError(
                "CONCIERGE_SPACECADET_PATH must be set to the path of spacecadet server.py"
            )

        params = StdioServerParameters(
            command="python3",
            args=[self._server_path],
        )
        self._cm = stdio_client(params)
        streams = await self._cm.__aenter__()
        self._cm2 = ClientSession(*streams)
        self._session = await self._cm2.__aenter__()
        await self._session.initialize()
        logger.info("Connected to spacecadet at %s", self._server_path)

    async def close(self) -> None:
        if self._cm2:
            await self._cm2.__aexit__(None, None, None)
        if self._cm:
            await self._cm.__aexit__(None, None, None)
        self._session = None
        logger.info("Disconnected from spacecadet")

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict:
        if self._session is None:
            raise RuntimeError("Not connected to spacecadet")

        clean_args = {k: v for k, v in args.items() if v is not None}

        result = await self._session.call_tool(name, clean_args)

        if result.isError:
            error_text = result.content[0].text if result.content else "Unknown error"
            logger.error("spacecadet %s failed: %s", name, error_text)
            return {"error": error_text}

        text = result.content[0].text if result.content else "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}

    async def list_tasks(self, **kwargs) -> dict:
        return await self.call_tool("list_tasks", kwargs)

    async def add_task(self, **kwargs) -> dict:
        return await self.call_tool("add_task", kwargs)

    async def update_task(self, **kwargs) -> dict:
        return await self.call_tool("update_task", kwargs)

    async def delete_task(self, **kwargs) -> dict:
        return await self.call_tool("delete_task", kwargs)

    async def get_task(self, **kwargs) -> dict:
        return await self.call_tool("get_task", kwargs)
