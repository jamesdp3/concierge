from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .acknowledger import Acknowledger
from .classifier import Classifier
from .config import settings
from .llm.anthropic_provider import AnthropicProvider
from .llm.ollama_provider import OllamaProvider
from .reconciler import Reconciler
from .spacecadet_client import SpacecadetClient
from .websocket_handler import websocket_endpoint

logger = logging.getLogger("concierge")

STATIC_DIR = Path(__file__).parent.parent / "static"


def _build_provider():
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

    app.state.classifier = Classifier(provider)
    app.state.reconciler = Reconciler(sc) if sc else None
    app.state.acknowledger = Acknowledger(provider)

    yield

    if sc:
        await sc.close()


app = FastAPI(title="concierge", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket_endpoint(websocket)
