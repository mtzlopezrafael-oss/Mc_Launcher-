from __future__ import annotations

"""Vista de detalle de instancia — pestaña General (edición) y Mods."""

import threading
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

import customtkinter as ctk

from src.gui.components import COLORS, ModCard, DropdownSelector, SearchBar
from src.utils import profiles
from src.utils.config import (
    RAM_OPTIONS_MB, DEFAULT_RAM_MB, format_ram_label, MINECRAFT_DIR,
)
from src.launcher.mods import (
    search_modrinth, search_curseforge,
    get_modrinth_download, get_curseforge_download,
    download_mod, uninstall_mod,
)
from src.launcher.modpacks import (
    search_modpacks_modrinth, search_modpacks_curseforge,
    get_modpack_download_modrinth, get_modpack_download_curseforge,
    install_modpack,
)

try:
    from src.gui.icons import get as _ico
except ImportError:
    def _ico(name, size=(18, 18)):  # type: ignore[misc]
        return None

if TYPE_CHECKING:
    from src.gui.main_window import MainWindow


class InstanceDetailView(ctk.CTkFrame):
    """
    Vista de detalle por instancia.
    Muestra dos pestañas: General (editar perfil) y Mods (buscar + gestionar).
    """

    def __init__(self, parent: ctk.CTkFrame, app: "MainWindow") -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._profile: Optional[Dict] = None
        self._dir_path: List[str] = [""]
        self._build()

    # ── Build ──────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── Top bar ────────────────────────────────────────────────
        topbar = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=0)
        topbar.pack(fill="x")

        inner = ctk.CTkFrame(topbar, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)

        # Botón Volver
        ctk.CTkButton(
            inner, text="← Volver",
            width=90, height=32,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["panel_light"], hover_color=COLORS["border"],
            text_color=COLORS["text"], corner_radius=8,
            command=self._go_back,
        ).pack(side="left")

        # Nombre del perfil
        self._title_label = ctk.CTkLabel(
            inner, text="—",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text"],
        )
        self._title_label.pack(side="left", padx=(16, 0))

        # Badge de versión / loader
        self._version_badge = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["accent"],
        )
        self._version_badge.pack(side="left", padx=(10, 0))

        # Botón "Seleccionar para jugar" (derecha)
        self._select_btn = ctk.CTkButton(
            inner, text="▶  Seleccionar para jugar",
            width=200, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS["play"], hover_color=COLORS["play_hover"],
            text_color=COLORS["accent"],
            border_color=COLORS["accent"], border_width=1,
            corner_radius=8,
            command=self._select_for_play,
        )
        self._select_btn.pack(side="right")

        # ── Tabview ────────────────────────────────────────────────
        self._tabs = ctk.CTkTabview(
            self,
            fg_color=COLORS["bg"],
            segmented_button_fg_color=COLORS["panel"],
            segmented_button_selected_color=COLORS["accent_dim"],
            segmented_button_selected_hover_color=COLORS["accent_dim"],
            segmented_button_unselected_color=COLORS["panel"],
            segmented_button_unselected_hover_color=COLORS["panel_light"],
            text_color=COLORS["text_dim"],
        )
        self._tabs.pack(fill="both", expand=True)

        self._tabs.add("General")
        self._tabs.add("Mods")
        self._tabs.add("Modpacks")

        self._build_general_tab(self._tabs.tab("General"))
        self._build_mods_tab(self._tabs.tab("Mods"))
        self._build_modpacks_tab(self._tabs.tab("Modpacks"))

    # ── Pestaña General ────────────────────────────────────────────

    def _build_general_tab(self, tab: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent",
            scrollbar_button_color=COLORS["panel_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        scroll.pack(fill="both", expand=True, padx=16, pady=16)
        scroll.columnconfigure(1, weight=1)

        def _lbl(text: str, row: int) -> None:
            ctk.CTkLabel(
                scroll, text=text, text_color=COLORS["accent"],
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=row, column=0, padx=(0, 20), pady=10, sticky="w")

        # Nombre
        _lbl("NOMBRE", 0)
        self._name_entry = ctk.CTkEntry(
            scroll, fg_color=COLORS["panel_light"], text_color=COLORS["text"],
            border_color=COLORS["accent"], corner_radius=8, height=36,
        )
        self._name_entry.grid(row=0, column=1, pady=10, sticky="ew")

        # Usuario
        _lbl("USUARIO", 1)
        self._user_entry = ctk.CTkEntry(
            scroll, fg_color=COLORS["panel_light"], text_color=COLORS["text"],
            border_color=COLORS["border"], corner_radius=8, height=36,
        )
        self._user_entry.grid(row=1, column=1, pady=10, sticky="ew")

        # Versión MC (solo lectura)
        _lbl("VERSIÓN MC", 2)
        self._mc_ver_label = ctk.CTkLabel(
            scroll, text="—",
            text_color=COLORS["text_dim"], font=ctk.CTkFont(size=13), anchor="w",
        )
        self._mc_ver_label.grid(row=2, column=1, pady=10, sticky="w")

        # Loader (solo lectura)
        _lbl("LOADER", 3)
        self._loader_label = ctk.CTkLabel(
            scroll, text="—",
            text_color=COLORS["text_dim"], font=ctk.CTkFont(size=13), anchor="w",
        )
        self._loader_label.grid(row=3, column=1, pady=10, sticky="w")

        # RAM
        _lbl("RAM", 4)
        self._ram_option = ctk.CTkOptionMenu(
            scroll, values=[format_ram_label(m) for m in RAM_OPTIONS_MB],
            fg_color=COLORS["panel_light"], button_color=COLORS["accent_dim"],
            text_color=COLORS["text"], corner_radius=8, height=36,
        )
        self._ram_option.grid(row=4, column=1, pady=10, sticky="ew")

        # Directorio de juego
        _lbl("DIRECTORIO", 5)
        dir_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        dir_frame.grid(row=5, column=1, pady=10, sticky="ew")
        dir_frame.columnconfigure(1, weight=1)

        def _pick_dir() -> None:
            from tkinter import filedialog
            chosen = filedialog.askdirectory(initialdir=self._dir_path[0] or str(Path.home()))
            if chosen:
                self._dir_path[0] = chosen
                self._dir_label.configure(
                    text=chosen[-36:], text_color=COLORS["text"],
                )

        _ic_folder = _ico("folder", (16, 16))
        _folder_kw = {"image": _ic_folder, "compound": "center"} if _ic_folder else {}
        ctk.CTkButton(
            dir_frame,
            text="" if _ic_folder else "📁",
            width=36, height=36,
            fg_color=COLORS["panel_light"], hover_color=COLORS["accent_dim"],
            corner_radius=8, command=_pick_dir,
            **_folder_kw,
        ).grid(row=0, column=0, padx=(0, 10))

        self._dir_label = ctk.CTkLabel(
            dir_frame, text="default (carpeta de Minecraft)",
            text_color=COLORS["text_dim"], font=ctk.CTkFont(size=11), anchor="w",
        )
        self._dir_label.grid(row=0, column=1, sticky="ew")

        # Botón Guardar
        sep = ctk.CTkFrame(scroll, height=1, fg_color=COLORS["border"])
        sep.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(20, 0))

        _ic_check = _ico("check", (16, 16))
        _check_kw = {"image": _ic_check, "compound": "left"} if _ic_check else {}
        ctk.CTkButton(
            scroll,
            text="  Guardar cambios" if _ic_check else "💾  Guardar cambios",
            height=40, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["play"], hover_color=COLORS["play_hover"],
            text_color=COLORS["accent"],
            border_color=COLORS["accent"], border_width=1,
            corner_radius=8, command=self._save_general,
            **_check_kw,
        ).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(12, 8))

    # ── Pestaña Mods ───────────────────────────────────────────────

    def _build_mods_tab(self, tab: ctk.CTkFrame) -> None:
        tab.columnconfigure(0, weight=0)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)

        # ── Panel izquierdo: mods instalados ──────────────────────
        left = ctk.CTkFrame(tab, fg_color=COLORS["panel"], corner_radius=12, width=280)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 6), pady=8)
        left.grid_propagate(False)

        # Cabecera panel izquierdo
        inst_header = ctk.CTkFrame(left, fg_color="transparent")
        inst_header.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(
            inst_header, text="Instalados",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["text"],
        ).pack(side="left")

        self._installed_count = ctk.CTkLabel(
            inst_header, text="(0)",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
        )
        self._installed_count.pack(side="left", padx=(6, 0))

        # Botón refresh instalados
        _ic_rcw = _ico("refresh-cw", (13, 13))
        _rcw_kw = {"image": _ic_rcw, "compound": "center"} if _ic_rcw else {}
        ctk.CTkButton(
            inst_header,
            text="" if _ic_rcw else "↺",
            width=28, height=28,
            fg_color=COLORS["panel_light"], hover_color=COLORS["border"],
            text_color=COLORS["text_dim"], corner_radius=6,
            command=self._refresh_installed_mods,
            **_rcw_kw,
        ).pack(side="right")

        # Ruta de la carpeta mods + botón abrir
        path_row = ctk.CTkFrame(left, fg_color="transparent")
        path_row.pack(fill="x", padx=10, pady=(0, 6))

        self._mods_path_label = ctk.CTkLabel(
            path_row, text="—",
            font=ctk.CTkFont(size=9), text_color=COLORS["text_dim"],
            anchor="w", wraplength=190,
        )
        self._mods_path_label.pack(side="left", fill="x", expand=True)

        _ic_ext = _ico("folder", (12, 12))
        _ext_kw = {"image": _ic_ext, "compound": "center"} if _ic_ext else {}
        ctk.CTkButton(
            path_row,
            text="" if _ic_ext else "📂",
            width=24, height=22,
            fg_color=COLORS["panel_light"], hover_color=COLORS["accent_dim"],
            text_color=COLORS["text_dim"], corner_radius=4,
            command=self._open_mods_folder,
            **_ext_kw,
        ).pack(side="right", padx=(4, 0))

        # Lista de mods instalados
        self._installed_scroll = ctk.CTkScrollableFrame(
            left, fg_color="transparent",
            scrollbar_button_color=COLORS["panel_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self._installed_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        # ── Panel derecho: búsqueda ────────────────────────────────
        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # Controles de búsqueda
        controls = ctk.CTkFrame(right, fg_color=COLORS["panel"], corner_radius=12)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctrl_row = ctk.CTkFrame(controls, fg_color="transparent")
        ctrl_row.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(
            ctrl_row, text="Fuente:",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
        ).pack(side="left")
        self._mod_source = DropdownSelector(
            ctrl_row, values=["Modrinth", "CurseForge", "Ambos"],
            default="Modrinth", width=120,
        )
        self._mod_source.pack(side="left", padx=(6, 12))

        ctk.CTkLabel(
            ctrl_row, text="Loader:",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
        ).pack(side="left")
        self._mod_loader_filter = DropdownSelector(
            ctrl_row, values=["Auto", "Fabric", "Forge", "NeoForge", "Quilt"],
            default="Auto", width=100,
        )
        self._mod_loader_filter.pack(side="left", padx=(6, 12))

        self._search_bar = SearchBar(
            ctrl_row, placeholder="Buscar mods...",
            on_search=self._on_mod_search, width=220,
        )
        self._search_bar.pack(side="left", fill="x", expand=True)

        # Resultados de búsqueda
        self._results_scroll = ctk.CTkScrollableFrame(
            right, fg_color="transparent",
            scrollbar_button_color=COLORS["panel_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self._results_scroll.grid(row=1, column=0, sticky="nsew")

        self._results_container = ctk.CTkFrame(
            self._results_scroll, fg_color="transparent",
        )
        self._results_container.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self._results_container,
            text="🔍  Busca mods para instalarlos en esta instancia",
            font=ctk.CTkFont(size=13), text_color=COLORS["text_dim"],
        ).pack(pady=60)

    # ── Carga de perfil ────────────────────────────────────────────

    def load_profile(self, profile: Dict) -> None:
        """Llamado por MainWindow al abrir una instancia."""
        self._profile = profile

        name    = profile.get("name", "Sin nombre")
        mc_ver  = profile.get("mc_version", "?")
        loader  = profile.get("loader", "vanilla").capitalize()

        # Header
        self._title_label.configure(text=name)
        self._version_badge.configure(text=f"MC {mc_ver}  •  {loader}")

        # Estado del botón seleccionar
        is_selected = profile.get("id") == self.app._selected_profile_id
        self._update_select_btn(is_selected)

        # Formulario General
        self._name_entry.delete(0, "end")
        self._name_entry.insert(0, name)

        self._user_entry.delete(0, "end")
        self._user_entry.insert(0, profile.get("username", "Player"))

        self._mc_ver_label.configure(text=mc_ver)
        self._loader_label.configure(text=f"{loader}  {profile.get('loader_version', '')}")

        self._ram_option.set(format_ram_label(profile.get("ram_mb", 4096)))

        gdir = profile.get("game_dir", "") or ""
        self._dir_path[0] = gdir
        self._dir_label.configure(
            text=(gdir[-36:] if gdir else "default (carpeta de Minecraft)"),
            text_color=COLORS["text"] if gdir else COLORS["text_dim"],
        )

        # Mostrar path de mods
        mods_dir = self._get_mods_dir()
        self._mods_path_label.configure(text=str(mods_dir))

        # Recargar mods instalados
        self._refresh_installed_mods()

        # Limpiar resultados anteriores
        for w in self._results_container.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._results_container,
            text="🔍  Busca mods para instalarlos en esta instancia",
            font=ctk.CTkFont(size=13), text_color=COLORS["text_dim"],
        ).pack(pady=60)

    def _update_select_btn(self, is_selected: bool) -> None:
        if is_selected:
            self._select_btn.configure(
                text="✓  Perfil activo",
                fg_color=COLORS["success"],
                hover_color="#00cc6a",
                text_color="#000000",
                border_color=COLORS["success"],
            )
        else:
            self._select_btn.configure(
                text="▶  Seleccionar para jugar",
                fg_color=COLORS["play"],
                hover_color=COLORS["play_hover"],
                text_color=COLORS["accent"],
                border_color=COLORS["accent"],
            )

    # ── Acciones del header ────────────────────────────────────────

    def _go_back(self) -> None:
        """Vuelve a la vista de inicio y activa el nav button correspondiente."""
        self.app._show_page("home")
        for nav_id, btn in self.app._nav_buttons.items():
            btn.set_active(nav_id == "home")
        self.app._current_section = "home"

    def _select_for_play(self) -> None:
        if not self._profile:
            return
        self.app._selected_profile_id = self._profile["id"]
        self._update_select_btn(True)
        self.app._update_bottom_bar_info()
        self.app.log(f"Perfil seleccionado: {self._profile.get('name')}")
        try:
            self.app._home_view.refresh()
        except Exception:
            pass

    # ── General: guardar ──────────────────────────────────────────

    def _save_general(self) -> None:
        if not self._profile:
            return

        n  = self._name_entry.get().strip() or self._profile.get("name", "Perfil")
        u  = self._user_entry.get().strip() or "Player"
        rl = self._ram_option.get()
        try:
            parts = rl.split()
            rm = int(parts[0]) * 1024 if "GB" in rl else int(parts[0])
        except (IndexError, ValueError):
            rm = DEFAULT_RAM_MB
        gd = self._dir_path[0] or self._profile.get("game_dir", "")

        profiles.update(self._profile["id"], name=n, username=u, ram_mb=rm, game_dir=gd)

        # Actualizar copia local del perfil
        self._profile.update({"name": n, "username": u, "ram_mb": rm, "game_dir": gd})

        # Actualizar header
        self._title_label.configure(text=n)

        if self.app._selected_profile_id == self._profile["id"]:
            self.app._update_bottom_bar_info()

        try:
            self.app._home_view.refresh()
        except Exception:
            pass

        self.app.log(f"Perfil guardado: {n}", "success")

    # ── Mods instalados ────────────────────────────────────────────

    def _get_mods_dir(self) -> Path:
        if not self._profile:
            return Path(str(MINECRAFT_DIR)) / "mods"
        gdir = self._profile.get("game_dir", "") or str(MINECRAFT_DIR)
        return Path(gdir) / "mods"

    def _refresh_installed_mods(self) -> None:
        for w in self._installed_scroll.winfo_children():
            w.destroy()

        mods_dir = self._get_mods_dir()

        # Listar .jar y .jar.disabled
        mods: List[Path] = []
        if mods_dir.exists():
            try:
                mods = sorted(
                    [f for f in mods_dir.iterdir()
                     if f.suffix == ".jar" or f.name.endswith(".jar.disabled")],
                    key=lambda f: f.name.lower(),
                )
            except Exception:
                mods = []

        self._installed_count.configure(text=f"({len(mods)})")

        if not mods:
            ctk.CTkLabel(
                self._installed_scroll,
                text="Sin mods instalados",
                font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
            ).pack(pady=24)
            return

        for mod_path in mods:
            self._build_mod_row(mod_path)

    def _build_mod_row(self, path: Path) -> None:
        is_disabled = path.name.endswith(".disabled")
        display = path.name
        for ext in (".jar.disabled", ".jar"):
            display = display.replace(ext, "")

        row = ctk.CTkFrame(
            self._installed_scroll,
            fg_color=COLORS["bg"] if is_disabled else COLORS["panel_light"],
            corner_radius=6,
        )
        row.pack(fill="x", pady=2)
        row.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            row, text=display,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"] if is_disabled else COLORS["text"],
            anchor="w",
        ).grid(row=0, column=0, padx=(10, 4), pady=5, sticky="w")

        # Botón toggle — muestra el ESTADO ACTUAL (On = activo, Off = desactivado)
        if is_disabled:
            toggle_text  = "Off"
            toggle_fg    = COLORS["panel"]
            toggle_tc    = COLORS["text_dim"]
        else:
            toggle_text  = "On"
            toggle_fg    = COLORS["success"]
            toggle_tc    = "#ffffff"
        ctk.CTkButton(
            row, text=toggle_text, width=36, height=22,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=toggle_fg, hover_color=COLORS["border"],
            text_color=toggle_tc, corner_radius=4,
            command=lambda p=path: self._toggle_mod(p),
        ).grid(row=0, column=1, padx=2, pady=4)

        # Botón eliminar
        _ic_trash = _ico("trash", (12, 12))
        _trash_kw = {"image": _ic_trash, "compound": "center"} if _ic_trash else {}
        ctk.CTkButton(
            row,
            text="" if _ic_trash else "✕",
            width=26, height=22,
            font=ctk.CTkFont(size=10),
            fg_color=COLORS["panel"], hover_color=COLORS["error"],
            text_color=COLORS["text_dim"], corner_radius=4,
            command=lambda p=path: self._remove_mod(p),
            **_trash_kw,
        ).grid(row=0, column=2, padx=(2, 8), pady=4)

    def _open_mods_folder(self) -> None:
        """Abre la carpeta de mods en el explorador del sistema."""
        import sys, subprocess
        mods_dir = self._get_mods_dir()
        mods_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(mods_dir)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(mods_dir)])
            else:
                subprocess.Popen(["xdg-open", str(mods_dir)])
        except Exception as e:
            self.app.log(f"No se pudo abrir la carpeta: {e}", "error")

    def _toggle_mod(self, path: Path) -> None:
        try:
            if path.name.endswith(".disabled"):
                # Activar: quitar .disabled
                new_path = path.with_name(path.name[: -len(".disabled")])
            else:
                new_path = path.with_name(path.name + ".disabled")
            path.rename(new_path)
            self._refresh_installed_mods()
            action = "desactivado" if str(new_path).endswith(".disabled") else "activado"
            self.app.log(f"Mod {action}: {path.stem}")
        except Exception as e:
            self.app.log(f"Error al cambiar estado del mod: {e}", "error")

    def _remove_mod(self, path: Path) -> None:
        try:
            uninstall_mod(path.parent, path.name)
            self._refresh_installed_mods()
            self.app.log(f"Mod eliminado: {path.stem}")
        except Exception as e:
            self.app.log(f"Error al eliminar mod: {e}", "error")

    # ── Búsqueda de mods ───────────────────────────────────────────

    def _on_mod_search(self, query: str) -> None:
        if not query.strip():
            return

        for w in self._results_container.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._results_container, text="🔄  Buscando...",
            font=ctk.CTkFont(size=13), text_color=COLORS["text_dim"],
        ).pack(pady=40)

        def search() -> None:
            results: List[Dict] = []
            source = self._mod_source.get()
            loader_val = self._mod_loader_filter.get()

            if loader_val == "Auto":
                loader = (self._profile.get("loader") if self._profile else None)
                loader = loader.lower() if loader and loader != "vanilla" else None
            else:
                loader = loader_val.lower()

            mc_ver = self._profile.get("mc_version", "1.21") if self._profile else "1.21"

            try:
                if source in ("Modrinth", "Ambos"):
                    results.extend(search_modrinth(query, mc_ver, loader))
                if source in ("CurseForge", "Ambos"):
                    results.extend(search_curseforge(query, mc_ver, loader))
            except Exception as e:
                self.app.log(f"Error en búsqueda: {e}", "error")

            try:
                self.after(0, lambda: self._display_results(results))
            except Exception:
                pass

        threading.Thread(target=search, daemon=True).start()

    def _display_results(self, results: List[Dict]) -> None:
        for w in self._results_container.winfo_children():
            w.destroy()

        if not results:
            ctk.CTkLabel(
                self._results_container, text="😔  No se encontraron mods",
                font=ctk.CTkFont(size=13), text_color=COLORS["text_dim"],
            ).pack(pady=40)
            return

        for mod in results[:20]:
            ModCard(
                self._results_container, mod_data=mod,
                on_install=self._on_mod_install,
            ).pack(fill="x", pady=3)

        self.app.log(f"Se encontraron {len(results)} mods", "success")

    def _on_mod_install(self, mod: Dict, card=None) -> None:
        if not self._profile:
            self.app.log("No hay perfil cargado en esta instancia", "error")
            return

        # Advertir si el perfil es vanilla (sin mod loader)
        loader = self._profile.get("loader", "vanilla")
        if loader == "vanilla":
            self.app.log(
                "⚠ Este perfil usa Vanilla — los mods necesitan un loader "
                "(Fabric, Forge, etc.) para funcionar. Instala un loader primero.",
                "warning",
            )
            # Restaurar el botón del card
            if card is not None:
                try:
                    self.after(0, lambda: card._install_btn.configure(
                        text="Instalar", state="normal",
                    ))
                    card._installing = False
                except Exception:
                    pass
            return

        name = mod.get("title") or mod.get("name", "Unknown")
        self.app.log(f"Instalando: {name}")

        def install() -> None:
            success = False
            try:
                mc_ver   = self._profile.get("mc_version", "1.21")
                mods_dir = self._get_mods_dir()

                source = mod.get("source", "modrinth")
                if source == "curseforge":
                    download_info = get_curseforge_download(mod.get("id"), mc_ver, loader)
                else:
                    download_info = get_modrinth_download(mod.get("id"), mc_ver, loader)

                if download_info:
                    url, filename = download_info

                    # Si existe una versión desactivada del mismo mod, eliminarla
                    # para que el mod quede siempre en estado On al instalar
                    disabled_path = mods_dir / (filename + ".disabled")
                    if disabled_path.exists():
                        try:
                            disabled_path.unlink()
                            self.app.log(f"Reemplazando versión desactivada de {name}")
                        except Exception:
                            pass

                    if download_mod(url, mods_dir, filename):
                        # Asegurarse de que el archivo descargado esté activo (.jar, no .disabled)
                        jar_path = mods_dir / filename
                        disabled_jar = mods_dir / (filename + ".disabled")
                        if disabled_jar.exists() and not jar_path.exists():
                            try:
                                disabled_jar.rename(jar_path)
                            except Exception:
                                pass
                        self.app.log(f"✓ Instalado: {name}", "success")
                        success = True
                    else:
                        self.app.log("Error al descargar el mod", "error")
                else:
                    self.app.log("No hay versión compatible para este perfil", "warning")
            except Exception as e:
                self.app.log(f"Error al instalar mod: {e}", "error")

            def _ui_update() -> None:
                try:
                    if success and card is not None:
                        card.set_installed()
                    elif not success and card is not None:
                        card._installing = False
                        card._install_btn.configure(text="Instalar", state="normal")
                    self._refresh_installed_mods()
                except Exception:
                    pass

            try:
                self.after(0, _ui_update)
            except Exception:
                pass

        threading.Thread(target=install, daemon=True).start()

    # ══════════════════════════════════════════════════════════════
    #  PESTAÑA MODPACKS
    # ══════════════════════════════════════════════════════════════

    def _build_modpacks_tab(self, tab: ctk.CTkFrame) -> None:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        # ── Controles de búsqueda ──
        controls = ctk.CTkFrame(tab, fg_color=COLORS["panel"], corner_radius=12)
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        ctrl_row = ctk.CTkFrame(controls, fg_color="transparent")
        ctrl_row.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(
            ctrl_row, text="Fuente:",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
        ).pack(side="left")
        self._mp_source = DropdownSelector(
            ctrl_row, values=["Modrinth", "CurseForge", "Ambos"],
            default="Modrinth", width=120,
        )
        self._mp_source.pack(side="left", padx=(6, 12))

        ctk.CTkLabel(
            ctrl_row, text="Loader:",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
        ).pack(side="left")
        self._mp_loader_filter = DropdownSelector(
            ctrl_row, values=["Auto", "Fabric", "Forge", "NeoForge", "Quilt"],
            default="Auto", width=100,
        )
        self._mp_loader_filter.pack(side="left", padx=(6, 12))

        self._mp_search_bar = SearchBar(
            ctrl_row, placeholder="Buscar modpacks...",
            on_search=self._on_modpack_search, width=220,
        )
        self._mp_search_bar.pack(side="left", fill="x", expand=True)

        # ── Área de resultados ──
        self._mp_results_scroll = ctk.CTkScrollableFrame(
            tab, fg_color="transparent",
            scrollbar_button_color=COLORS["panel_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self._mp_results_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))

        self._mp_results_container = ctk.CTkFrame(
            self._mp_results_scroll, fg_color="transparent",
        )
        self._mp_results_container.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self._mp_results_container,
            text="🔍  Busca modpacks para instalarlos en esta instancia",
            font=ctk.CTkFont(size=13), text_color=COLORS["text_dim"],
        ).pack(pady=60)

        # ── Barra de progreso de instalación (oculta por defecto) ──
        self._mp_progress_frame = ctk.CTkFrame(tab, fg_color=COLORS["panel"], corner_radius=12)

        self._mp_progress_label = ctk.CTkLabel(
            self._mp_progress_frame, text="",
            font=ctk.CTkFont(size=12), text_color=COLORS["text"],
        )
        self._mp_progress_label.pack(padx=12, pady=(8, 2))

        self._mp_progress_bar = ctk.CTkProgressBar(
            self._mp_progress_frame,
            fg_color=COLORS["panel_light"],
            progress_color=COLORS["accent"],
            height=8,
        )
        self._mp_progress_bar.pack(fill="x", padx=12, pady=(2, 8))
        self._mp_progress_bar.set(0)

    # ── Búsqueda de modpacks ──

    def _on_modpack_search(self, query: str) -> None:
        if not query.strip():
            return

        for w in self._mp_results_container.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._mp_results_container, text="🔄  Buscando modpacks...",
            font=ctk.CTkFont(size=13), text_color=COLORS["text_dim"],
        ).pack(pady=40)

        def search() -> None:
            results: List[Dict] = []
            source = self._mp_source.get()
            loader_val = self._mp_loader_filter.get()

            if loader_val == "Auto":
                loader = (self._profile.get("loader") if self._profile else None)
                loader = loader.lower() if loader and loader != "vanilla" else None
            else:
                loader = loader_val.lower()

            mc_ver = self._profile.get("mc_version", "1.21") if self._profile else "1.21"

            try:
                if source in ("Modrinth", "Ambos"):
                    results.extend(search_modpacks_modrinth(query, mc_ver, loader))
                if source in ("CurseForge", "Ambos"):
                    results.extend(search_modpacks_curseforge(query, mc_ver, loader))
            except Exception as e:
                self.app.log(f"Error buscando modpacks: {e}", "error")

            try:
                self.after(0, lambda: self._display_modpack_results(results))
            except Exception:
                pass

        threading.Thread(target=search, daemon=True).start()

    def _display_modpack_results(self, results: List[Dict]) -> None:
        for w in self._mp_results_container.winfo_children():
            w.destroy()

        if not results:
            ctk.CTkLabel(
                self._mp_results_container, text="😔  No se encontraron modpacks",
                font=ctk.CTkFont(size=13), text_color=COLORS["text_dim"],
            ).pack(pady=40)
            return

        for pack in results[:20]:
            self._build_modpack_card(pack)

        self.app.log(f"Se encontraron {len(results)} modpacks", "success")

    def _build_modpack_card(self, pack: Dict) -> None:
        """Construye una tarjeta visual para un modpack."""
        card = ctk.CTkFrame(
            self._mp_results_container,
            fg_color=COLORS["panel"],
            corner_radius=10,
        )
        card.pack(fill="x", pady=4)
        card.columnconfigure(1, weight=1)

        # Icono placeholder
        icon_label = ctk.CTkLabel(
            card, text="📦", font=ctk.CTkFont(size=24),
            width=50, height=50,
        )
        icon_label.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=8)

        # Cargar icono real en background
        icon_url = pack.get("icon_url", "")
        if icon_url:
            threading.Thread(
                target=self._load_modpack_icon,
                args=(icon_url, icon_label),
                daemon=True,
            ).start()

        # Título
        ctk.CTkLabel(
            card, text=pack.get("title", ""),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"], anchor="w",
        ).grid(row=0, column=1, sticky="w", pady=(8, 0))

        # Descripción
        desc = pack.get("description", "")[:100]
        if len(pack.get("description", "")) > 100:
            desc += "..."
        ctk.CTkLabel(
            card, text=desc,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"], anchor="w",
            wraplength=350,
        ).grid(row=1, column=1, sticky="w", pady=(0, 2))

        # Info: autor + descargas
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 4))

        dl_count = pack.get("downloads", 0)
        dl_text = f"{dl_count/1_000_000:.1f}M" if dl_count >= 1_000_000 else (
            f"{dl_count/1_000:.0f}K" if dl_count >= 1_000 else str(dl_count))

        source_label = "MR" if pack.get("source") == "modrinth" else "CF"
        ctk.CTkLabel(
            info_frame,
            text=f"{source_label}  •  {pack.get('author', '?')}  •  {dl_text} descargas",
            font=ctk.CTkFont(size=10), text_color=COLORS["text_dim"],
        ).pack(side="left")

        # Botón Instalar
        install_btn = ctk.CTkButton(
            card, text="Instalar",
            width=100, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_dim"],
            text_color="#000000",
            corner_radius=8,
            command=lambda p=pack, b=None: self._on_modpack_install(p, install_btn),
        )
        install_btn.grid(row=0, column=2, rowspan=2, padx=(8, 12), pady=8)

    def _load_modpack_icon(self, url: str, label: ctk.CTkLabel) -> None:
        """Descarga y muestra el icono de un modpack."""
        try:
            from PIL import Image
            import io
            req = urllib.request.Request(url, headers={"User-Agent": "CTK-Launcher/3.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            img = img.resize((50, 50), Image.LANCZOS)
            bg = Image.new("RGB", img.size, (19, 19, 42))
            bg.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
            ctk_img = ctk.CTkImage(bg, size=(50, 50))
            # Mantener referencia para evitar garbage collection
            if not hasattr(self, '_mp_icon_refs'):
                self._mp_icon_refs = []
            self._mp_icon_refs.append(ctk_img)
            try:
                self.after(0, lambda: label.configure(image=ctk_img, text=""))
            except Exception:
                pass
        except Exception:
            pass

    # ── Instalación de modpack ──

    def _on_modpack_install(self, pack: Dict, btn: ctk.CTkButton) -> None:
        if not self._profile:
            self.app.log("No hay perfil cargado", "error")
            return

        name = pack.get("title", "Modpack")
        source = pack.get("source", "modrinth")
        btn.configure(text="Instalando...", state="disabled")

        # Mostrar barra de progreso
        self._mp_progress_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        self._mp_progress_label.configure(text=f"Preparando {name}...")
        self._mp_progress_bar.set(0)

        self.app.log(f"Instalando modpack: {name}...")

        def install() -> None:
            mc_ver = self._profile.get("mc_version", "1.21") if self._profile else "1.21"
            loader_val = self._mp_loader_filter.get()
            if loader_val == "Auto":
                loader = (self._profile.get("loader") if self._profile else None)
                loader = loader.lower() if loader and loader != "vanilla" else None
            else:
                loader = loader_val.lower()

            # Obtener URL de descarga
            try:
                if source == "curseforge":
                    dl_info = get_modpack_download_curseforge(pack.get("id"), mc_ver, loader)
                else:
                    dl_info = get_modpack_download_modrinth(pack.get("id"), mc_ver, loader)
            except Exception as e:
                self.app.log(f"Error obteniendo descarga: {e}", "error")
                try:
                    self.after(0, lambda: self._mp_install_done(btn, False, name))
                except Exception:
                    pass
                return

            if not dl_info:
                self.app.log(f"No hay versión compatible de {name} para este perfil", "warning")
                try:
                    self.after(0, lambda: self._mp_install_done(btn, False, name))
                except Exception:
                    pass
                return

            dl_url, filename, version_name = dl_info
            self.app.log(f"Versión: {version_name}")

            # Directorio de la instancia
            instance_dir = Path(
                self._profile.get("game_dir", "") or str(MINECRAFT_DIR)
            )

            def progress(stage: str, current: int, total: int):
                if total <= 0:
                    return
                pct = current / total
                if stage == "download":
                    msg = f"Descargando... {int(pct * 100)}%"
                else:
                    msg = f"Instalando mods... {current}/{total}"
                try:
                    self.after(0, lambda m=msg, p=pct: self._mp_update_progress(m, p))
                except Exception:
                    pass

            def log_msg(msg: str):
                self.app.log(f"[Modpack] {msg}")

            ok = install_modpack(
                download_url=dl_url,
                filename=filename,
                instance_dir=instance_dir,
                source=source,
                progress_cb=progress,
                log_cb=log_msg,
            )

            try:
                self.after(0, lambda: self._mp_install_done(btn, ok, name))
            except Exception:
                pass

        threading.Thread(target=install, daemon=True).start()

    def _mp_update_progress(self, msg: str, pct: float) -> None:
        if not self.winfo_exists():
            return
        self._mp_progress_label.configure(text=msg)
        self._mp_progress_bar.set(pct)

    def _mp_install_done(self, btn: ctk.CTkButton, success: bool, name: str) -> None:
        if not self.winfo_exists():
            return
        self._mp_progress_frame.grid_forget()
        if success:
            btn.configure(text="✓ Instalado", fg_color=COLORS["success"], state="disabled")
            self.app.log(f"✓ Modpack instalado: {name}", "success")
            self._refresh_installed_mods()
        else:
            btn.configure(text="Instalar", state="normal")
            self.app.log(f"Error instalando modpack: {name}", "error")
