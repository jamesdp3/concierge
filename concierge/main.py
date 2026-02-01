from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .acknowledger import Acknowledger
from .classifier import Classifier
from .config import settings
from .llm.anthropic_provider import AnthropicProvider
from .llm.ollama_provider import OllamaProvider
from .llm.openai_provider import OpenAIProvider
from .reconciler import Reconciler
from .spacecadet_client import SpacecadetClient
from .websocket_handler import websocket_endpoint

logger = logging.getLogger("concierge")

STATIC_DIR = Path(__file__).parent.parent / "static"


def _build_provider():
    if settings.llm_provider == "openai":
        return OpenAIProvider()
    if settings.llm_provider == "ollama":
        return OllamaProvider()
    return AnthropicProvider()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

    provider = _build_provider()
    sc = SpacecadetClient()

    if settings.spacecadet_path:
        try:
            await sc.connect()
            logger.info("spacecadet connected")
        except Exception as e:
            logger.warning("spacecadet not available: %s", e)
            sc = None
    else:
        logger.warning("CONCIERGE_SPACECADET_PATH not set — running without spacecadet")
        sc = None

    app.state.spacecadet_client = sc
    app.state.classifier = Classifier(provider)
    app.state.reconciler = Reconciler(sc) if sc else None
    app.state.acknowledger = Acknowledger(provider)
    app.state.task_cache = None
    app.state.task_cache_time = 0
    app.state.task_cache_lock = asyncio.Lock()

    yield

    if sc:
        await sc.close()


app = FastAPI(title="concierge", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html", headers=NO_CACHE)


@app.get("/tasks")
async def tasks_page():
    return FileResponse(STATIC_DIR / "tasks.html", headers=NO_CACHE)


CACHE_TTL = 30  # seconds


async def _get_tasks():
    """Return cached task list, refreshing if stale."""
    sc = app.state.spacecadet_client
    if sc is None:
        return None
    now = time.monotonic()
    if app.state.task_cache is not None and now - app.state.task_cache_time < CACHE_TTL:
        return app.state.task_cache
    async with app.state.task_cache_lock:
        # Double-check after acquiring lock
        now = time.monotonic()
        if app.state.task_cache is not None and now - app.state.task_cache_time < CACHE_TTL:
            return app.state.task_cache
        result = await sc.list_tasks()
        app.state.task_cache = result if isinstance(result, list) else []
        app.state.task_cache_time = time.monotonic()
        return app.state.task_cache


def _invalidate_cache():
    app.state.task_cache = None
    app.state.task_cache_time = 0


@app.get("/api/tasks")
async def api_tasks(state: str | None = None, priority: str | None = None):
    tasks = await _get_tasks()
    if tasks is None:
        return JSONResponse({"error": "spacecadet not connected"}, status_code=503)
    return tasks


@app.patch("/api/tasks/{task_id}")
async def api_update_task(task_id: str, request: Request):
    sc = app.state.spacecadet_client
    if sc is None:
        return JSONResponse({"error": "spacecadet not connected"}, status_code=503)
    body = await request.json()
    new_state = body.get("state")
    if not new_state:
        return JSONResponse({"error": "state is required"}, status_code=400)
    # Optimistically update cache
    if app.state.task_cache is not None:
        for t in app.state.task_cache:
            if t.get("id") == task_id:
                t["todo"] = new_state
                break
    result = await sc.update_task(id=task_id, new_state=new_state)
    if isinstance(result, dict) and "error" in result:
        _invalidate_cache()
        return JSONResponse(result, status_code=500)
    _invalidate_cache()
    return result


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket_endpoint(websocket)
