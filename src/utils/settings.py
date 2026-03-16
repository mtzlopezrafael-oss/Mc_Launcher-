from __future__ import annotations

"""Persistencia de la configuración del usuario entre sesiones."""

import json
from pathlib import Path
from typing import Any, Dict

# FIX-069: importar SETTINGS_FILE de config.py en vez de redefinirlo
from src.utils.config import LAUNCHER_DIR, MINECRAFT_DIR, DEFAULT_RAM_MB, SETTINGS_FILE

_DEFAULTS: Dict[str, Any] = {
    "username":   "Player",
    "version_id": "",
    "ram_mb":     DEFAULT_RAM_MB,
    "game_dir":   str(MINECRAFT_DIR),
}


def load() -> Dict[str, Any]:
    """Carga la configuración guardada. Devuelve defaults si no existe."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        # Rellenar claves faltantes con defaults
        for k, v in _DEFAULTS.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return dict(_DEFAULTS)


def save(username: str, version_id: str, ram_mb: int, game_dir: str) -> None:
    """Guarda la configuración — merges con el JSON existente para no borrar otras claves."""
    LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
    # Leer datos existentes para preservar cualquier otra clave del JSON
    existing: Dict[str, Any] = {}
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            existing = json.load(f)
    except Exception:
        pass
    existing.update({
        "username":   username,
        "version_id": version_id,
        "ram_mb":     ram_mb,
        "game_dir":   game_dir,
    })
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
