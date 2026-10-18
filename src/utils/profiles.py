from __future__ import annotations

"""Perfil de instancia al estilo Prism — cada perfil es una instalación independiente."""

import json
import logging
import re
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from src.utils.config import INSTANCES_DIR, DEFAULT_RAM_MB, PROFILES_FILE
from src.utils.jsonio import atomic_write_json, backup_corrupt

_log = logging.getLogger("launcher.profiles")

# Serializa load→modificar→save: touch_last_played() corre en un hilo de fondo
# mientras la UI puede estar guardando otro cambio al mismo tiempo.
_lock = threading.RLock()
_corrupt_backed_up = False


def load() -> List[Dict]:
    global _corrupt_backed_up
    with _lock:
        try:
            with open(PROFILES_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as e:
            _log.error("profiles.json corrupto: %s", e)
            # Respaldar antes de que el próximo save() lo sobrescriba
            if not _corrupt_backed_up:
                _corrupt_backed_up = backup_corrupt(PROFILES_FILE) is not None
            return []
        except Exception as e:
            _log.error("Error cargando perfiles: %s", e)
            return []


def save(profiles: List[Dict]) -> None:
    with _lock:
        atomic_write_json(PROFILES_FILE, profiles)


def _make_slug(name: str) -> str:
    # Sanitizar el slug: solo alfanuméricos, guiones y puntos
    slug = re.sub(r'[^a-z0-9._-]', '-', name.lower())
    return re.sub(r'-+', '-', slug).strip('-.') or "instancia"


def _unique_instance_dir(slug: str, profiles: List[Dict]) -> str:
    """
    Devuelve INSTANCES_DIR/<slug> sin chocar con la carpeta de otro perfil ni
    con una carpeta existente (dos perfiles llamados igual compartirían mods
    y mundos).
    """
    used = {str(p.get("game_dir", "")).lower() for p in profiles}
    candidate = INSTANCES_DIR / slug
    n = 2
    while str(candidate).lower() in used or candidate.exists():
        candidate = INSTANCES_DIR / f"{slug}-{n}"
        n += 1
    return str(candidate)


def add(name: str, mc_version: str, loader: str = "vanilla",
        loader_version: Optional[str] = None, ram_mb: int = DEFAULT_RAM_MB,
        username: str = "Player", game_dir: Optional[str] = None) -> Dict:
    with _lock:
        profiles = load()
        p = {
            "id":             str(uuid.uuid4()),
            "name":           name,
            "mc_version":     mc_version,
            "loader":         loader,
            "loader_version": loader_version,
            "ram_mb":         ram_mb,
            "username":       username,
            "game_dir":       game_dir or _unique_instance_dir(_make_slug(name), profiles),
            "created_at":     datetime.now().isoformat(),
            "last_played":    None,
        }
        profiles.append(p)
        save(profiles)
        return p


def update(profile_id: str, **kwargs) -> bool:
    """Actualiza campos del perfil. Retorna False si el perfil no existe."""
    with _lock:
        profiles = load()
        found = False
        for p in profiles:
            if p.get("id") == profile_id:
                p.update(kwargs)
                found = True
        if found:
            save(profiles)
        else:
            _log.warning("update(): perfil %s no encontrado", profile_id)
        return found


def delete(profile_id: str) -> None:
    with _lock:
        save([p for p in load() if p.get("id") != profile_id])


def get(profile_id: str) -> Optional[Dict]:
    return next((p for p in load() if p.get("id") == profile_id), None)


def touch_last_played(profile_id: str) -> None:
    update(profile_id, last_played=datetime.now().isoformat())
