from __future__ import annotations

"""Version play history — persisted in LAUNCHER_DIR/history.json."""

import json
from datetime import datetime
from typing import List, Dict

from src.utils.config import HISTORY_FILE, LAUNCHER_DIR, HISTORY_MAX


def load_history() -> List[Dict[str, str]]:
    """Return list of history entries, newest first."""
    try:
        with open(HISTORY_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


def add_entry(version_id: str, username: str) -> None:
    """Prepend an entry and trim to HISTORY_MAX."""
    history = load_history()
    # Remove existing entry for same version so it moves to top
    history = [h for h in history if h.get("version") != version_id]
    history.insert(0, {
        "version":   version_id,
        "username":  username,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    history = history[:HISTORY_MAX]
    LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2, ensure_ascii=False)
