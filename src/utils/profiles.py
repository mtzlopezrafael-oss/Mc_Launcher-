from __future__ import annotations

"""Perfil de instancia al estilo Prism — cada perfil es una instalación independiente."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.utils.config import LAUNCHER_DIR, INSTANCES_DIR, DEFAULT_RAM_MB, MINECRAFT_DIR, PROFILES_FILE


def _defaults() -> Dict:
    return {
        "id":             str(uuid.uuid4()),
        "name":           "New Profile",
        "mc_version":     "1.21.1",
        "loader":         "vanilla",
        "loader_version": None,
        "ram_mb":         DEFAULT_RAM_MB,
        "username":       "Player",
        "game_dir":       str(INSTANCES_DIR / "new-profile"),
        "created_at":     datetime.now().isoformat(),
        "last_played":    None,
    }


def load() -> List[Dict]:
    try:
        with open(PROFILES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as e:
        import sys
        print(f"[profiles] profiles.json corrupto: {e}", file=sys.stderr)
        return []
    except Exception as e:
        import sys
        print(f"[profiles] Error cargando perfiles: {e}", file=sys.stderr)
        return []


def save(profiles: List[Dict]) -> None:
    LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)


def add(name: str, mc_version: str, loader: str = "vanilla",
        loader_version: Optional[str] = None, ram_mb: int = DEFAULT_RAM_MB,
        username: str = "Player", game_dir: Optional[str] = None) -> Dict:
    import re as _re
    # Sanitizar el slug: solo alfanuméricos, guiones y puntos
    slug = name.lower()
    slug = _re.sub(r'[^a-z0-9._-]', '-', slug)
    slug = _re.sub(r'-+', '-', slug).strip('-') or "instancia"
    # FIX-070: construir el perfil directamente sin _defaults() que generaba
    # un UUID y timestamp que se sobreescribían inmediatamente
    p = {
        "id":             str(uuid.uuid4()),
        "name":           name,
        "mc_version":     mc_version,
        "loader":         loader,
        "loader_version": loader_version,
        "ram_mb":         ram_mb,
        "username":       username,
        "game_dir":       game_dir if game_dir else str(INSTANCES_DIR / slug),
        "created_at":     datetime.now().isoformat(),
        "last_played":    None,
    }
    profiles = load()
    profiles.append(p)
    save(profiles)
    return p


def update(profile_id: str, **kwargs) -> None:
    profiles = load()
    for p in profiles:
        if p["id"] == profile_id:
            p.update(kwargs)
    save(profiles)


def delete(profile_id: str) -> None:
    save([p for p in load() if p["id"] != profile_id])


def get(profile_id: str) -> Optional[Dict]:
    return next((p for p in load() if p["id"] == profile_id), None)


def touch_last_played(profile_id: str) -> None:
    update(profile_id, last_played=datetime.now().isoformat())
