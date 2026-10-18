from __future__ import annotations

"""Fetches Minecraft Java patch notes from Mojang's launcher content API."""

from typing import List, Dict

from src.utils.config import NEWS_URL
from src.utils.net import get_json


def fetch_patch_notes(limit: int = 8) -> List[Dict[str, str]]:
    """
    Returns a list of patch note dicts with keys:
        title, version, type, date
    Returns empty list on any network/parse failure.
    """
    data = get_json(NEWS_URL, timeout=6)
    if not isinstance(data, dict):
        return []

    result = []
    for e in data.get("entries", [])[:limit]:
        result.append({
            "title":   e.get("title", "Sin título"),
            "version": e.get("version", ""),
            "type":    e.get("type", "release"),
            # La API devuelve ISO 8601 ("2024-06-13T12:00:00Z"): mostrar solo la fecha
            "date":    str(e.get("date", ""))[:10],
        })
    return result
