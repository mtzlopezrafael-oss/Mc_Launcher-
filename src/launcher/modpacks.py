from __future__ import annotations

"""
Búsqueda e instalación de modpacks desde Modrinth y CurseForge.

Modrinth:   facets=[["project_type:modpack"]]  — formato .mrpack (ZIP con modrinth.index.json)
CurseForge: classId=4471                       — formato ZIP con manifest.json

Flujo de instalación de un modpack:
  1. Buscar modpacks (search_modpacks_modrinth / search_modpacks_curseforge)
  2. Obtener la versión del modpack compatible (get_modpack_download_*)
  3. Descargar el archivo del modpack (.mrpack o .zip)
  4. Leer los requisitos (versión de Minecraft + loader) y avisar al llamador
  5. Extraer overrides/ al directorio de la instancia
  6. Descargar (en paralelo) cada mod listado en el index
"""

import json
import logging
import shutil
import tempfile
import urllib.parse
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from src.utils.config import MODRINTH_API, CURSEFORGE_API, CURSEFORGE_GAME_ID
from src.utils.net import (
    JSON_HEADERS, cf_headers, get_json, post_json, download_file, safe_filename,
)

_log = logging.getLogger("launcher.modpacks")

# CurseForge classId para modpacks
CURSEFORGE_CLASS_MODPACKS = 4471

# Loader map para CurseForge
_CF_LOADER_MAP = {
    "fabric": 4,
    "forge": 1,
    "neoforge": 6,
    "quilt": 5,
}

# Descargas simultáneas de mods (un modpack típico tiene 100–300 archivos)
_DOWNLOAD_WORKERS = 6

# (url, ruta destino, sha1 esperado o None)
DownloadItem = Tuple[str, str, Optional[str]]


def _cf_edge_url(file_id: int, filename: str) -> str:
    """URL del CDN de CurseForge para mods que no permiten descarga por API."""
    return (f"https://edge.forgecdn.net/files/{file_id // 1000}/{file_id % 1000}/"
            f"{urllib.parse.quote(filename)}")


def _inside(base: Path, target: Path) -> bool:
    """True si `target` (ya resuelto) queda dentro de `base` (ya resuelto)."""
    try:
        target.relative_to(base)
        return True
    except ValueError:
        return False


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
    data = get_json(url, JSON_HEADERS)

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
    data = get_json(url, cf_headers())

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

    url = f"{MODRINTH_API}/project/{urllib.parse.quote(str(project_id))}/version"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    data = get_json(url, JSON_HEADERS)
    if not data or not isinstance(data, list):
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
    filename = safe_filename(primary.get("filename", ""), "modpack.mrpack")
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
    params: Dict = {"pageSize": 10, "sortOrder": "desc"}
    if mc_version:
        params["gameVersion"] = mc_version
    if loader and loader in _CF_LOADER_MAP:
        params["modLoaderType"] = _CF_LOADER_MAP[loader]
    url = (f"{CURSEFORGE_API}/mods/{urllib.parse.quote(str(mod_id))}/files?"
           + urllib.parse.urlencode(params))

    data = get_json(url, cf_headers())
    if not data or "data" not in data or not data["data"]:
        return None

    file_info = data["data"][0]
    dl_url = file_info.get("downloadUrl")
    filename = safe_filename(file_info.get("fileName", ""), "modpack.zip")
    version_name = file_info.get("displayName", filename)

    # CurseForge a veces no da downloadUrl; intentar construirla
    if not dl_url:
        file_id = file_info.get("id")
        if not file_id:
            return None
        dl_url = _cf_edge_url(int(file_id), filename)

    return dl_url, filename, version_name


# ══════════════════════════════════════════════════════════════════════════
# REQUISITOS DEL MODPACK (versión de Minecraft + loader)
# ══════════════════════════════════════════════════════════════════════════

_MRPACK_LOADER_KEYS = {
    "fabric-loader": "fabric",
    "quilt-loader":  "quilt",
    "forge":         "forge",
    "neoforge":      "neoforge",
}


def parse_mrpack_requirements(index: Dict) -> Dict[str, Optional[str]]:
    """
    Lee `dependencies` de modrinth.index.json, p. ej.
    {"minecraft": "1.20.1", "fabric-loader": "0.15.7"} →
    {"mc_version": "1.20.1", "loader": "fabric", "loader_version": "0.15.7"}
    """
    deps = index.get("dependencies") or {}
    req: Dict[str, Optional[str]] = {
        "mc_version": deps.get("minecraft"), "loader": "vanilla", "loader_version": None,
    }
    for key, loader in _MRPACK_LOADER_KEYS.items():
        if deps.get(key):
            req["loader"], req["loader_version"] = loader, str(deps[key])
            break
    return req


def parse_cf_requirements(manifest: Dict) -> Dict[str, Optional[str]]:
    """
    Lee la sección `minecraft` de manifest.json de CurseForge, p. ej.
    {"version": "1.20.1", "modLoaders": [{"id": "forge-47.2.0", "primary": true}]} →
    {"mc_version": "1.20.1", "loader": "forge", "loader_version": "47.2.0"}
    """
    mc = manifest.get("minecraft") or {}
    req: Dict[str, Optional[str]] = {
        "mc_version": mc.get("version"), "loader": "vanilla", "loader_version": None,
    }
    loaders = mc.get("modLoaders") or []
    primary = next((l for l in loaders if l.get("primary")), loaders[0] if loaders else None)
    if primary and primary.get("id"):
        name, _, version = str(primary["id"]).partition("-")
        name = name.lower()
        if name in ("forge", "neoforge", "fabric", "quilt"):
            req["loader"], req["loader_version"] = name, version or None
    return req


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
    on_requirements: Optional[Callable[[Dict[str, Optional[str]]], None]] = None,
) -> bool:
    """
    Descarga e instala un modpack en el directorio de la instancia.

    progress_cb(stage, current, total) — progreso por etapas
    log_cb(message) — log informativo
    on_requirements(req) — versión de Minecraft y loader que pide el modpack
        ({"mc_version", "loader", "loader_version"}), para ajustar el perfil.

    Retorna False si la instalación falla o si algún mod no se pudo descargar.
    """
    _logger = _log  # capturar logger del módulo antes de shadowing

    def _log(msg: str):
        if log_cb:
            log_cb(msg)
        _logger.info(msg)

    tmp_dir = None
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="mc-modpack-"))
        pack_path = tmp_dir / safe_filename(filename, "modpack.zip")

        # ── 1. Descargar el modpack ──
        _log(f"Descargando modpack ({pack_path.name})...")
        ok = download_file(
            download_url, pack_path, timeout=300,
            progress_cb=(lambda d, t: progress_cb("download", d, t)) if progress_cb else None,
        )
        if not ok:
            _log("ERROR: no se pudo descargar el archivo del modpack")
            return False
        _log(f"Descarga completa: {pack_path.stat().st_size / (1024*1024):.1f} MB")

        # ── 2. Extraer el archivo ──
        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir()

        with zipfile.ZipFile(pack_path, "r") as zf:
            # Seguridad: validar path traversal
            extract_resolved = extract_dir.resolve()
            for info in zf.infolist():
                target = (extract_dir / info.filename).resolve()
                if not _inside(extract_resolved, target):
                    _log("ERROR: archivo ZIP con path traversal detectado")
                    return False
            zf.extractall(extract_dir)

        # ── 3. Determinar formato, requisitos y lista de mods ──
        modrinth_index = extract_dir / "modrinth.index.json"
        cf_manifest = extract_dir / "manifest.json"

        instance_dir = Path(instance_dir)
        (instance_dir / "mods").mkdir(parents=True, exist_ok=True)

        if modrinth_index.exists():
            _log("Formato detectado: Modrinth (.mrpack)")
            index = _read_json(modrinth_index, _log)
            if index is None:
                return False
            requirements = parse_mrpack_requirements(index)
            to_download = _parse_modrinth_index(index, instance_dir, _log)
        elif cf_manifest.exists():
            _log("Formato detectado: CurseForge")
            manifest = _read_json(cf_manifest, _log)
            if manifest is None:
                return False
            requirements = parse_cf_requirements(manifest)
            to_download = _parse_curseforge_manifest(manifest, instance_dir, _log)
        else:
            _log("WARN: No se encontró manifiesto, copiando contenido tal cual")
            _copy_overrides(extract_dir, instance_dir, _log)
            return True

        if requirements.get("mc_version"):
            loader_txt = requirements["loader"] or "vanilla"
            if requirements.get("loader_version"):
                loader_txt += f" {requirements['loader_version']}"
            _log(f"Requisitos: Minecraft {requirements['mc_version']} • {loader_txt}")
            if on_requirements:
                on_requirements(requirements)

        # ── 4. Copiar overrides ──
        for override_name in ("overrides", "client-overrides"):
            override_dir = extract_dir / override_name
            if override_dir.exists():
                _log(f"Copiando {override_name}/...")
                _copy_overrides(override_dir, instance_dir, _log)

        # ── 5. Descargar mods en paralelo ──
        failed = _download_all(to_download, progress_cb, _log)
        total = len(to_download)
        if failed:
            _log(f"⚠ {failed} de {total} archivos no se pudieron descargar — "
                 "el modpack puede no funcionar. Vuelve a instalarlo para reintentar.")
            return False

        _log(f"Modpack instalado correctamente ({total} archivos)")
        return True

    except Exception as e:
        _log(f"Error instalando modpack: {e}")
        _logger.exception("Error en install_modpack")
        return False
    finally:
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _read_json(path: Path, log_cb: Callable[[str], None]) -> Optional[Dict]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception as e:
        log_cb(f"Error leyendo {path.name}: {e}")
        return None


def _download_all(
    items: List[DownloadItem],
    progress_cb: Optional[Callable[[str, int, int], None]],
    log_cb: Callable[[str], None],
) -> int:
    """Descarga todos los archivos en paralelo. Retorna cuántos fallaron."""
    total = len(items)
    if not total:
        return 0
    log_cb(f"Descargando {total} archivos...")
    done = failed = 0
    with ThreadPoolExecutor(max_workers=_DOWNLOAD_WORKERS) as pool:
        futures = {
            pool.submit(download_file, url, Path(dest), None, sha1): Path(dest).name
            for url, dest, sha1 in items
        }
        for fut in as_completed(futures):
            name = futures[fut]
            done += 1
            try:
                ok = fut.result()
            except Exception:
                ok = False
            if ok:
                log_cb(f"  [{done}/{total}] {name}")
            else:
                failed += 1
                log_cb(f"  [{done}/{total}] ERROR: {name}")
            if progress_cb:
                progress_cb("mods", done, total)
    return failed


def _parse_modrinth_index(
    index: Dict,
    instance_dir: Path,
    log_cb: Callable[[str], None],
) -> List[DownloadItem]:
    """Lista de (url, dest_path, sha1) a descargar según modrinth.index.json."""
    base = instance_dir.resolve()
    items: List[DownloadItem] = []

    for file_info in index.get("files", []):
        path_rel = str(file_info.get("path", "")).replace("\\", "/")
        downloads = file_info.get("downloads", [])
        if not path_rel or not downloads:
            continue

        # Solo descargar archivos del lado cliente o ambos
        env = file_info.get("env") or {}
        if env.get("client", "required") == "unsupported":
            continue

        # Seguridad: rechazar rutas absolutas ("/etc/x", "C:/x") y "..", que
        # escribirían fuera de la instancia.
        dest = (instance_dir / path_rel).resolve()
        if Path(path_rel).is_absolute() or ":" in path_rel or not _inside(base, dest):
            log_cb(f"WARN: ruta insegura ignorada en el modpack: {path_rel}")
            continue

        sha1 = (file_info.get("hashes") or {}).get("sha1")
        items.append((downloads[0], str(dest), sha1))

    return items


def _cf_file_info(file_ids: List[int]) -> Dict[int, Dict]:
    """
    Info de archivos de CurseForge por id. Usa el endpoint por lotes
    (POST /mods/files) — una petición en vez de una por mod — y recurre a
    peticiones individuales si el lote falla.
    """
    result: Dict[int, Dict] = {}
    for i in range(0, len(file_ids), 500):
        chunk = file_ids[i:i + 500]
        data = post_json(f"{CURSEFORGE_API}/mods/files", {"fileIds": chunk}, cf_headers())
        if data and isinstance(data.get("data"), list):
            for f in data["data"]:
                if f.get("id") is not None:
                    result[int(f["id"])] = f
    return result


def _parse_curseforge_manifest(
    manifest: Dict,
    instance_dir: Path,
    log_cb: Callable[[str], None],
) -> List[DownloadItem]:
    """Lista de (url, dest_path, sha1) a descargar según manifest.json."""
    entries = [
        (int(e["projectID"]), int(e["fileID"]))
        for e in manifest.get("files", [])
        if e.get("projectID") and e.get("fileID")
    ]
    infos = _cf_file_info([fid for _, fid in entries])

    mods_dir = instance_dir / "mods"
    items: List[DownloadItem] = []
    for project_id, file_id in entries:
        info = infos.get(file_id)
        if info is None:
            data = get_json(f"{CURSEFORGE_API}/mods/{project_id}/files/{file_id}", cf_headers())
            info = (data or {}).get("data")
        if not info:
            log_cb(f"WARN: no se encontró el archivo {file_id} del proyecto {project_id}")
            # Contará como fallo en la descarga
            items.append(("", str(mods_dir / f"mod_{file_id}.jar"), None))
            continue

        fname = safe_filename(info.get("fileName", ""), f"mod_{file_id}.jar")
        dl_url = info.get("downloadUrl") or _cf_edge_url(file_id, fname)
        sha1 = next(
            (h.get("value") for h in info.get("hashes", []) if h.get("algo") == 1),
            None,
        )
        items.append((dl_url, str(mods_dir / fname), sha1))

    return items


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
        if not _inside(dest_resolved, dest_file):
            continue
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(item), str(dest_file))
        copied += 1
    log_cb(f"  {copied} archivos copiados desde overrides")
