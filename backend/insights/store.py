"""Atomic JSON file store for insights."""

import json
import os
import tempfile
from pathlib import Path


class InsightStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_all(self, insights: list[dict]) -> None:
        """Atomic write: write to temp file, then os.replace."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix=".insights_"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(insights, f, indent=2, default=str)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def mark_read(self, insight_id: str) -> bool:
        """Mark a single insight as read. Returns True if found."""
        insights = self.load_all()
        for ins in insights:
            if ins["id"] == insight_id:
                ins["read"] = True
                self.save_all(insights)
                return True
        return False
