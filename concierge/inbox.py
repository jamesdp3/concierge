from __future__ import annotations

import json
from pathlib import Path

from .config import settings
from .models import Message


class Inbox:
    def __init__(self, directory: str | None = None):
        self.directory = Path(directory or settings.inbox_dir)
        self.directory.mkdir(parents=True, exist_ok=True)

    def append(self, message: Message) -> Path:
        filename = f"{message.timestamp.strftime('%Y%m%d_%H%M%S')}_{message.id}.json"
        path = self.directory / filename
        path.write_text(
            json.dumps(message.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return path

    def read_all(self) -> list[Message]:
        messages = []
        for path in sorted(self.directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            messages.append(Message(**data))
        return messages
