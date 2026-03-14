"""Per-user preferences store (JSON file, atomic writes)."""

import json
import os
import tempfile
from pathlib import Path

_PREFS_PATH = Path(__file__).parent.parent / "data" / "user_preferences.json"


class UserPreferencesStore:
    def __init__(self, path: Path = _PREFS_PATH):
        self._path = path

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save(self, data: dict):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _get_user(self, data: dict, user_id: str) -> dict:
        return data.get(user_id, {"insight_bookmarks": []})

    def get_bookmarks(self, user_id: str) -> list[str]:
        data = self._load()
        return self._get_user(data, user_id).get("insight_bookmarks", [])

    def add_bookmark(self, user_id: str, insight_id: str):
        data = self._load()
        user = self._get_user(data, user_id)
        if insight_id not in user.get("insight_bookmarks", []):
            user.setdefault("insight_bookmarks", []).append(insight_id)
        data[user_id] = user
        self._save(data)

    def remove_bookmark(self, user_id: str, insight_id: str):
        data = self._load()
        if user_id not in data:
            return
        user = data[user_id]
        bookmarks = user.get("insight_bookmarks", [])
        if insight_id in bookmarks:
            bookmarks.remove(insight_id)
            user["insight_bookmarks"] = bookmarks
            self._save(data)
