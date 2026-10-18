from __future__ import annotations

"""
Helpers HTTP compartidos (Modrinth, CurseForge, noticias de Mojang).

Antes cada módulo tenía su propio _get(), sus headers y su validación de la
API key de CurseForge; ahora viven aquí.
"""

import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.utils.config import CURSEFORGE_API_KEY, USER_AGENT

_log = logging.getLogger("launcher.net")

DEFAULT_TIMEOUT = 10

JSON_HEADERS: Dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept":     "application/json",
}

# Caracteres válidos en un HTTP header value: ASCII imprimible, sin newlines ni CR
_VALID_HEADER_RE = re.compile(r'^[\x20-\x7E]+$')


def is_valid_api_key(key: Optional[str]) -> bool:
    """
    Valida que la API key sea un string de una sola línea con caracteres ASCII
    imprimibles. Rechaza keys corruptas (p. ej. output de terminal pegado por error).
    """
    if not key or not isinstance(key, str):
        return False
    key = key.strip()
    return bool(key) and bool(_VALID_HEADER_RE.match(key))


def resolve_cf_key(api_key: Optional[str] = None) -> str:
    """API key explícita (si es válida) o la embebida. "" si ninguna es válida."""
    candidate = api_key if api_key is not None else CURSEFORGE_API_KEY
    return candidate.strip() if is_valid_api_key(candidate) else ""


def cf_headers(api_key: Optional[str] = None) -> Dict[str, str]:
    """Headers JSON + x-api-key de CurseForge (si hay una key válida)."""
    headers = dict(JSON_HEADERS)
    key = resolve_cf_key(api_key)
    if key:
        headers["x-api-key"] = key
    return headers


def _request_json(req: urllib.request.Request, timeout: int) -> Optional[Any]:
    short = req.full_url.split("?")[0]
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _log.warning("HTTP %s en %s — %s", e.code, short, e.reason)
    except Exception as e:
        _log.warning("%s en %s: %s", e.__class__.__name__, short, e)
    return None


def get_json(url: str, headers: Optional[Dict[str, str]] = None,
             timeout: int = DEFAULT_TIMEOUT) -> Optional[Any]:
    """GET que devuelve el JSON decodificado, o None ante cualquier error."""
    return _request_json(urllib.request.Request(url, headers=headers or JSON_HEADERS), timeout)


def post_json(url: str, payload: Any, headers: Optional[Dict[str, str]] = None,
              timeout: int = DEFAULT_TIMEOUT) -> Optional[Any]:
    """POST con cuerpo JSON. Devuelve el JSON de respuesta, o None ante error."""
    h = dict(headers or JSON_HEADERS)
    h["Content-Type"] = "application/json"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=h, method="POST",
    )
    return _request_json(req, timeout)


def safe_filename(name: str, default: str = "mod.jar") -> str:
    """Nombre base sin rutas (../exploit), sin caracteres de control y ≤255 chars."""
    base = Path(str(name).replace("\\", "/")).name
    if (not base or base in (".", "..") or len(base) > 255
            or any(ord(c) < 32 for c in base)):
        return default
    return base


def download_file(
    url: str,
    dest: Path,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    expected_sha1: Optional[str] = None,
    timeout: int = 60,
) -> bool:
    """
    Descarga `url` a `dest` pasando por `dest.part` y renombrando al final, de
    modo que nunca queda un .jar a medias que Minecraft intente cargar.
    Si se da `expected_sha1`, verifica el hash antes de aceptar el archivo.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    sha1 = hashlib.sha1()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            total = int(r.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            with open(part, "wb") as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha1.update(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb(downloaded, total)
        if expected_sha1 and sha1.hexdigest().lower() != expected_sha1.lower():
            _log.error("SHA-1 no coincide para %s — descarga descartada", dest.name)
            part.unlink(missing_ok=True)
            return False
        os.replace(part, dest)
        return True
    except Exception as e:
        _log.warning("Fallo descargando %s: %s", url.split("?")[0], e)
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
        return False
