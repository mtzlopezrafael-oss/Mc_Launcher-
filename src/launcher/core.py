from __future__ import annotations

"""Launcher core v3 — soporta loaders y verifica instalación antes de descargar."""

import subprocess
import threading
import uuid as uuid_lib
from pathlib import Path
from typing import Callable, Dict, List, Optional

import minecraft_launcher_lib

from src.utils import config
from src.utils.config import LaunchSettings
from src.launcher import java_checker
from src.launcher import loaders

LogFn      = Callable[[str], None]
ProgressFn = Callable[[int, int], None]
DoneFn     = Callable[[Optional[subprocess.Popen]], None]
ErrFn      = Callable[[str], None]


def _make_offline_uuid(username: str) -> str:
    return str(uuid_lib.uuid3(uuid_lib.NAMESPACE_OID, f"OfflinePlayer:{username}"))


def classify_game_line(line: str) -> str:
    """
    Nivel de log ("error" | "warning" | "info") de una línea de salida de
    Minecraft. Usa el formato de log4j ("[hh:mm:ss] [Thread/LEVEL]: ...") y
    solo recurre a heurísticas para trazas de Java, para no marcar como error
    líneas como "Loaded 0 errors".
    """
    upper = line.upper()
    if "/ERROR]" in upper or "/FATAL]" in upper:
        return "error"
    if "/WARN]" in upper:
        return "warning"
    if "/INFO]" in upper or "/DEBUG]" in upper:
        return "info"
    stripped = line.lstrip()
    if (stripped.startswith(("at ", "Caused by:", "Exception in thread"))
            or stripped.split(":", 1)[0].endswith(("Exception", "Error"))):
        return "error"
    return "info"


def resolve_java_for_version(version_id: str, mc_dir: str,
                             system_java: Optional[Path]) -> Optional[str]:
    """
    Java a usar para una versión. Prefiere el runtime que Mojang descarga para
    esa versión (versión de Java correcta: 8 para 1.16, 17 para 1.18–1.20.4,
    21 para 1.20.5+) y recurre al Java del sistema si no hay runtime.
    """
    try:
        info = minecraft_launcher_lib.runtime.get_version_runtime_information(version_id, mc_dir)
        if info:
            exe = minecraft_launcher_lib.runtime.get_executable_path(info["name"], mc_dir)
            if exe and Path(exe).exists():
                return str(exe)
    except Exception:
        pass
    return str(system_java) if system_java else None


class LauncherCore:
    def __init__(self, log_fn: LogFn) -> None:
        self.log = log_fn
        self._install_max: int = 1

    def fetch_versions(self) -> List[Dict[str, str]]:
        try:
            versions = minecraft_launcher_lib.utils.get_version_list()
        except Exception as exc:
            self.log(f"Error obteniendo versiones: {exc}")
            return []
        return [v for v in versions if v.get("type") in config.VERSION_TYPES]

    def download_and_launch(
        self,
        settings: LaunchSettings,
        progress_cb: ProgressFn,
        done_cb: DoneFn,
        error_cb: ErrFn,
        close_on_launch: bool = False,
    ) -> None:
        def worker() -> None:
            mc_dir = str(settings.game_dir)

            # 0. Validar datos esenciales antes de hacer nada
            if not settings.version_id:
                error_cb("El perfil no tiene una versión de Minecraft asignada. Edita el perfil.")
                return
            if not settings.username.strip():
                error_cb("El nombre de usuario no puede estar vacío.")
                return

            self.log(f"Perfil: '{settings.username}' | {settings.version_id} | {settings.loader}")

            # 1. Java del sistema (opcional: Minecraft trae su propio runtime)
            found, java_path, java_ver, message = java_checker.ensure_java()
            if found:
                self.log(message)
            else:
                self.log("Java del sistema no encontrado — se usará el runtime de Mojang.")

            # 2. Directorio de instancia
            settings.game_dir.mkdir(parents=True, exist_ok=True)

            # 3. UUID offline
            offline_uuid = _make_offline_uuid(settings.username)
            self.log(f"UUID offline: {offline_uuid}")

            # 4. Verificar si ya está instalada la versión vanilla
            vanilla_installed = loaders.is_installed("vanilla", settings.version_id, mc_dir)
            if vanilla_installed:
                self.log(f"✓ Versión {settings.version_id} ya instalada.")
                progress_cb(100, 100)  # 100% para vanilla
            else:
                self.log(f"Instalando Minecraft {settings.version_id}...")
                self._install_max = 1  # reset antes de cada instalación
                cb = self._build_callback(progress_cb)
                try:
                    minecraft_launcher_lib.install.install_minecraft_version(
                        settings.version_id, mc_dir, callback=cb,
                    )
                except minecraft_launcher_lib.exceptions.VersionNotFound:
                    error_cb(f"Versión '{settings.version_id}' no encontrada.")
                    return
                except Exception as exc:
                    error_cb(f"Error instalando Minecraft: {exc}")
                    return

            # Java correcto para esta versión (instalado en el paso 4)
            java_exe = resolve_java_for_version(settings.version_id, mc_dir, java_path)
            if not java_exe:
                # La versión ya estaba instalada (p. ej. por otro launcher)
                # pero sin el runtime de Mojang: descargarlo ahora.
                java_exe = self._install_runtime(settings.version_id, mc_dir, progress_cb)
            if java_exe:
                self.log(f"☕ Java: {java_exe}")
            else:
                error_cb(
                    "No hay Java disponible para esta versión. "
                    "Instala Java 17+ o comprueba tu conexión a internet."
                )
                return

            # 5. Instalar loader si no es vanilla
            launch_version_id = settings.version_id
            if settings.loader != "vanilla":
                loader_already = loaders.is_installed(settings.loader, settings.version_id, mc_dir)
                if loader_already:
                    self.log(f"✓ {settings.loader} ya instalado.")
                else:
                    self.log(f"Instalando {settings.loader}...")
                    self._install_max = 1  # reset para el loader
                    cb2 = self._build_callback(progress_cb)
                    ok, err_msg = loaders.install(
                        settings.loader, settings.version_id, mc_dir,
                        loader_version=settings.loader_version,
                        callback=cb2, java=java_exe,
                    )
                    if not ok:
                        error_cb(err_msg or f"Error instalando {settings.loader}.")
                        return

                # Buscar el version_id del loader instalado
                found_id = loaders.find_installed_version_id(
                    settings.loader, settings.version_id, mc_dir
                )
                if found_id:
                    launch_version_id = found_id
                    self.log(f"✓ Versión del loader detectada: {found_id}")
                else:
                    self.log(
                        f"⚠️ ADVERTENCIA: No se encontró el version_id de {settings.loader}. "
                        f"El juego se lanzará sin mod loader — los mods NO cargarán."
                    )

            # 6. Construir opciones y lanzar
            mods_dir = Path(mc_dir) / "mods"
            self.log(f"📁 Directorio de mods: {mods_dir}")
            if mods_dir.exists():
                mods = [f.name for f in mods_dir.iterdir()
                        if f.suffix == ".jar" or f.name.endswith(".jar.disabled")]
                if mods:
                    self.log(f"📦 Mods encontrados ({len(mods)}): {', '.join(mods[:5])}"
                             + (f" … (+{len(mods)-5} más)" if len(mods) > 5 else ""))
                else:
                    self.log("📦 Carpeta mods vacía — no se encontraron .jar")
            else:
                self.log("📦 Carpeta mods no existe aún")

            self.log(f"🚀 Lanzando con version_id: {launch_version_id}")

            launch_options = {
                "username":        settings.username,
                "uuid":            offline_uuid,
                "token":           "0",
                "jvmArguments":    [f"-Xms{settings.ram_mb}M", f"-Xmx{settings.ram_mb}M"],
                "launcherName":    config.LAUNCHER_NAME,
                "launcherVersion": config.LAUNCHER_VERSION,
                "gameDirectory":   mc_dir,
            }
            # Versiones sin runtime propio: usar el Java del sistema detectado
            # en vez de depender de que "java" esté en el PATH.
            if java_path:
                launch_options["defaultExecutablePath"] = str(java_path)
            try:
                cmd = minecraft_launcher_lib.command.get_minecraft_command(
                    launch_version_id, mc_dir, launch_options,
                )
                self.log("Lanzando Minecraft...")
                import platform
                if close_on_launch:
                    # El launcher se cerrará: un PIPE sin lector acabaría
                    # bloqueando o rompiendo la salida del juego.
                    out = subprocess.DEVNULL
                else:
                    out = subprocess.PIPE
                popen_kwargs = {
                    "cwd": mc_dir,
                    "stdout": out,
                    "stderr": subprocess.STDOUT,
                }
                # En Windows: ocultar la ventana de consola negra
                if platform.system() == "Windows":
                    popen_kwargs["creationflags"] = (
                        subprocess.CREATE_NO_WINDOW
                    )
                process = subprocess.Popen(cmd, **popen_kwargs)
                done_cb(process)
            except Exception as exc:
                error_cb(f"No se pudo iniciar: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _install_runtime(self, version_id: str, mc_dir: str,
                         progress_cb: ProgressFn) -> Optional[str]:
        """Descarga el runtime de Java de Mojang para la versión, si lo declara."""
        try:
            info = minecraft_launcher_lib.runtime.get_version_runtime_information(version_id, mc_dir)
            if not info:
                return None
            self.log(f"Descargando Java {info['javaMajorVersion']} de Mojang...")
            self._install_max = 1
            minecraft_launcher_lib.runtime.install_jvm_runtime(
                info["name"], mc_dir, callback=self._build_callback(progress_cb),
            )
            return resolve_java_for_version(version_id, mc_dir, None)
        except Exception as exc:
            self.log(f"No se pudo instalar el runtime de Java: {exc}")
            return None

    def _build_callback(self, progress_cb: ProgressFn) -> Dict[str, Callable]:
        def set_status(s: str)   -> None: self.log(s)
        def set_progress(v: int) -> None: progress_cb(v, self._install_max)
        def set_max(v: int)      -> None: self._install_max = max(1, v)
        return {"setStatus": set_status, "setProgress": set_progress, "setMax": set_max}