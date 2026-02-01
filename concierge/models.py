from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageStatus(str, Enum):
    DELIVERED = "delivered"
    READ = "read"


class SystemStatus(str, Enum):
    IDLE = "idle"
    TYPING = "typing"
    PROCESSING = "processing"


class Message(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: MessageStatus = MessageStatus.DELIVERED


class IntentType(str, Enum):
    NEW_TASK = "new_task"
    MODIFY_TASK = "modify_task"
    PRIORITY_CHANGE = "priority_change"
    CANCEL_TASK = "cancel_task"
    CLARIFICATION = "clarification"
    GENERAL_NOTE = "general_note"
    STATUS_QUERY = "status_query"
    CHAT = "chat"


class IntentClassification(BaseModel):
    intent: IntentType
    heading: str | None = None
    task_id: str | None = None
    priority: str | None = None
    deadline: str | None = None
    scheduled: str | None = None
    tags: list[str] = Field(default_factory=list)
    state: str | None = None
    note: str | None = None
    raw_text: str = ""


class Burst(BaseModel):
    messages: list[Message]
    started_at: datetime
    ended_at: datetime


# WebSocket protocol messages

class WSIncoming(BaseModel):
    type: str = "message"
    text: str


class WSOutgoing(BaseModel):
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


def ws_status_update(message_id: str, status: MessageStatus) -> WSOutgoing:
    return WSOutgoing(
        type="status_update",
        data={"message_id": message_id, "status": status.value},
    )


def ws_system_status(status: SystemStatus) -> WSOutgoing:
    return WSOutgoing(
        type="system_status",
        data={"status": status.value},
    )


def ws_response(text: str) -> WSOutgoing:
    return WSOutgoing(
        type="response",
        data={"text": text, "timestamp": datetime.now(UTC).isoformat()},
    )


def ws_task_list(tasks: list[dict], header: str = "") -> WSOutgoing:
    return WSOutgoing(
        type="task_list",
        data={"tasks": tasks, "header": header, "timestamp": datetime.now(UTC).isoformat()},
    )


def ws_error(message: str) -> WSOutgoing:
    return WSOutgoing(
        type="error",
        data={"message": message},
    )
