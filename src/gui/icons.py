"""
Cargador de iconos para el launcher.
Carga PNGs de assets/icons/{tema}/ como CTkImage con caché en memoria.
El tema activo se lee desde src.utils.config.CURRENT_THEME en tiempo de ejecución.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import customtkinter as ctk
from PIL import Image

# Raíz de iconos: src/gui/ → ../../assets/icons/
_ICONS_ROOT = Path(__file__).parent.parent.parent / "assets" / "icons"

# Caché: (theme, name, w, h) → CTkImage
_cache: Dict[Tuple[str, str, int, int], ctk.CTkImage] = {}


def _icons_dir() -> Path:
    """Devuelve la carpeta del tema activo (light/ o dark/)."""
    try:
        from src.utils.config import CURRENT_THEME
        theme = CURRENT_THEME
    except Exception:
        theme = "light"
    themed = _ICONS_ROOT / theme
    # Fallback al directorio raíz si la carpeta de tema no existe
    return themed if themed.exists() else _ICONS_ROOT


def get(name: str, size: Tuple[int, int] = (18, 18)) -> Optional[ctk.CTkImage]:
    """
    Devuelve el ícono `name` como CTkImage escalado a `size`.
    Retorna None si el archivo no existe (degradación elegante).
    """
    try:
        from src.utils.config import CURRENT_THEME
        theme = CURRENT_THEME
    except Exception:
        theme = "light"

    key = (theme, name, size[0], size[1])
    if key in _cache:
        return _cache[key]

    icon_path = _icons_dir() / f"{name}.png"
    if not icon_path.exists():
        return None

    try:
        img = Image.open(icon_path).convert("RGBA")
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        _cache[key] = ctk_img
        return ctk_img
    except Exception:
        return None


def clear_cache() -> None:
    """Vacía la caché (útil en tests)."""
    _cache.clear()
