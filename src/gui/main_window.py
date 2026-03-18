"""
Minecraft Launcher - Main Window
Adapted from Next.js/React design to Python customtkinter

Ventana principal: layout, sidebar, barra inferior, navegación y lanzamiento.
Las páginas individuales están en src/gui/views/.
"""

import sys
import threading
from pathlib import Path
from typing import Optional, Dict, List

import customtkinter as ctk

from src.utils.logger import get_logger as _get_logger
_mw_log = _get_logger("launcher.gui")

from src.gui.components import (
    COLORS, LOADER_COLORS,
    AvatarWidget, PlayButton, ProgressBarWithLabel, NavButton,
)
from src.gui.views import HomeView, NewsView, LogView, SettingsView, InstanceDetailView

# Iconos PNG para la barra lateral
try:
    from src.gui.icons import get as _ico
except ImportError:
    def _ico(name, size=(18, 18)):  # type: ignore[misc]
        return None

# Auto-updater
try:
    from src.updater import (
        check_for_updates, download_update, apply_update,
        download_and_run_installer, UpdateInfo,
    )
    from src.utils.config import UPDATE_VERSION_URL
    _UPDATER_AVAILABLE = True
except ImportError:
    _UPDATER_AVAILABLE = False
    UPDATE_VERSION_URL = ""

# Launcher back-end
try:
    from src.launcher.core import LauncherCore, LaunchSettings
    from src.launcher.java_checker import ensure_java
    from src.utils.config import MINECRAFT_DIR
except ImportError:
    # Stubs mínimos para desarrollo/testing
    class LauncherCore:
        def __init__(self, log_fn): self._log = log_fn
        def fetch_versions(self): return []
        def download_and_launch(self, *a, **kw): pass

    class LaunchSettings:
        def __init__(self, **kw): self.__dict__.update(kw)

    def ensure_java():
        return (True, "", "21.0.10", "Java found")

    MINECRAFT_DIR = Path.home() / ".minecraft"


class MainWindow(ctk.CTk):
    """
    Main application window for the Minecraft Launcher.
    Layout: Sidebar (230px) | Content (flexible) | Bottom Bar (80px)
    """

    APP_VERSION = "3.2.0"
    WINDOW_WIDTH = 1100
    WINDOW_HEIGHT = 680
    SIDEBAR_WIDTH = 230
    BOTTOM_BAR_HEIGHT = 80

    NAV_ITEMS = [
        {"id": "home",     "label": "Inicio",   "icon": "🏠", "icon_name": "home"},
        {"id": "news",     "label": "Noticias", "icon": "📰", "icon_name": "newspaper"},
        {"id": "log",      "label": "Log",      "icon": "💻", "icon_name": "terminal"},
        {"id": "settings", "label": "Ajustes",  "icon": "⚙️", "icon_name": "settings"},
    ]

    def __init__(self):
        super().__init__()

        # Configure window
        self.title("MC Launcher")
        self.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.minsize(900, 550)
        self.resizable(True, True)
        self.configure(fg_color=COLORS["bg"])
        self._is_fullscreen = False

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # ── Shared state ──────────────────────────────────────────
        self._current_section = "home"
        self._selected_profile_id: Optional[str] = self._load_setting("selected_profile_id", None)
        self._profiles: List[Dict] = []
        self._java_status = {"found": False, "version": "", "message": "Checking..."}
        self._is_launching = False
        self._close_on_launch: bool = self._load_setting("close_on_launch", False)
        self._all_versions: List[str] = []      # IDs filtrados (lo que ven los diálogos)
        self._all_versions_raw: List[Dict] = [] # Todos los dicts crudos de la API
        self._show_snapshots: bool = self._load_setting("show_snapshots", False)
        self._update_info: Optional[object] = None   # UpdateInfo si hay actualización disponible
        self.core = LauncherCore(self.log)

        # ── Nav buttons / pages references ────────────────────────
        self._nav_buttons: Dict[str, NavButton] = {}
        self._pages: Dict[str, ctk.CTkFrame] = {}
        self._instance_detail_view: Optional[ctk.CTkFrame] = None

        # ── Build UI ──────────────────────────────────────────────
        self._build_layout()
        self._build_sidebar()
        self._build_bottom_bar()
        self._build_views()

        # ── Fullscreen shortcut (F11) ────────────────────────────
        self.bind("<F11>", lambda e: self.toggle_fullscreen())

        # ── Initial data ──────────────────────────────────────────
        self._load_initial_data()
        self._show_page("home")
        # ── Check for updates (background, no-blocking) ───────────
        self._check_update_async()

    # =================================================================
    #  LAYOUT
    # =================================================================

    def _build_layout(self):
        """Create the main layout structure."""
        self._main_container = ctk.CTkFrame(self, fg_color="transparent")
        self._main_container.pack(fill="both", expand=True)

        self._main_container.grid_rowconfigure(0, weight=1)
        self._main_container.grid_rowconfigure(1, weight=0)
        self._main_container.grid_columnconfigure(0, weight=0)
        self._main_container.grid_columnconfigure(1, weight=1)

        # Sidebar
        self._sidebar = ctk.CTkFrame(
            self._main_container, width=self.SIDEBAR_WIDTH,
            fg_color=COLORS["panel"], corner_radius=0,
        )
        self._sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
        self._sidebar.grid_propagate(False)

        # Content area
        self._content = ctk.CTkFrame(
            self._main_container, fg_color=COLORS["bg"], corner_radius=0,
        )
        self._content.grid(row=0, column=1, sticky="nsew")

        # Bottom bar
        self._bottom_bar_frame = ctk.CTkFrame(
            self._main_container, height=self.BOTTOM_BAR_HEIGHT,
            fg_color=COLORS["panel"], corner_radius=0,
        )
        self._bottom_bar_frame.grid(row=1, column=1, sticky="sew")
        self._bottom_bar_frame.grid_propagate(False)

    def _build_sidebar(self):
        """Build the sidebar with navigation."""
        # Logo + fullscreen button
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=16, pady=(20, 8))

        ctk.CTkLabel(logo_frame, text="⛏️", font=ctk.CTkFont(size=24)).pack(side="left")
        ctk.CTkLabel(
            logo_frame, text="MC Launcher",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=COLORS["text"],
        ).pack(side="left", padx=(8, 0))

        _fs_icon = _ico("maximize", (16, 16))
        _fs_kw = {"image": _fs_icon} if _fs_icon else {}
        self._fullscreen_btn = ctk.CTkButton(
            logo_frame, text="" if _fs_icon else "⛶", width=28, height=28,
            fg_color="transparent", hover_color=COLORS["panel_light"],
            text_color=COLORS["text_dim"], font=ctk.CTkFont(size=14),
            corner_radius=6, command=self.toggle_fullscreen, **_fs_kw,
        )
        self._fullscreen_btn.pack(side="right")

        ctk.CTkLabel(
            self._sidebar, text=f"v{self.APP_VERSION}",
            font=ctk.CTkFont(size=11), text_color=COLORS["text_dim"],
        ).pack(anchor="w", padx=16, pady=(0, 16))

        # Separator
        ctk.CTkFrame(self._sidebar, height=1, fg_color=COLORS["border"]).pack(
            fill="x", padx=16, pady=(0, 16),
        )

        # Nav items
        nav_container = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        nav_container.pack(fill="x", padx=12)

        for item in self.NAV_ITEMS:
            nav_icon = _ico(item.get("icon_name", ""), (18, 18))
            btn = NavButton(
                nav_container,
                text=item["label"],
                icon=item["icon"],        # fallback emoji si no hay PNG
                ctk_image=nav_icon,       # PNG tiene prioridad
                is_active=(item["id"] == self._current_section),
                command=lambda s=item["id"]: self._on_nav_click(s),
            )
            btn.pack(fill="x", pady=2)
            self._nav_buttons[item["id"]] = btn

        # Spacer
        ctk.CTkFrame(self._sidebar, fg_color="transparent").pack(fill="both", expand=True)

        # Banner de actualización disponible (oculto hasta que haya update)
        self._update_banner = ctk.CTkFrame(
            self._sidebar,
            fg_color=COLORS["accent_dim"],
            corner_radius=8,
            border_color=COLORS["accent"],
            border_width=1,
        )
        # No se hace pack aquí — aparece solo cuando hay update

        self._update_banner_label = ctk.CTkLabel(
            self._update_banner,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["accent"],
            wraplength=180,
            justify="left",
        )
        self._update_banner_label.pack(padx=10, pady=(8, 4), anchor="w")

        self._update_banner_btn = ctk.CTkButton(
            self._update_banner,
            text="⬇  Instalar actualización",
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent2"],
            text_color="#ffffff",
            corner_radius=6,
            command=self._on_install_update,
        )
        self._update_banner_btn.pack(fill="x", padx=10, pady=(0, 8))

        # Java status
        self._java_status_frame = ctk.CTkFrame(
            self._sidebar, fg_color=COLORS["panel_light"], corner_radius=8,
        )
        self._java_status_frame.pack(fill="x", padx=12, pady=(0, 16))

        self._java_label = ctk.CTkLabel(
            self._java_status_frame, text="☕ Checking Java...",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
        )
        self._java_label.pack(padx=12, pady=8)

    def _build_bottom_bar(self):
        """Build the bottom bar with profile info and play button."""
        # Left: Avatar + Profile Info
        left = ctk.CTkFrame(self._bottom_bar_frame, fg_color="transparent")
        left.pack(side="left", fill="y", padx=20)

        self._avatar = AvatarWidget(left, size=48, username="Steve")
        self._avatar.pack(side="left", pady=16)

        info = ctk.CTkFrame(left, fg_color="transparent")
        info.pack(side="left", padx=(12, 0))

        self._username_label = ctk.CTkLabel(
            info, text="Steve",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["text"],
        )
        self._username_label.pack(anchor="w")

        self._profile_info_label = ctk.CTkLabel(
            info, text="No profile selected",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
        )
        self._profile_info_label.pack(anchor="w")

        # Right: Discord + Play button + Progress
        right = ctk.CTkFrame(self._bottom_bar_frame, fg_color="transparent")
        right.pack(side="right", fill="y", padx=20)

        self._play_button = PlayButton(right, command=self._on_play_click)
        self._play_button.pack(side="right", pady=16)

        # Botón de Discord (al lado izquierdo del Play)
        _dc_icon = _ico("discord", (28, 28))
        _dc_kw = {"image": _dc_icon} if _dc_icon else {}
        self._discord_btn = ctk.CTkButton(
            right, text="" if _dc_icon else "Discord", width=44, height=44,
            fg_color=COLORS["panel_light"],
            hover_color="#5865F2",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12),
            corner_radius=10,
            command=self._open_discord,
            **_dc_kw,
        )
        self._discord_btn.pack(side="right", padx=(0, 12), pady=16)

        self._launch_progress = ProgressBarWithLabel(right, width=200)

    # =================================================================
    #  VIEWS
    # =================================================================

    def _build_views(self):
        """Create all page views."""
        self._home_view            = HomeView(self._content, self)
        self._news_view            = NewsView(self._content, self)
        self._log_view             = LogView(self._content, self)
        self._settings_view        = SettingsView(self._content, self)
        self._instance_detail_view = InstanceDetailView(self._content, self)

        self._pages = {
            "home":     self._home_view,
            "news":     self._news_view,
            "log":      self._log_view,
            "settings": self._settings_view,
            "instance": self._instance_detail_view,
        }

    # =================================================================
    #  NAVIGATION
    # =================================================================

    def _on_nav_click(self, section: str):
        if section == self._current_section:
            return
        for nav_id, btn in self._nav_buttons.items():
            btn.set_active(nav_id == section)
        self._current_section = section
        self._show_page(section)

    def _show_page(self, page_id: str):
        for pid, frame in self._pages.items():
            if pid == page_id:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    # =================================================================
    #  DATA LOADING
    # =================================================================

    def open_instance_detail(self, profile_id: str) -> None:
        """Abre la vista de detalle para el perfil indicado."""
        prof = None
        for p in self._profiles:
            if p.get("id") == profile_id:
                prof = p
                break
        if prof is None:
            # intentar carga fresca desde disco
            from src.utils import profiles as _prof
            prof = _prof.get(profile_id)
        if prof is None:
            self.log(f"Perfil no encontrado: {profile_id}", "error")
            return

        # Desactivar todos los botones de nav (estamos fuera del nav)
        for btn in self._nav_buttons.values():
            btn.set_active(False)
        self._current_section = "instance"

        self._instance_detail_view.load_profile(prof)
        self._show_page("instance")

    def _load_initial_data(self):
        self._check_java_async()
        threading.Thread(target=self._fetch_versions, daemon=True).start()
        self._home_view.refresh()
        self._news_view.refresh()

    def _fetch_versions(self):
        try:
            # FIX-064: reutilizar self.core en vez de crear otro LauncherCore
            self._all_versions_raw = self.core.fetch_versions()
            self._apply_version_filter()
        except Exception as e:
            self._all_versions_raw = []
            self._all_versions = []
            self.log(f"Error cargando versiones: {e}", "error")

    def _apply_version_filter(self) -> None:
        """Filtra _all_versions_raw según _show_snapshots y guarda los IDs."""
        if self._show_snapshots:
            self._all_versions = [v["id"] for v in self._all_versions_raw]
        else:
            self._all_versions = [
                v["id"] for v in self._all_versions_raw
                if v.get("type") == "release"
            ]

    def _check_java_async(self):
        def check():
            try:
                found, path, version, message = ensure_java()
                self._java_status = {"found": found, "version": version, "message": message}
            except Exception as e:
                self._java_status = {"found": False, "version": "", "message": str(e)}
            try:
                self.after(0, self._update_java_status_ui)
            except Exception:
                pass

        threading.Thread(target=check, daemon=True).start()

    def _update_java_status_ui(self):
        if not self.winfo_exists():
            return
        if self._java_status["found"]:
            ver = self._java_status["version"] or "?"
            self._java_label.configure(
                text=f"☕ Java {ver} ✓",
                text_color=COLORS["success"],
            )
        else:
            self._java_label.configure(
                text="☕ Java no encontrado ✗",
                text_color=COLORS["error"],
            )

    # =================================================================
    #  PUBLIC HELPERS  (used by views)
    # =================================================================

    def get_selected_profile(self) -> Optional[Dict]:
        """Retorna el perfil seleccionado actualmente, o None."""
        if not self._selected_profile_id:
            return None
        for p in self._profiles:
            if p.get("id") == self._selected_profile_id:
                return p
        return None

    def _update_bottom_bar_info(self):
        # Persistir perfil seleccionado
        self._save_setting("selected_profile_id", self._selected_profile_id)
        profile = self.get_selected_profile()
        if profile:
            username = profile.get("username", "Steve")
            mc_ver = profile.get("mc_version", "?")
            loader = profile.get("loader", "vanilla").capitalize()
            ram = profile.get("ram_mb", 4096) // 1024
            self._username_label.configure(text=username)
            self._profile_info_label.configure(text=f"MC {mc_ver} • {loader} • {ram}GB")
            self._avatar.refresh(username)
        else:
            self._username_label.configure(text="Steve")
            self._profile_info_label.configure(text="No profile selected")

    # ── Auto-update ───────────────────────────────────────────────

    def _check_update_async(self) -> None:
        """Comprueba actualizaciones en un hilo de fondo."""
        if not _UPDATER_AVAILABLE:
            return

        def _check():
            try:
                info = check_for_updates(self.APP_VERSION, UPDATE_VERSION_URL)
            except Exception:
                info = None
            if info is not None:
                try:
                    self.after(0, lambda: self._on_update_found(info))
                except Exception:
                    pass

        threading.Thread(target=_check, daemon=True).start()

    def _on_update_found(self, info) -> None:
        """Muestra el banner de actualización en la sidebar."""
        self._update_info = info
        self._update_banner_label.configure(
            text=f"🆕 Versión {info.version} disponible\n{info.changelog[:80]}",
        )
        self._update_banner.pack(fill="x", padx=12, pady=(0, 8), before=self._java_status_frame)
        self.log(
            f"🆕 Actualización disponible: v{info.version} — ve a Ajustes para instalar",
            "success",
        )

    def _on_install_update(self) -> None:
        """
        Inicia la descarga e instalación de la actualización.

        - EXE compilado (PyInstaller frozen): descarga el instalador .exe de
          GitHub Releases y lo ejecuta. El instalador desinstala la versión
          anterior e instala la nueva automáticamente.
        - Código fuente (desarrollo): descarga el ZIP del repo y copia los archivos.
        """
        if not self._update_info or not _UPDATER_AVAILABLE:
            return

        self._update_banner_btn.configure(text="Descargando...", state="disabled")
        self.log(f"Descargando actualización v{self._update_info.version}...")

        info = self._update_info
        is_frozen = getattr(sys, "frozen", False)  # True cuando corre como EXE compilado

        def _progress(downloaded: int, total: int) -> None:
            if total:
                pct = int(downloaded / total * 100)
                msg = f"Descargando... {pct}%"
            else:
                mb = downloaded / (1024 * 1024)
                msg = f"Descargando... {mb:.1f} MB"
            try:
                self.after(0, lambda m=msg: self._update_banner_btn.configure(text=m))
            except Exception:
                pass

        def _do_update():
            if is_frozen:
                # ── Modo EXE: descargar y ejecutar el instalador de GitHub Releases ──
                ver = info.version
                installer_url = (
                    f"https://github.com/mtzlopezrafael-oss/Mc_Launcher-"
                    f"/releases/download/v{ver}"
                    f"/MC_Launcher_v{ver}_Windows_x64_Setup.exe"
                )
                _mw_log.info("URL del instalador: %s", installer_url)
                self.log(f"Descargando instalador v{ver} desde GitHub Releases...")
                ok = download_and_run_installer(installer_url, progress_cb=_progress)
                if ok:
                    try:
                        self.after(0, self._update_installer_launched)
                    except Exception:
                        pass
                else:
                    _mw_log.error("download_and_run_installer retorno False")
                    try:
                        self.after(0, lambda: self._update_error(
                            "No se pudo descargar el instalador. "
                            "Descargalo manualmente desde GitHub Releases."
                        ))
                    except Exception:
                        pass
            else:
                # ── Modo fuente: ZIP update (desarrollo) ──────────────────────────
                zip_path = download_update(info, progress_cb=_progress)
                if zip_path is None:
                    try:
                        self.after(0, lambda: self._update_error(
                            "No se pudo descargar la actualización"
                        ))
                    except Exception:
                        pass
                    return
                self.log("Aplicando actualización...")
                ok = apply_update(zip_path)
                if ok:
                    try:
                        self.after(0, self._update_success)
                    except Exception:
                        pass
                else:
                    try:
                        self.after(0, lambda: self._update_error(
                            "Error al aplicar la actualización"
                        ))
                    except Exception:
                        pass

        threading.Thread(target=_do_update, daemon=True).start()

    def _update_installer_launched(self) -> None:
        """El instalador nuevo fue descargado y lanzado. Cerrar el launcher."""
        self.log("✅ Instalador lanzado — cerrando el launcher para actualizar...", "success")
        self._update_banner_btn.configure(text="✅ Instalando...", state="disabled")
        # Esperar 2 segundos y cerrar para que el instalador tome el control
        self.after(2000, lambda: sys.exit(0))

    def _update_success(self) -> None:
        self.log("✅ Actualización aplicada — reiniciando...", "success")
        self._update_banner_btn.configure(text="✅ Reiniciando...")
        try:
            self.after(1500, self._restart)
        except Exception:
            self._restart()

    def _update_error(self, msg: str) -> None:
        self.log(f"❌ {msg}", "error")
        self._update_banner_btn.configure(
            text="⬇  Instalar actualización",
            state="normal",
        )

    # ── Snapshot preference ───────────────────────────────────────

    def _open_discord(self) -> None:
        """Abre el servidor de Discord en el navegador."""
        import webbrowser
        webbrowser.open("https://discord.gg/bE78ef8wRU")
        self.log("Abriendo servidor de Discord...")

    def toggle_fullscreen(self) -> None:
        """Alterna entre ventana normal y pantalla completa."""
        self._is_fullscreen = not self._is_fullscreen
        self.attributes("-fullscreen", self._is_fullscreen)
        # Actualizar el botón / tooltip
        if self._is_fullscreen:
            _ic_name = "minimize"
            _fallback = "⮌"
        else:
            _ic_name = "maximize"
            _fallback = "⛶"
        new_icon = _ico(_ic_name, (16, 16))
        if new_icon:
            self._fullscreen_btn.configure(image=new_icon, text="")
        else:
            self._fullscreen_btn.configure(text=_fallback)

    def change_theme(self, theme: str) -> None:
        """Guarda el tema y reinicia el launcher para aplicarlo."""
        self._save_setting("theme", theme)
        import os, sys
        self.log(f"Cambiando tema a '{theme}' — reiniciando...", "info")
        try:
            self.after(300, self._restart)
        except Exception:
            self._restart()

    def _restart(self) -> None:
        import os, sys
        python = sys.executable
        args   = [python] + sys.argv
        self.destroy()
        if sys.platform == "win32":
            import subprocess
            subprocess.Popen(args)
            sys.exit(0)
        else:
            os.execv(python, args)

    def set_show_snapshots(self, value: bool) -> None:
        """Llamado por SettingsView al cambiar el toggle de snapshots."""
        self._show_snapshots = value
        self._apply_version_filter()
        self._save_setting("show_snapshots", value)
        label = "activados" if value else "desactivados"
        self.log(f"Snapshots {label}")

    # ── Persistent settings helpers ───────────────────────────────

    def _load_setting(self, key: str, default):
        """Lee un valor de settings.json, devuelve default si no existe."""
        import json as _json
        try:
            from src.utils.config import SETTINGS_FILE
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                return _json.load(f).get(key, default)
        except Exception:
            return default

    def _save_setting(self, key: str, value) -> None:
        """Guarda un valor en settings.json sin borrar las otras claves."""
        import json as _json
        try:
            from src.utils.config import LAUNCHER_DIR, SETTINGS_FILE
            LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
            data: dict = {}
            try:
                with open(SETTINGS_FILE, encoding="utf-8") as f:
                    data = _json.load(f)
            except Exception:
                pass
            data[key] = value
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                _json.dump(data, f, indent=2)
        except Exception:
            pass

    # =================================================================
    #  PLAY / LAUNCH
    # =================================================================

    def _on_play_click(self):
        if self._is_launching:
            return

        profile = self.get_selected_profile()
        if not profile:
            self.log("Selecciona un perfil para jugar", "warning")
            return

        if not self._java_status["found"]:
            self.log("Java no está instalado", "error")
            return

        self._is_launching = True
        self._play_button.set_launching(True)

        self._launch_progress.pack(side="left", padx=(0, 16), pady=16)
        self._launch_progress.set_progress(0, "Preparando...")
        self.log(f"Iniciando {profile.get('name')}...")

        def progress_callback(current: int, maximum: int):
            progress = current / maximum if maximum > 0 else 0
            try:
                self.after(0, lambda: self._launch_progress.set_progress(
                    progress, f"Descargando... {int(progress * 100)}%",
                ))
            except Exception:
                pass

        def done_callback(process):
            try:
                self.after(0, self._on_launch_complete)
                # Cambiar a pestaña de Logs para ver la salida del juego
                self.after(0, lambda: self._navigate("log"))
            except Exception:
                pass

            from src.utils import profiles as _prof
            _prof.touch_last_played(profile.get("id"))
            self.log("Juego iniciado", "success")

            # Leer stdout/stderr del proceso y enviarlo al log del launcher
            if process and process.stdout:
                self._read_game_output(process)

            # FIX-062: usar la variable booleana, NO el widget — se ejecuta desde Thread
            if self._close_on_launch:
                try:
                    self.after(2000, self.destroy)
                except Exception:
                    pass

        def error_callback(message: str):
            try:
                self.after(0, lambda: self._on_launch_error(message))
            except Exception:
                pass

        def launch():
            try:
                settings = LaunchSettings(
                    username=profile.get("username", "Steve"),
                    version_id=profile.get("mc_version", "1.21"),
                    ram_mb=profile.get("ram_mb", 4096),
                    game_dir=Path(profile.get("game_dir", "") or str(MINECRAFT_DIR)),
                    loader=profile.get("loader", "vanilla"),
                    loader_version=profile.get("loader_version"),
                )
                self.core.download_and_launch(
                    settings,
                    progress_cb=progress_callback,
                    done_cb=done_callback,
                    error_cb=error_callback,
                    close_on_launch=self._close_on_launch,
                )
            except Exception as e:
                error_callback(str(e))

        threading.Thread(target=launch, daemon=True).start()

    def _on_launch_complete(self):
        # No resetear _is_launching aqui — se resetea cuando Minecraft se cierra
        self._launch_progress.pack_forget()
        self._play_button.set_playing(True)

    def _on_game_exited(self):
        """Minecraft se cerró — restaurar botón de Play."""
        if not self.winfo_exists():
            return
        self._is_launching = False
        self._play_button.set_playing(False)

    def _on_launch_error(self, message: str):
        self._is_launching = False
        # FIX-063: NO resetear _close_on_launch ni recrear LauncherCore
        self._play_button.set_launching(False)
        self._launch_progress.pack_forget()
        self.log(f"Error al iniciar: {message}", "error")

    def _read_game_output(self, process: "subprocess.Popen") -> None:
        """Lee stdout/stderr del proceso de Minecraft y lo envía al LogView."""
        import subprocess as _sp

        def _reader():
            try:
                for raw_line in process.stdout:
                    if not self.winfo_exists():
                        break
                    try:
                        line = raw_line.decode("utf-8", errors="replace").rstrip()
                    except Exception:
                        line = str(raw_line).rstrip()
                    if not line:
                        continue
                    # Detectar nivel por contenido de la línea
                    lower = line.lower()
                    if "error" in lower or "exception" in lower or "fatal" in lower:
                        lvl = "error"
                    elif "warn" in lower:
                        lvl = "warning"
                    else:
                        lvl = "info"
                    try:
                        self.after(0, lambda m=line, l=lvl: self.log(f"[MC] {m}", l))
                    except Exception:
                        break
                # Proceso terminó
                retcode = process.wait()
                try:
                    if retcode == 0:
                        self.after(0, lambda: self.log("[MC] Minecraft se cerró normalmente", "success"))
                    else:
                        self.after(0, lambda r=retcode: self.log(
                            f"[MC] Minecraft se cerró con código {r}", "warning"
                        ))
                    # Restaurar botón de Play
                    self.after(0, self._on_game_exited)
                except Exception:
                    pass
            except Exception:
                pass

        threading.Thread(target=_reader, daemon=True, name="mc-output-reader").start()

    # =================================================================
    #  LOGGING
    # =================================================================

    def log(self, message: str, level: str = "info"):
        """
        Envía un mensaje al LogView y al archivo de log.
        Thread-safe: despacha al hilo principal para la UI.
        """
        # ── Archivo de log (siempre, desde cualquier hilo) ────────────
        _file_log = getattr(_mw_log, level, None) or _mw_log.info
        _file_log(message)

        # ── UI (sólo en hilo principal vía after) ─────────────────────
        def _do():
            try:
                self._log_view.log(message, level)
            except Exception:
                pass
        try:
            self.after(0, _do)
        except Exception:
            pass


# Entry point for testing
if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
