from __future__ import annotations

"""
Búsqueda e instalación de modpacks desde Modrinth y CurseForge.

Modrinth:   facets=[["project_type:modpack"]]  — formato .mrpack (ZIP con modrinth.index.json)
CurseForge: classId=4471                       — formato ZIP con manifest.json

Flujo de instalación de un modpack:
  1. Buscar modpacks (search_modpacks_modrinth / search_modpacks_curseforge)
  2. Obtener la versión del modpack compatible (get_modpack_version)
  3. Descargar el archivo del modpack (.mrpack o .zip)
  4. Extraer overrides/ al directorio de la instancia
  5. Descargar cada mod listado en el index
"""

import json
import logging
import os
import shutil
import tempfile
import urllib.request
import urllib.parse
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from src.utils.config import (
    MODRINTH_API, CURSEFORGE_API,
    CURSEFORGE_GAME_ID, CURSEFORGE_API_KEY,
)

_log = logging.getLogger("launcher.modpacks")

_HEADERS_MODRINTH = {
    "User-Agent": "CustomTK-Minecraft-Launcher/3.0",
    "Accept": "application/json",
}

_HEADERS_CF_BASE = {
    "User-Agent": "CustomTK-Minecraft-Launcher/3.0",
    "Accept": "application/json",
}

_TIMEOUT = 10

# CurseForge classId para modpacks
CURSEFORGE_CLASS_MODPACKS = 4471

# Loader map para CurseForge
_CF_LOADER_MAP = {
    "fabric": 4,
    "forge": 1,
    "neoforge": 6,
    "quilt": 5,
}

import re as _re
_VALID_HEADER_RE = _re.compile(r'^[\x20-\x7E]+$')


def _is_valid_api_key(key: str) -> bool:
    if not key or not isinstance(key, str):
        return False
    key = key.strip()
    return bool(key) and bool(_VALID_HEADER_RE.match(key))


def _get(url: str, headers: dict, timeout: int = _TIMEOUT) -> Optional[any]:
    """GET request genérico con manejo de errores."""
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        _log.warning("GET %s falló: %s", url, e)
        return None


def _cf_headers(api_key: Optional[str] = None) -> dict:
    key = api_key or CURSEFORGE_API_KEY
    if not _is_valid_api_key(key):
        return _HEADERS_CF_BASE
    h = dict(_HEADERS_CF_BASE)
    h["x-api-key"] = key.strip()
    return h


# ══════════════════════════════════════════════════════════════════════════
# BÚSQUEDA — MODRINTH
# ══════════════════════════════════════════════════════════════════════════

def search_modpacks_modrinth(
    query: str,
    mc_version: Optional[str] = None,
    loader: Optional[str] = None,
    limit: int = 20,
) -> List[Dict]:
    """Busca modpacks en Modrinth."""
    facets = [["project_type:modpack"]]
    if mc_version:
        facets.append([f"versions:{mc_version}"])
    if loader:
        facets.append([f"categories:{loader}"])

    params = {
        "query": query,
        "limit": limit,
        "facets": json.dumps(facets),
    }
    url = f"{MODRINTH_API}/search?" + urllib.parse.urlencode(params)
    data = _get(url, _HEADERS_MODRINTH)

    if not data or "hits" not in data:
        return []

    results = []
    for hit in data["hits"]:
        results.append({
            "id": hit.get("project_id", hit.get("slug", "")),
            "title": hit.get("title", ""),
            "description": hit.get("description", ""),
            "author": hit.get("author", ""),
            "downloads": hit.get("downloads", 0),
            "icon_url": hit.get("icon_url", ""),
            "source": "modrinth",
            "categories": hit.get("categories", []),
            "versions": hit.get("versions", []),
        })
    return results


# ══════════════════════════════════════════════════════════════════════════
# BÚSQUEDA — CURSEFORGE
# ══════════════════════════════════════════════════════════════════════════

def search_modpacks_curseforge(
    query: str,
    mc_version: Optional[str] = None,
    loader: Optional[str] = None,
    limit: int = 20,
) -> List[Dict]:
    """Busca modpacks en CurseForge."""
    params = {
        "gameId": CURSEFORGE_GAME_ID,
        "classId": CURSEFORGE_CLASS_MODPACKS,
        "searchFilter": query,
        "pageSize": limit,
        "sortField": 2,  # Popularity
        "sortOrder": "desc",
    }
    if mc_version:
        params["gameVersion"] = mc_version
    if loader and loader in _CF_LOADER_MAP:
        params["modLoaderType"] = _CF_LOADER_MAP[loader]

    url = f"{CURSEFORGE_API}/mods/search?" + urllib.parse.urlencode(params)
    data = _get(url, _cf_headers())

    if not data or "data" not in data:
        return []

    results = []
    for item in data["data"]:
        logo = item.get("logo") or {}
        results.append({
            "id": str(item.get("id", "")),
            "title": item.get("name", ""),
            "description": item.get("summary", ""),
            "author": (item.get("authors", [{}])[0].get("name", "")
                       if item.get("authors") else ""),
            "downloads": item.get("downloadCount", 0),
            "icon_url": logo.get("thumbnailUrl", ""),
            "source": "curseforge",
            "categories": [c.get("name", "") for c in item.get("categories", [])],
        })
    return results


# ══════════════════════════════════════════════════════════════════════════
# OBTENER VERSIÓN DE MODPACK PARA DESCARGAR
# ══════════════════════════════════════════════════════════════════════════

def get_modpack_download_modrinth(
    project_id: str,
    mc_version: Optional[str] = None,
    loader: Optional[str] = None,
) -> Optional[Tuple[str, str, str]]:
    """
    Obtiene la URL de descarga del modpack en Modrinth.
    Retorna (url, filename, version_name) o None.
    """
    params = {}
    if mc_version:
        params["game_versions"] = json.dumps([mc_version])
    if loader and loader != "vanilla":
        params["loaders"] = json.dumps([loader])

    url = f"{MODRINTH_API}/project/{project_id}/version"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    data = _get(url, _HEADERS_MODRINTH)
    if not data or not isinstance(data, list) or not data:
        return None

    version = data[0]
    version_name = version.get("name", version.get("version_number", "?"))
    files = version.get("files", [])
    if not files:
        return None

    primary = next((f for f in files if f.get("primary")), files[0])
    dl_url = primary.get("url")
    if not dl_url:
        return None
    filename = primary.get("filename", "modpack.mrpack")
    return dl_url, filename, version_name


def get_modpack_download_curseforge(
    mod_id: str,
    mc_version: Optional[str] = None,
    loader: Optional[str] = None,
) -> Optional[Tuple[str, str, str]]:
    """
    Obtiene la URL de descarga del modpack en CurseForge.
    Retorna (url, filename, version_name) o None.
    """
    url = f"{CURSEFORGE_API}/mods/{mod_id}/files?pageSize=10&sortOrder=desc"
    if mc_version:
        url += f"&gameVersion={mc_version}"
    if loader and loader in _CF_LOADER_MAP:
        url += f"&modLoaderType={_CF_LOADER_MAP[loader]}"

    data = _get(url, _cf_headers())
    if not data or "data" not in data or not data["data"]:
        return None

    file_info = data["data"][0]
    dl_url = file_info.get("downloadUrl")
    filename = file_info.get("fileName", "modpack.zip")
    version_name = file_info.get("displayName", filename)

    # CurseForge a veces no da downloadUrl; intentar construirla
    if not dl_url:
        file_id = file_info.get("id")
        if file_id:
            dl_url = f"https://edge.forgecdn.net/files/{file_id // 1000}/{file_id % 1000}/{filename}"
        else:
            return None

    return dl_url, filename, version_name


# ══════════════════════════════════════════════════════════════════════════
# INSTALACIÓN DE MODPACK
# ══════════════════════════════════════════════════════════════════════════

def install_modpack(
    download_url: str,
    filename: str,
    instance_dir: Path,
    source: str = "modrinth",
    progress_cb: Optional[Callable[[str, int, int], None]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Descarga e instala un modpack en el directorio de la instancia.

    progress_cb(stage, current, total) — progreso por etapas
    log_cb(message) — log informativo

    Flujo:
      1. Descargar el archivo (.mrpack o .zip)
      2. Extraer y leer el manifiesto (modrinth.index.json o manifest.json)
      3. Copiar overrides/ al directorio de la instancia
      4. Descargar cada mod listado en el manifiesto
    """
    def _log(msg: str):
        _logging_log = _log  # evitar shadowing
        if log_cb:
            log_cb(msg)
        _logging_log.info(msg)

    tmp_dir = None
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="mc-modpack-"))
        pack_path = tmp_dir / filename

        # ── 1. Descargar el modpack ──
        _log(f"Descargando modpack ({filename})...")
        req = urllib.request.Request(download_url, headers=_HEADERS_MODRINTH)
        with urllib.request.urlopen(req, timeout=300) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(pack_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb("download", downloaded, total)

        _log(f"Descarga completa: {downloaded / (1024*1024):.1f} MB")

        # ── 2. Extraer el archivo ──
        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir()

        with zipfile.ZipFile(pack_path, "r") as zf:
            # Seguridad: validar path traversal
            for info in zf.infolist():
                if ".." in info.filename or info.filename.startswith("/"):
                    _log("ERROR: archivo ZIP con path traversal detectado")
                    return False
            zf.extractall(extract_dir)

        # ── 3. Determinar formato y procesar ──
        modrinth_index = extract_dir / "modrinth.index.json"
        cf_manifest = extract_dir / "manifest.json"

        mods_dir = instance_dir / "mods"
        mods_dir.mkdir(parents=True, exist_ok=True)

        mods_to_download: List[Tuple[str, str]] = []  # (url, dest_path)

        if modrinth_index.exists():
            # ── Formato Modrinth (.mrpack) ──
            _log("Formato detectado: Modrinth (.mrpack)")
            mods_to_download = _parse_modrinth_index(modrinth_index, instance_dir, _log)
        elif cf_manifest.exists():
            # ── Formato CurseForge ──
            _log("Formato detectado: CurseForge")
            mods_to_download = _parse_curseforge_manifest(cf_manifest, instance_dir, _log)
        else:
            _log("WARN: No se encontró manifiesto, copiando contenido tal cual")
            _copy_overrides(extract_dir, instance_dir, _log)
            return True

        # ── 4. Copiar overrides ──
        for override_name in ("overrides", "client-overrides"):
            override_dir = extract_dir / override_name
            if override_dir.exists():
                _log(f"Copiando {override_name}/...")
                _copy_overrides(override_dir, instance_dir, _log)

        # ── 5. Descargar mods ──
        total_mods = len(mods_to_download)
        if total_mods > 0:
            _log(f"Descargando {total_mods} mods...")

        for i, (mod_url, dest_path) in enumerate(mods_to_download, 1):
            if progress_cb:
                progress_cb("mods", i, total_mods)
            dest = Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                req = urllib.request.Request(mod_url, headers=_HEADERS_MODRINTH)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    with open(dest, "wb") as f:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                _log(f"  [{i}/{total_mods}] {dest.name}")
            except Exception as e:
                _log(f"  [{i}/{total_mods}] ERROR: {dest.name} — {e}")

        _log(f"Modpack instalado correctamente ({total_mods} mods)")
        return True

    except Exception as e:
        _log(f"Error instalando modpack: {e}")
        _log_module = logging.getLogger("launcher.modpacks")
        _log_module.exception("Error en install_modpack")
        return False
    finally:
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _parse_modrinth_index(
    index_path: Path,
    instance_dir: Path,
    log_cb: Callable[[str], None],
) -> List[Tuple[str, str]]:
    """
    Lee modrinth.index.json y retorna lista de (url, dest_path) para descargar.
    """
    try:
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)
    except Exception as e:
        log_cb(f"Error leyendo modrinth.index.json: {e}")
        return []

    mods_to_download = []
    files = index.get("files", [])

    for file_info in files:
        path_rel = file_info.get("path", "")
        downloads = file_info.get("downloads", [])

        if not path_rel or not downloads:
            continue

        # Seguridad: no permitir path traversal
        if ".." in path_rel:
            continue

        dest = instance_dir / path_rel
        url = downloads[0]  # Primer mirror

        # Solo descargar mods del lado cliente o ambos
        env = file_info.get("env", {})
        client_req = env.get("client", "required")
        if client_req == "unsupported":
            continue

        mods_to_download.append((url, str(dest)))

    return mods_to_download


def _parse_curseforge_manifest(
    manifest_path: Path,
    instance_dir: Path,
    log_cb: Callable[[str], None],
) -> List[Tuple[str, str]]:
    """
    Lee manifest.json de CurseForge y retorna lista de (url, dest_path).
    """
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        log_cb(f"Error leyendo manifest.json: {e}")
        return []

    mods_to_download = []
    mods_dir = instance_dir / "mods"

    for file_entry in manifest.get("files", []):
        project_id = file_entry.get("projectID")
        file_id = file_entry.get("fileID")
        if not project_id or not file_id:
            continue

        # Obtener info del archivo desde la API de CurseForge
        url = f"{CURSEFORGE_API}/mods/{project_id}/files/{file_id}"
        data = _get(url, _cf_headers())
        if not data or "data" not in data:
            continue

        file_data = data["data"]
        dl_url = file_data.get("downloadUrl")
        fname = file_data.get("fileName", f"mod_{file_id}.jar")

        if not dl_url:
            # Construir URL alternativa
            dl_url = f"https://edge.forgecdn.net/files/{file_id // 1000}/{file_id % 1000}/{fname}"

        dest = mods_dir / fname
        mods_to_download.append((dl_url, str(dest)))

    return mods_to_download


def _copy_overrides(src_dir: Path, dest_dir: Path, log_cb: Callable[[str], None]) -> None:
    """Copia archivos de overrides al directorio de la instancia."""
    copied = 0
    dest_resolved = dest_dir.resolve()
    for item in src_dir.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(src_dir)
        dest_file = (dest_dir / rel).resolve()
        # Protección path traversal
        if not str(dest_file).startswith(str(dest_resolved)):
            continue
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(item), str(dest_file))
        copied += 1
    log_cb(f"  {copied} archivos copiados desde overrides")
