from __future__ import annotations

"""Fetches Minecraft Java patch notes from Mojang's launcher content API."""

import urllib.request
import json
from typing import List, Dict

from src.utils.config import NEWS_URL


def fetch_patch_notes(limit: int = 8) -> List[Dict[str, str]]:
    """
    Returns a list of patch note dicts with keys:
        title, version, type, date
    Returns empty list on any network/parse failure.
    """
    try:
        req = urllib.request.Request(
            NEWS_URL,
            headers={"User-Agent": "CustomTK-Minecraft-Launcher/3.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        entries = data.get("entries", [])[:limit]
        result = []
        for e in entries:
            result.append({
                "title":   e.get("title", "Sin título"),
                "version": e.get("version", ""),
                "type":    e.get("type", "release"),
                "date":    e.get("date", ""),
            })
        return result
    except Exception:
        return []
