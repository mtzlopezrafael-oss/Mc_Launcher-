from __future__ import annotations

"""
Búsqueda e instalación de mods desde Modrinth y CurseForge.

Modrinth:   API pública, sin key.  https://api.modrinth.com/v2
CurseForge: API key embebida en config.CURSEFORGE_API_KEY (igual que Prism Launcher).
            Los usuarios finales no necesitan configurar nada.
"""

import json
import logging
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.utils.config import (
    MODRINTH_API, CURSEFORGE_API,
    CURSEFORGE_GAME_ID, CURSEFORGE_CLASS_MODS, CURSEFORGE_LOADER_MAP,
)
from src.utils.net import (
    JSON_HEADERS, cf_headers, resolve_cf_key, get_json, download_file, safe_filename,
)

_log = logging.getLogger("launcher.mods")

# Alias conservados por compatibilidad con el resto del módulo
_HEADERS_MODRINTH = JSON_HEADERS
_get = get_json


# ══════════════════════════════════════════════════════════════════════════
# MODRINTH
# ══════════════════════════════════════════════════════════════════════════

def search_modrinth(
    query: str,
    mc_version: str,
    loader: str,
    limit: int = 20,
    offset: int = 0,
) -> List[Dict]:
    """
    Busca mods en Modrinth.
    Retorna lista de dicts normalizados con keys:
        id, title, description, downloads, icon_url, source, author, versions, categories
    """
    facets = [["project_type:mod"]]
    if mc_version:
        facets.append([f"versions:{mc_version}"])
    if loader and loader != "vanilla":
        facets.append([f"categories:{loader}"])

    params = {
        "query":  query,
        "facets": json.dumps(facets),
        "limit":  limit,
        "offset": offset,
    }
    url = f"{MODRINTH_API}/search?" + urllib.parse.urlencode(params)
    data = _get(url, headers=_HEADERS_MODRINTH)
    if not data:
        return []

    results = []
    for h in data.get("hits", []):
        results.append({
            "id":          h.get("project_id", ""),
            "title":       h.get("title", ""),
            "description": h.get("description", ""),
            "downloads":   h.get("downloads", 0),
            "icon_url":    h.get("icon_url", ""),
            "author":      h.get("author", ""),
            "versions":    h.get("versions", []),
            "categories":  h.get("categories", []),
            "source":      "modrinth",
            "slug":        h.get("slug", ""),
        })
    return results


def get_modrinth_download(
    project_id: str,
    mc_version: str,
    loader: str,
) -> Optional[Tuple[str, str]]:
    """
    Retorna (download_url, filename) del archivo más reciente compatible.
    None si no hay versión compatible.
    """
    params: Dict = {}
    if mc_version:
        params["game_versions"] = json.dumps([mc_version])
    if loader and loader != "vanilla":
        params["loaders"] = json.dumps([loader])

    url = f"{MODRINTH_API}/project/{project_id}/version"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    data = _get(url, headers=_HEADERS_MODRINTH)
    if not data or not isinstance(data, list):
        return None

    # Tomar la primera versión (más reciente)
    version = data[0]
    files = version.get("files", [])
    if not files:
        return None

    # Preferir el archivo primario
    primary = next((f for f in files if f.get("primary")), files[0])
    dl_url = primary.get("url")
    if not dl_url:
        return None
    return dl_url, primary.get("filename", "mod.jar")


# ══════════════════════════════════════════════════════════════════════════
# CURSEFORGE
# ══════════════════════════════════════════════════════════════════════════

def search_curseforge(
    query: str,
    mc_version: str,
    loader: str,
    api_key: Optional[str] = None,
    limit: int = 20,
) -> List[Dict]:
    """
    Busca mods en CurseForge.
    api_key es opcional — si se omite se usa CURSEFORGE_API_KEY de config.
    Retorna lista normalizada con los mismos keys que Modrinth.
    """
    # Resolver la key (argumento explícito → embedded fallback)
    api_key = resolve_cf_key(api_key)
    if not api_key:
        _log.error("CurseForge API key no configurada. "
                   "Rellena CURSEFORGE_API_KEY en src/utils/config.py.")
        return []

    loader_type = CURSEFORGE_LOADER_MAP.get(loader, 0)
    params = {
        "gameId":        CURSEFORGE_GAME_ID,
        "classId":       CURSEFORGE_CLASS_MODS,
        "searchFilter":  query,
        "pageSize":      limit,
        "sortField":     2,  # 2 = Popularity
        "sortOrder":     "desc",
    }
    if mc_version:
        params["gameVersion"] = mc_version
    if loader_type:
        params["modLoaderType"] = loader_type

    url = f"{CURSEFORGE_API}/mods/search?" + urllib.parse.urlencode(params)
    headers = cf_headers(api_key)
    data = _get(url, headers=headers)
    if not data:
        return []

    results = []
    for mod in data.get("data", []):
        logo = mod.get("logo") or {}
        results.append({
            "id":          str(mod.get("id", "")),
            "title":       mod.get("name", ""),
            "description": mod.get("summary", ""),
            "downloads":   mod.get("downloadCount", 0),
            "icon_url":    logo.get("thumbnailUrl", ""),
            "author":      mod.get("authors", [{}])[0].get("name", "") if mod.get("authors") else "",
            "versions":    [],
            "categories":  [c.get("name", "") for c in mod.get("categories", [])],
            "source":      "curseforge",
            "slug":        mod.get("slug", ""),
        })
    return results


def get_curseforge_download(
    mod_id: str,
    mc_version: str,
    loader: str,
    api_key: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """Retorna (download_url, filename) del archivo más reciente compatible."""
    api_key = resolve_cf_key(api_key)
    if not api_key:
        return None

    loader_type = CURSEFORGE_LOADER_MAP.get(loader, 0)
    params = {"gameVersion": mc_version, "pageSize": 5}
    if loader_type:
        params["modLoaderType"] = loader_type

    url = f"{CURSEFORGE_API}/mods/{mod_id}/files?" + urllib.parse.urlencode(params)
    headers = cf_headers(api_key)
    data = _get(url, headers=headers)
    if not data:
        return None

    files = data.get("data", [])
    if not files:
        return None

    f = files[0]
    dl_url = f.get("downloadUrl")
    if not dl_url:
        return None
    return dl_url, f.get("fileName", "mod.jar")


# ══════════════════════════════════════════════════════════════════════════
# DOWNLOAD & INSTALL
# ══════════════════════════════════════════════════════════════════════════

def download_mod(
    url: str,
    dest_dir: Path,
    filename: str,
    progress_cb=None,
) -> bool:
    """
    Descarga un archivo de mod a dest_dir/filename.
    progress_cb(downloaded_bytes, total_bytes) opcional.
    """
    # Sanitizar filename: solo usar el nombre base, sin rutas relativas (../exploit)
    dest = Path(dest_dir) / safe_filename(filename)
    return download_file(url, dest, progress_cb=progress_cb, timeout=30)


def get_installed_mods(mods_dir: Path) -> List[str]:
    """Retorna lista de nombres de archivos .jar instalados."""
    if not mods_dir.exists():
        return []
    try:
        return sorted(f.name for f in mods_dir.iterdir() if f.suffix == ".jar")
    except PermissionError:
        return []


def uninstall_mod(mods_dir: Path, filename: str) -> bool:
    """Elimina un mod instalado."""
    target = mods_dir / safe_filename(filename)
    try:
        if target.exists():
            target.unlink()
        return True
    except Exception:
        return False


def format_downloads(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)
