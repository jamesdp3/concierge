from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from .burst import BurstDetector
from .inbox import Inbox
from .models import (
    Burst,
    IntentType,
    Message,
    MessageStatus,
    SystemStatus,
    WSOutgoing,
    ws_error,
    ws_response,
    ws_status_update,
    ws_task_list,
)
from .status import StatusMachine

logger = logging.getLogger("concierge")


async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    inbox = Inbox()
    closed = False

    async def send(msg: WSOutgoing) -> None:
        if closed:
            return
        try:
            await websocket.send_text(msg.model_dump_json())
        except RuntimeError:
            return

    status = StatusMachine(send)

    # Access pipeline components from app state
    app = websocket.app
    classifier = getattr(app.state, "classifier", None)
    reconciler = getattr(app.state, "reconciler", None)
    acknowledger = getattr(app.state, "acknowledger", None)

    burst_done = asyncio.Event()
    burst_done.set()

    async def on_burst(burst: Burst) -> None:
        burst_done.clear()
        try:
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

            # Send interim message for status queries
            has_query = any(i.intent == IntentType.STATUS_QUERY for i in intents)
            if has_query:
                await send(ws_response("Searching..."))

            # Step 2: Reconcile against spacecadet
            await status.set(SystemStatus.PROCESSING)

            if reconciler is not None:
                results = await reconciler.reconcile(intents)
            else:
                results = [{"note": "spacecadet not connected — task not persisted"}] * len(intents)

            # Step 3: Send structured task list for status queries
            has_task_list = False
            for intent, result in zip(intents, results):
                if intent.intent == IntentType.STATUS_QUERY and "error" not in result:
                    tasks = result if isinstance(result, list) else [result]
                    await send(ws_task_list(tasks, header=f"{len(tasks)} task(s)"))
                    has_task_list = True

            # Step 4: Generate acknowledgement for non-query intents
            non_query = [
                (i, r) for i, r in zip(intents, results)
                if i.intent != IntentType.STATUS_QUERY
            ]

            if non_query:
                await status.set(SystemStatus.TYPING)
                if acknowledger is not None:
                    ack = await acknowledger.acknowledge(
                        [i for i, _ in non_query],
                        [r for _, r in non_query],
                    )
                else:
                    ack = f"Processed {len(non_query)} action(s)"
                await send(ws_response(ack))
            elif not has_task_list:
                await status.set(SystemStatus.TYPING)
                if acknowledger is not None:
                    ack = await acknowledger.acknowledge(intents, results)
                else:
                    ack = f"Processed {len(intents)} intent(s)"
                await send(ws_response(ack))

            await status.set(SystemStatus.IDLE)
        except Exception as e:
            logger.error("Burst processing error: %s", e)
            await send(ws_error(str(e)))
            await status.set(SystemStatus.IDLE)
        finally:
            burst_done.set()

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
            await status.set(SystemStatus.TYPING)

            detector.push(message)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        closed = True
        # Wait for any in-flight burst to finish (up to 5s)
        try:
            await asyncio.wait_for(burst_done.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
