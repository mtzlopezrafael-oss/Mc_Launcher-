from __future__ import annotations

"""Instalación de mod loaders usando minecraft-launcher-lib v8.0.

API: minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
IDs válidos: fabric, forge, neoforge, quilt
"""

from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import minecraft_launcher_lib


def purge_empty_jars(mc_dir: str) -> int:
    """
    Elimina archivos .jar con 0 bytes dentro de mc_dir/libraries.
    Estos causan el error 'wrong Checksum' de Forge/NeoForge cuando
    una descarga anterior falló silenciosamente.
    Retorna el número de archivos eliminados.
    """
    libraries_dir = Path(mc_dir) / "libraries"
    if not libraries_dir.exists():
        return 0
    count = 0
    for jar in libraries_dir.rglob("*.jar"):
        if jar.stat().st_size == 0:
            jar.unlink()
            count += 1
    return count


def get_versions(loader_id: str, mc_version: str, stable_only: bool = False) -> List[str]:
    """
    Versiones disponibles del loader para una versión de Minecraft.
    stable_only=False devuelve todas (incluyendo betas).
    stable_only=True devuelve solo versiones estables.
    """
    if loader_id == "vanilla":
        return []
    try:
        loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
        # API correcta en v8.0: get_loader_versions(mc_version, stable_only)
        versions = loader.get_loader_versions(mc_version, stable_only)
        return [str(v) for v in versions] if versions else []
    except Exception:
        return []


def get_stable_versions(loader_id: str, mc_version: str) -> List[str]:
    """Solo versiones estables del loader."""
    return get_versions(loader_id, mc_version, stable_only=True)


def get_latest_version(loader_id: str, mc_version: str) -> Optional[str]:
    """Versión más reciente del loader para una versión de Minecraft."""
    if loader_id == "vanilla":
        return None
    try:
        loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
        return loader.get_latest_loader_version(mc_version)
    except Exception:
        # Fallback: tomar el primero de la lista completa
        versions = get_versions(loader_id, mc_version)
        return versions[0] if versions else None


def install(
    loader_id: str,
    mc_version: str,
    mc_dir: str,
    loader_version: Optional[str] = None,
    callback: Optional[Dict[str, Callable]] = None,
    java: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Instala el loader.
    Retorna (True, "") si fue exitoso, (False, mensaje_error) si falló.

    Antes de instalar, limpia JARs vacíos para evitar el error
    'wrong Checksum' causado por descargas incompletas anteriores.
    """
    if loader_id == "vanilla":
        return True, ""

    log = callback.get("setStatus") if callback else None

    # Limpiar JARs vacíos antes de instalar
    removed = purge_empty_jars(mc_dir)
    if removed > 0:
        if log:
            log(f"🧹 Limpiados {removed} archivos corruptos (0 bytes) antes de instalar.")

    try:
        loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
        kwargs: Dict = {"callback": callback or {}}
        if loader_version:
            kwargs["loader_version"] = loader_version
        if java:
            kwargs["java"] = java
        loader.install(mc_version, mc_dir, **kwargs)
        return True, ""

    except Exception as e:
        err_str = str(e)

        # Detectar específicamente el error de checksum
        if "wrong Checksum" in err_str or "Checksum" in err_str:
            # Intentar limpiar y reintentar una vez
            if log:
                log(f"⚠️ Checksum inválido detectado. Limpiando archivos corruptos y reintentando...")
            removed2 = purge_empty_jars(mc_dir)
            if log:
                log(f"🧹 Eliminados {removed2} archivos corruptos.")
            try:
                loader2 = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
                loader2.install(mc_version, mc_dir, **kwargs)
                if log:
                    log(f"✅ {loader_id} instalado correctamente en el reintento.")
                return True, ""
            except Exception as e2:
                msg = (
                    f"Error de checksum persistente en {loader_id}. "
                    f"Verifica tu conexión a internet y vuelve a intentarlo. Detalle: {e2}"
                )
                if log:
                    log(f"❌ {msg}")
                return False, msg

        msg = f"Error instalando {loader_id}: {err_str}"
        if log:
            log(f"❌ {msg}")
        return False, msg


def find_installed_version_id(
    loader_id: str,
    mc_version: str,
    mc_dir: str,
) -> Optional[str]:
    """
    Busca el version_id instalado del loader en el directorio.
    Retorna None si no está instalado aún.
    """
    if loader_id == "vanilla":
        return mc_version
    try:
        installed = minecraft_launcher_lib.utils.get_installed_versions(mc_dir)
        for v in installed:
            vid = v.get("id", "")
            if loader_id == "forge" and f"{mc_version}-forge" in vid:
                return vid
            elif loader_id == "neoforge" and vid.startswith("neoforge-") and mc_version in vid:
                return vid
            elif loader_id in ("fabric", "quilt") and f"{loader_id}-loader-" in vid and mc_version in vid:
                return vid
        return None
    except Exception:
        return None


def is_installed(loader_id: str, mc_version: str, mc_dir: str) -> bool:
    """Verifica si ya está instalado el loader para esa versión de MC."""
    if loader_id == "vanilla":
        try:
            installed = minecraft_launcher_lib.utils.get_installed_versions(mc_dir)
            return any(v.get("id") == mc_version for v in installed)
        except Exception:
            return False
    return find_installed_version_id(loader_id, mc_version, mc_dir) is not None
