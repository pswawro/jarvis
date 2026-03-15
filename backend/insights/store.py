"""Atomic JSON file store for insights with file locking."""

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


class InsightStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock_path = self.path.with_suffix(".lock")

    @contextmanager
    def _file_lock(self, shared: bool = False):
        """Context manager for file locking. Use shared=True for read-only operations."""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(self._lock_path, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()

    def _load(self) -> list[dict]:
        """Internal load without locking — caller must hold lock."""
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def load_all(self) -> list[dict]:
        """Load all insights with a shared lock for read consistency."""
        with self._file_lock(shared=True):
            return self._load()

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
        """Mark a single insight as read. Returns True if found. Uses file lock."""
        with self._file_lock(shared=False):
            insights = self._load()
            for ins in insights:
                if ins["id"] == insight_id:
                    ins["read"] = True
                    self.save_all(insights)
                    return True
            return False
