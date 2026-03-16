from __future__ import annotations

"""Vista de búsqueda e instalación de mods."""

import threading
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

import customtkinter as ctk

from src.gui.components import COLORS, ModCard, DropdownSelector, SearchBar

try:
    from src.gui.icons import get as _ico
except ImportError:
    def _ico(name, size=(18, 18)):  # type: ignore[misc]
        return None

from src.launcher.mods import (
    search_modrinth, search_curseforge,
    get_modrinth_download, get_curseforge_download,
    download_mod, get_installed_mods,
)
from src.utils.config import MINECRAFT_DIR

if TYPE_CHECKING:
    from src.gui.main_window import MainWindow


class ModsView(ctk.CTkFrame):
    """Página de mods — búsqueda, instalación y gestión."""

    def __init__(self, parent: ctk.CTkFrame, app: MainWindow) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    # ── Build ─────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── Header con controles de búsqueda ──
        header = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=0)
        header.pack(fill="x")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(fill="x", padx=16, pady=12)

        # Fuente
        ctk.CTkLabel(
            controls, text="Fuente:",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
        ).pack(side="left")

        self._source = DropdownSelector(
            controls, values=["Modrinth", "CurseForge", "Ambos"],
            default="Modrinth", width=120,
        )
        self._source.pack(side="left", padx=(8, 16))

        # Loader
        ctk.CTkLabel(
            controls, text="Loader:",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
        ).pack(side="left")

        self._loader_filter = DropdownSelector(
            controls, values=["Todos", "Fabric", "Forge", "NeoForge", "Quilt"],
            default="Todos", width=100,
        )
        self._loader_filter.pack(side="left", padx=(8, 16))

        # Barra de búsqueda
        self._search_bar = SearchBar(
            controls, placeholder="Buscar mods...",
            on_search=self._on_search, width=300,
        )
        self._search_bar.pack(side="left", fill="x", expand=True, padx=(0, 16))

        # ── Área de resultados ──
        results_frame = ctk.CTkFrame(self, fg_color="transparent")
        results_frame.pack(fill="both", expand=True)

        self._scroll = ctk.CTkScrollableFrame(
            results_frame, fg_color="transparent",
            scrollbar_button_color=COLORS["panel_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self._scroll.pack(fill="both", expand=True, padx=16, pady=16)

        self._container = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._container.pack(fill="both", expand=True)

        # Estado vacío
        ctk.CTkLabel(
            self._container,
            text="🔍 Busca mods para comenzar",
            font=ctk.CTkFont(size=16), text_color=COLORS["text_dim"],
        ).pack(pady=100)

        # ── Barra de mods instalados ──
        installed_bar = ctk.CTkFrame(self, fg_color=COLORS["panel"], height=50)
        installed_bar.pack(fill="x", side="bottom")
        installed_bar.pack_propagate(False)

        self._installed_label = ctk.CTkLabel(
            installed_bar, text="Mods instalados: 0",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_dim"],
        )
        self._installed_label.pack(side="left", padx=16, pady=12)

        _ic_rcw = _ico("refresh-cw", (14, 14))
        _rcw_kw = {"image": _ic_rcw, "compound": "left"} if _ic_rcw else {}
        ctk.CTkButton(
            installed_bar,
            text="  Actualizar" if _ic_rcw else "↺ Actualizar",
            width=110, height=32, font=ctk.CTkFont(size=12),
            fg_color=COLORS["panel_light"], hover_color=COLORS["border"],
            text_color=COLORS["text"], command=self.refresh_installed,
            **_rcw_kw,
        ).pack(side="right", padx=16, pady=9)

    # ── Búsqueda ──────────────────────────────────────────────────

    def _on_search(self, query: str) -> None:
        if not query.strip():
            return

        self.app.log(f"Buscando mods: {query}")

        # Limpiar y mostrar cargando
        for w in self._container.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._container, text="🔄 Buscando...",
            font=ctk.CTkFont(size=14), text_color=COLORS["text_dim"],
        ).pack(pady=50)

        def search():
            results: List[Dict] = []
            source = self._source.get()
            loader = self._loader_filter.get()
            if loader == "Todos":
                loader = None
            else:
                # FIX-068: las APIs esperan minúsculas
                loader = loader.lower()

            profile = self.app.get_selected_profile()
            mc_ver = profile.get("mc_version", "1.21") if profile else "1.21"

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
        for w in self._container.winfo_children():
            w.destroy()

        if not results:
            ctk.CTkLabel(
                self._container, text="😔 No se encontraron mods",
                font=ctk.CTkFont(size=14), text_color=COLORS["text_dim"],
            ).pack(pady=50)
            return

        for mod in results[:20]:
            ModCard(
                self._container, mod_data=mod,
                on_install=self._on_install,
            ).pack(fill="x", pady=4)

        self.app.log(f"Se encontraron {len(results)} mods", "success")

    # ── Instalación ───────────────────────────────────────────────

    def _on_install(self, mod: Dict, card=None) -> None:
        profile = self.app.get_selected_profile()
        if not profile:
            self.app.log("Selecciona un perfil primero", "warning")
            return

        self.app.log(f"Instalando mod: {mod.get('title') or mod.get('name', 'Unknown')}")

        def install():
            try:
                mc_ver = profile.get("mc_version", "1.21")
                loader = profile.get("loader", "fabric")
                game_dir = profile.get("game_dir", "") or str(MINECRAFT_DIR)
                mods_dir = Path(game_dir) / "mods"

                # FIX-067: API correcta según la fuente del mod
                source = mod.get("source", "modrinth")
                if source == "curseforge":
                    download_info = get_curseforge_download(mod.get("id"), mc_ver, loader)
                else:
                    download_info = get_modrinth_download(mod.get("id"), mc_ver, loader)

                if download_info:
                    url, filename = download_info
                    if download_mod(url, mods_dir, filename):
                        self.app.log(
                            f"Mod instalado: {mod.get('title') or mod.get('name', '?')}",
                            "success",
                        )
                    else:
                        self.app.log("Error instalando mod", "error")
                else:
                    self.app.log("No se encontró descarga compatible", "warning")
            except Exception as e:
                self.app.log(f"Error: {e}", "error")

            try:
                self.after(0, self.refresh_installed)
            except Exception:
                pass

        threading.Thread(target=install, daemon=True).start()

    # ── Mods instalados ───────────────────────────────────────────

    def refresh_installed(self) -> None:
        """Actualiza el contador de mods instalados."""
        try:
            profile = self.app.get_selected_profile()
            if profile:
                mods_dir = Path(profile.get("game_dir", "") or str(MINECRAFT_DIR)) / "mods"
                mods = get_installed_mods(mods_dir)
                self._installed_label.configure(text=f"Mods instalados: {len(mods)}")
            else:
                self._installed_label.configure(text="Mods instalados: 0")
        except Exception:
            self._installed_label.configure(text="Mods instalados: ?")
