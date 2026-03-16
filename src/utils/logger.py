from __future__ import annotations

"""
Sistema de logging centralizado — MC Launcher.

Uso:
    from src.utils.logger import setup_logging, get_logger

    # En main.py (una sola vez al arrancar):
    setup_logging(version="3.0.0", log_dir=Path.home() / ".ctk-mc-launcher" / "logs")

    # En cualquier módulo:
    _log = get_logger(__name__)
    _log.info("Hola")
    _log.error("Algo falló", exc_info=True)   # exc_info=True adjunta el traceback completo
"""

import logging
import platform
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# ── Estado global ───────────────────────────────────────────────────────────
_LOG_DIR:  Optional[Path] = None
_LOG_FILE: Optional[Path] = None
_initialized: bool = False


# ── Setup ───────────────────────────────────────────────────────────────────

def setup_logging(version: str, log_dir: Path) -> Path:
    """
    Configura el logging para toda la aplicación.

    - Archivo rotativo: max 2 MB por archivo, últimos 5 guardados.
    - Consola: solo WARNING y superior (no inunda la terminal).
    - Primer bloque del log: versión, SO, Python, ruta del log.

    Devuelve la ruta del archivo de log activo.
    """
    global _LOG_DIR, _LOG_FILE, _initialized

    log_dir.mkdir(parents=True, exist_ok=True)
    _LOG_DIR = log_dir

    date_str  = datetime.now().strftime("%Y-%m-%d")
    _LOG_FILE = log_dir / f"launcher_{date_str}.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Evitar duplicar handlers si setup_logging se llama más de una vez
    if root.handlers:
        root.handlers.clear()

    fmt = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Handler: archivo rotativo ────────────────────────────────────────
    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=2 * 1024 * 1024,   # 2 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # ── Handler: consola (solo WARNING+, no molesta en terminal) ─────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)

    _initialized = True

    # ── Cabecera informativa ─────────────────────────────────────────────
    startup_log = logging.getLogger("launcher.startup")
    startup_log.info("=" * 60)
    startup_log.info(f"MC Launcher v{version} — sesión iniciada")
    startup_log.info(
        f"Sistema:  {platform.system()} {platform.release()} "
        f"({platform.machine()}) — {platform.version()}"
    )
    startup_log.info(f"Python:   {sys.version.split()[0]}  ({sys.executable})")
    startup_log.info(f"Log:      {_LOG_FILE}")
    startup_log.info("=" * 60)

    return _LOG_FILE


# ── Helpers ─────────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger nombrado listo para usar."""
    return logging.getLogger(name)


def get_log_file() -> Optional[Path]:
    """Ruta del archivo de log activo (None si no se llamó setup_logging)."""
    return _LOG_FILE


def get_log_dir() -> Optional[Path]:
    """Carpeta donde se guardan todos los logs."""
    return _LOG_DIR


def read_log_tail(lines: int = 200) -> str:
    """
    Devuelve las últimas `lines` líneas del log actual como string.
    Útil para mostrar en un diálogo de diagnóstico o copiar al portapapeles.
    """
    if _LOG_FILE is None or not _LOG_FILE.exists():
        return "(No hay archivo de log disponible)"
    try:
        all_lines = _LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return "\n".join(tail)
    except Exception as exc:
        return f"(Error leyendo log: {exc})"
