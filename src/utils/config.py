from __future__ import annotations

"""Launcher-wide configuration, constants and design system — v3.0"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ── Paths ──────────────────────────────────────────────────────────────────
MINECRAFT_DIR: Path  = Path.home() / ".minecraft"
LAUNCHER_DIR:  Path  = Path.home() / ".ctk-mc-launcher"
INSTANCES_DIR: Path  = LAUNCHER_DIR / "instances"
HISTORY_FILE:  Path  = LAUNCHER_DIR / "history.json"
SETTINGS_FILE: Path  = LAUNCHER_DIR / "settings.json"
PROFILES_FILE: Path  = LAUNCHER_DIR / "profiles.json"
LOG_DIR:       Path  = LAUNCHER_DIR / "logs"

# ── Metadata ───────────────────────────────────────────────────────────────
LAUNCHER_NAME:    str = "CustomTK Minecraft Launcher"
LAUNCHER_VERSION: str = "3.0.4"   # Actualizar aquí y en version.json al publicar

# ── Window ─────────────────────────────────────────────────────────────────
APP_WIDTH:       int = 1100
APP_HEIGHT:      int = 680
THEME:           str = "dark-blue"
APPEARANCE_MODE: str = "dark"

# ── Paletas de color ────────────────────────────────────────────────────────
_LIGHT_COLORS: Dict[str, str] = {
    "bg":          "#f0f1f5",  # gris claro — fondo principal
    "panel":       "#ffffff",  # blanco — tarjetas y paneles
    "panel_light": "#f7f8fc",  # blanco roto — hover y elementos anidados
    "border":      "#dde0ec",  # borde sutil
    "accent":      "#3b7dd8",  # azul principal
    "accent_dim":  "#e8f0fd",  # azul muy claro — estado activo/seleccionado
    "accent2":     "#7c3aed",  # violeta secundario
    "text":        "#1a1d2e",  # casi negro — texto principal
    "text_dim":    "#7480a0",  # gris azulado — texto secundario
    "success":     "#16a34a",  # verde
    "error":       "#dc2626",  # rojo
    "warning":     "#d97706",  # ámbar
    "play":        "#eef4ff",  # azul muy claro — fondo botón play
    "play_hover":  "#d5e6ff",  # azul claro — hover botón play
    "fabric":      "#b07040",
    "forge":       "#c05820",
    "neoforge":    "#c06800",
    "vanilla":     "#2d8a3e",
}

_DARK_COLORS: Dict[str, str] = {
    "bg":          "#000000",  # negro puro
    "panel":       "#0c0c0c",  # casi negro — tarjetas
    "panel_light": "#141414",  # gris muy oscuro — hover
    "border":      "#1e1e1e",  # borde sutil oscuro
    "accent":      "#4a90d9",  # azul principal (más brillante en negro)
    "accent_dim":  "#0d2040",  # azul muy oscuro — estado activo/seleccionado
    "accent2":     "#8b5cf6",  # violeta
    "text":        "#e8eaf8",  # blanco azulado — texto principal
    "text_dim":    "#484858",  # gris oscuro — texto secundario
    "success":     "#22c55e",  # verde brillante
    "error":       "#f43f5e",  # rojo brillante
    "warning":     "#f59e0b",  # ámbar brillante
    "play":        "#080e1a",  # azul muy oscuro — fondo botón play
    "play_hover":  "#0f1c38",  # azul oscuro — hover botón play
    "fabric":      "#dbb69a",
    "forge":       "#e07030",
    "neoforge":    "#f08010",
    "vanilla":     "#55aa55",
}

_DARK_LOADER_COLORS: Dict[str, str] = {
    "vanilla":  "#55aa55",
    "fabric":   "#dbb69a",
    "forge":    "#e07030",
    "neoforge": "#f08010",
}

_LIGHT_LOADER_COLORS: Dict[str, str] = {
    "vanilla":  "#2d8a3e",
    "fabric":   "#b07040",
    "forge":    "#c05820",
    "neoforge": "#c06800",
}

# ── Tema activo — se carga desde settings.json al importar el módulo ────────
def _read_active_theme() -> str:
    """Lee el tema guardado sin importar nada más del proyecto."""
    import json as _j
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as _f:
            return _j.load(_f).get("theme", "light")
    except Exception:
        return "light"

CURRENT_THEME: str = _read_active_theme()

# COLORS y LOADER_COLORS son dicts mutables — se actualizan con el tema activo.
COLORS:       Dict[str, str] = dict(_LIGHT_COLORS if CURRENT_THEME == "light" else _DARK_COLORS)
LOADER_COLORS: Dict[str, str] = dict(_LIGHT_LOADER_COLORS if CURRENT_THEME == "light" else _DARK_LOADER_COLORS)

# ── Loaders ────────────────────────────────────────────────────────────────
LOADER_IDS:   List[str]       = ["vanilla", "fabric", "forge", "neoforge"]
LOADER_ICONS: Dict[str, str]  = {
    "vanilla":  "⬜",
    "fabric":   "🌿",
    "forge":    "🔨",
    "neoforge": "🔥",
}

# ── CurseForge ─────────────────────────────────────────────────────────────
# API key embebida en tiempo de compilación — igual que Prism Launcher.
# Registra tu aplicación en https://console.curseforge.com → "API Keys"
# para obtener tu propia key de desarrollador (gratuita) y pégala aquí.
# Los usuarios finales no necesitan configurar nada.
CURSEFORGE_API_KEY: str = "$2a$10$.kruo.ERigoNiJTo.XANC.G5bbflyRU/Ht/fWe49ncoPlvWaNEKIK"

CURSEFORGE_GAME_ID: int = 432     # Minecraft
CURSEFORGE_CLASS_MODS: int = 6   # Mods class
CURSEFORGE_LOADER_MAP: Dict[str, int] = {
    "fabric":   4,
    "forge":    1,
    "neoforge": 6,
    "vanilla":  0,
}

# ── Options ────────────────────────────────────────────────────────────────
RAM_OPTIONS_MB: List[int] = [512, 1024, 2048, 4096, 8192, 16384]
DEFAULT_RAM_MB: int        = 2048
VERSION_TYPES:  List[str]  = ["release", "snapshot"]
HISTORY_MAX:    int        = 15
LOG_LINE_LIMIT: int        = 800

# ── External APIs ──────────────────────────────────────────────────────────
NEWS_URL:        str = "https://launchercontent.mojang.com/v2/javaPatchNotes.json"
AVATAR_URL:      str = "https://minotar.net/avatar/{username}/80"
MODRINTH_API:    str = "https://api.modrinth.com/v2"
CURSEFORGE_API:  str = "https://api.curseforge.com/v1"

# ── Auto-update ─────────────────────────────────────────────────────────────
UPDATE_VERSION_URL: str = (
    "https://raw.githubusercontent.com/mtzlopezrafael-oss/Mc_Launcher-/main/version.json"
)


def format_ram_label(ram_mb: int) -> str:
    return f"{ram_mb // 1024} GB" if ram_mb >= 1024 else f"{ram_mb} MB"


@dataclass
class LaunchSettings:
    username:       str
    version_id:     str
    ram_mb:         int            = DEFAULT_RAM_MB
    game_dir:       Path           = field(default_factory=lambda: MINECRAFT_DIR)
    loader:         str            = "vanilla"
    loader_version: Optional[str]  = None
