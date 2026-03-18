from __future__ import annotations

"""
Sistema de auto-actualización del launcher.

Flujo:
  1. check_for_updates()  → consulta version.json en GitHub (raw URL)
  2. Si hay versión nueva  → retorna UpdateInfo
  3. download_update()     → descarga el ZIP del repositorio a un directorio temporal
  4. apply_update()        → extrae el ZIP sobre el directorio de la app y reinicia

El version.json remoto debe tener este formato:
    {
        "version":      "3.1.0",
        "download_url": "https://github.com/USER/REPO/archive/refs/heads/main.zip",
        "changelog":    "Descripción de los cambios"
    }
"""

import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


# ── Utilidades de versión ──────────────────────────────────────────────────────

def _parse_version(v: str) -> tuple:
    """Convierte "3.1.0" → (3, 1, 0). Ignora el prefijo 'v'."""
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except Exception:
        return (0,)


def is_newer(remote: str, current: str) -> bool:
    """Retorna True si la versión remota es mayor que la actual."""
    return _parse_version(remote) > _parse_version(current)


# ── Datos de actualización ─────────────────────────────────────────────────────

@dataclass
class UpdateInfo:
    version:      str
    download_url: str
    changelog:    str = ""


# ── Comprobación remota ────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent":    "CustomTK-Minecraft-Launcher/3.0",
    "Cache-Control": "no-cache",
}


def check_for_updates(
    current_version: str,
    version_url: str,
    timeout: int = 6,
) -> Optional[UpdateInfo]:
    """
    Descarga version.json desde `version_url` y compara con `current_version`.
    Retorna UpdateInfo si hay una versión más nueva, None en caso contrario.
    Nunca lanza excepciones — retorna None ante cualquier error.
    """
    if not version_url or "YOUR_USER" in version_url or "YOUR_REPO" in version_url:
        return None  # URL de placeholder — repo aún no configurado

    try:
        req = urllib.request.Request(version_url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        remote_version = data.get("version", "0.0.0")
        if not is_newer(remote_version, current_version):
            return None

        return UpdateInfo(
            version=remote_version,
            download_url=data.get("download_url", ""),
            changelog=data.get("changelog", ""),
        )
    except Exception:
        return None


# ── Descarga ───────────────────────────────────────────────────────────────────

def download_update(
    update_info: UpdateInfo,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    timeout: int = 120,
) -> Optional[Path]:
    """
    Descarga el ZIP de la actualización a un directorio temporal.
    progress_cb(downloaded_bytes, total_bytes) — opcional.
    Retorna la ruta al ZIP descargado, o None si falló.
    """
    if not update_info.download_url:
        return None

    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="mc-launcher-update-"))
        zip_path = tmp_dir / "update.zip"

        req = urllib.request.Request(update_info.download_url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk = 65536  # 64 KB
            with open(zip_path, "wb") as f:
                while True:
                    data = resp.read(chunk)
                    if not data:
                        break
                    f.write(data)
                    downloaded += len(data)
                    if progress_cb and total:
                        progress_cb(downloaded, total)

        return zip_path
    except Exception:
        return None


# ── Aplicación ─────────────────────────────────────────────────────────────────

def apply_update(
    zip_path: Path,
    app_dir: Optional[Path] = None,
) -> bool:
    """
    Extrae `zip_path` y copia los archivos sobre `app_dir` (directorio de la app).
    El ZIP de GitHub tiene un directorio raíz llamado "REPO-BRANCH/"; lo saltamos.
    Retorna True si el proceso completó sin errores críticos.

    No sobrescribe:
      - settings.json (configuración del usuario)
      - profiles.json (perfiles del usuario)
      - assets/ (iconos y recursos locales)
    """
    if not zip_path or not zip_path.exists():
        return False

    if app_dir is None:
        # Directorio raíz del proyecto (dos niveles arriba de este archivo)
        app_dir = Path(__file__).parent.parent

    _SKIP_PREFIXES = {"assets/", "assets\\"}
    _SKIP_FILES = {"settings.json", "profiles.json", "history.json"}

    try:
        extract_dir = zip_path.parent / "extracted"
        extract_dir.mkdir(exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Validar que no haya path traversal en el ZIP
            for info in zf.infolist():
                if ".." in info.filename or info.filename.startswith("/"):
                    return False
            zf.extractall(extract_dir)

        # El ZIP de GitHub tiene un directorio raíz (p. ej. "launcher-main/")
        roots = [d for d in extract_dir.iterdir() if d.is_dir()]
        source_dir = roots[0] if len(roots) == 1 else extract_dir

        # Copiar recursivamente, respetando exclusiones
        _copy_tree(source_dir, app_dir, _SKIP_PREFIXES, _SKIP_FILES)

        # Limpiar temporales
        shutil.rmtree(zip_path.parent, ignore_errors=True)
        return True

    except Exception:
        return False


def _copy_tree(
    src: Path,
    dst: Path,
    skip_prefixes: set,
    skip_files: set,
) -> None:
    """Copia recursivamente src → dst, saltando rutas en skip_prefixes/skip_files."""
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        rel_str = str(rel).replace("\\", "/")

        # Saltar archivos/carpetas excluidos
        if any(rel_str.startswith(p) for p in skip_prefixes):
            continue
        if item.name in skip_files:
            continue
        if item.name.startswith("."):
            continue  # Ignorar .git, .gitignore, etc.

        dest = (dst / rel).resolve()
        # Proteger contra path traversal
        if not str(dest).startswith(str(dst.resolve())):
            continue
        if item.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(item), str(dest))


# ── Instalador EXE (modo compilado PyInstaller) ────────────────────────────────

def download_and_run_installer(
    installer_url: str,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    timeout: int = 300,
) -> bool:
    """
    Descarga el instalador .exe de GitHub Releases a un archivo temporal y lo ejecuta.
    Se usa cuando el launcher corre como EXE compilado (PyInstaller frozen).

    El instalador se encarga de desinstalar la versión anterior e instalar la nueva.
    Retorna True si el instalador se lanzó correctamente.
    """
    import logging
    import os
    import subprocess
    import tempfile

    log = logging.getLogger("launcher.updater")

    try:
        # Descargar el .exe instalador a un archivo temporal
        tmp_fd, tmp_path = tempfile.mkstemp(suffix="_mc_launcher_setup.exe")
        os.close(tmp_fd)

        log.info("Descargando instalador desde: %s", installer_url)
        req = urllib.request.Request(installer_url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            log.info("Content-Length reportado: %d bytes", total)
            downloaded = 0
            chunk = 65536  # 64 KB
            last_pct_reported = -1
            with open(tmp_path, "wb") as f:
                while True:
                    data = resp.read(chunk)
                    if not data:
                        break
                    f.write(data)
                    downloaded += len(data)
                    if progress_cb:
                        if total:
                            pct = int(downloaded / total * 100)
                            # Solo reportar cada 5% para no saturar el UI
                            if pct >= last_pct_reported + 5:
                                last_pct_reported = pct
                                progress_cb(downloaded, total)
                        else:
                            # Sin Content-Length: reportar MB descargados cada 512KB
                            if downloaded % (512 * 1024) < chunk:
                                progress_cb(downloaded, 0)

        file_size = os.path.getsize(tmp_path)
        log.info("Descarga completa: %d bytes en %s", file_size, tmp_path)

        if file_size < 100_000:
            # Un instalador real no pesa menos de 100KB — probablemente es un 404 HTML
            log.error("Archivo descargado muy pequeno (%d bytes), posible error", file_size)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return False

        # Ejecutar el instalador y salir del launcher actual
        log.info("Lanzando instalador: %s", tmp_path)
        subprocess.Popen([tmp_path], shell=False)
        return True

    except Exception as exc:
        log.exception("Error descargando/ejecutando instalador: %s", exc)
        return False


# ── Reinicio post-actualización ────────────────────────────────────────────────

def restart_launcher() -> None:
    """Reemplaza el proceso actual con una nueva instancia del launcher."""
    import os
    python = sys.executable
    args = [python] + sys.argv
    if sys.platform == "win32":
        import subprocess
        subprocess.Popen(args)
        sys.exit(0)
    else:
        os.execv(python, args)
