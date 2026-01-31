from __future__ import annotations

import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from .burst import BurstDetector
from .inbox import Inbox
from .models import (
    Burst,
    Message,
    MessageStatus,
    SystemStatus,
    WSOutgoing,
    ws_error,
    ws_response,
    ws_status_update,
)
from .status import StatusMachine

logger = logging.getLogger("concierge")


async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    inbox = Inbox()

    async def send(msg: WSOutgoing) -> None:
        await websocket.send_text(msg.model_dump_json())

    status = StatusMachine(send)

    # Access pipeline components from app state
    app = websocket.app
    classifier = getattr(app.state, "classifier", None)
    reconciler = getattr(app.state, "reconciler", None)
    acknowledger = getattr(app.state, "acknowledger", None)

    async def on_burst(burst: Burst) -> None:
        for m in burst.messages:
            await send(ws_status_update(m.id, MessageStatus.READ))

        await status.set(SystemStatus.TYPING)

        # Step 1: Classify intents
        if classifier is None:
            await send(ws_response("[no LLM configured]"))
            await status.set(SystemStatus.IDLE)
            return

        intents = await classifier.classify(burst)
        if not intents:
            await send(ws_response("I couldn't understand that — could you rephrase?"))
            await status.set(SystemStatus.IDLE)
            return

        # Step 2: Reconcile against spacecadet
        await status.set(SystemStatus.PROCESSING)

        if reconciler is not None:
            results = await reconciler.reconcile(intents)
        else:
            results = [{"note": "spacecadet not connected — task not persisted"}] * len(intents)

        # Step 3: Generate acknowledgement
        await status.set(SystemStatus.TYPING)

        if acknowledger is not None:
            ack = await acknowledger.acknowledge(intents, results)
        else:
            ack = f"Processed {len(intents)} intent(s)"

        await send(ws_response(ack))
        await status.set(SystemStatus.IDLE)

    detector = BurstDetector(on_burst=on_burst)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await send(ws_error("Invalid JSON"))
                continue

            text = data.get("text", "").strip()
            if not text:
                continue

            message = Message(id=data.get("id", ""), text=text)
            inbox.append(message)
            await send(ws_status_update(message.id, MessageStatus.DELIVERED))

            detector.push(message)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
