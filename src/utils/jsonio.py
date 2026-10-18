from __future__ import annotations

"""Lectura/escritura segura de archivos JSON de datos del usuario."""

import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

_log = logging.getLogger("launcher.jsonio")


def atomic_write_json(path: Path, data: Any) -> None:
    """
    Escribe `data` en `path` de forma atómica: primero a un archivo temporal en
    la misma carpeta y luego os.replace(). Si el proceso muere a mitad de la
    escritura, el archivo original queda intacto (nunca a medio escribir).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def backup_corrupt(path: Path) -> Path | None:
    """
    Copia un JSON corrupto a `<nombre>.corrupt-<fecha>` para que no se pierda
    cuando el launcher vuelva a escribir el archivo. Retorna la ruta del backup.
    """
    path = Path(path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        shutil.copy2(path, backup)
        _log.error("Archivo JSON corrupto respaldado en %s", backup)
        return backup
    except OSError as exc:
        _log.error("No se pudo respaldar %s: %s", path, exc)
        return None
