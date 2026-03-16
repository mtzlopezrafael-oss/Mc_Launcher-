from __future__ import annotations

"""Vista principal — gestión de perfiles de instancia."""

import customtkinter as ctk
from typing import Dict, List, Optional, TYPE_CHECKING

from src.gui.components import COLORS, ProfileCard
from src.utils import profiles

try:
    from src.gui.icons import get as _ico
except ImportError:
    def _ico(name, size=(18, 18)):  # type: ignore[misc]
        return None

if TYPE_CHECKING:
    from src.gui.main_window import MainWindow


class HomeView(ctk.CTkFrame):
    """Página de inicio — muestra, crea, edita y elimina perfiles."""

    def __init__(self, parent: ctk.CTkFrame, app: MainWindow) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    # ── Build ─────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(24, 16))

        ctk.CTkLabel(
            header, text="Perfiles",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS["text"],
        ).pack(side="left")

        _ic_plus = _ico("plus", (16, 16))
        _plus_kw = {"image": _ic_plus, "compound": "left"} if _ic_plus else {}
        ctk.CTkButton(
            header,
            text="  Nuevo" if _ic_plus else "+ Nuevo",
            width=100, height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_dim"],
            text_color="#000000", corner_radius=8,
            command=self._on_new_profile,
            **_plus_kw,
        ).pack(side="right")

        # Scrollable profiles grid
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=COLORS["panel_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self._scroll.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self._container = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._container.pack(fill="both", expand=True)

    # ── Refresh ───────────────────────────────────────────────────

    def refresh(self) -> None:
        """Recarga los perfiles desde disco y repinta las tarjetas."""
        try:
            self.app._profiles = profiles.load()
        except Exception:
            self.app._profiles = []

        for w in self._container.winfo_children():
            w.destroy()

        if not self.app._profiles:
            ctk.CTkLabel(
                self._container,
                text="No hay perfiles. Crea uno nuevo.",
                font=ctk.CTkFont(size=14), text_color=COLORS["text_dim"],
            ).pack(pady=50)
            return

        row, col = 0, 0
        for profile in self.app._profiles:
            is_selected = profile.get("id") == self.app._selected_profile_id

            card = ProfileCard(
                self._container,
                profile=profile,
                on_select=self._on_select,
                on_open=self._on_open,
                on_delete=self._on_delete,
                is_selected=is_selected,
            )
            card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)

            col += 1
            if col >= 2:
                col = 0
                row += 1

        self._container.grid_columnconfigure(0, weight=1)
        self._container.grid_columnconfigure(1, weight=1)

    # ── Selección ─────────────────────────────────────────────────

    def _on_select(self, profile_id: str) -> None:
        self.app._selected_profile_id = profile_id
        self.refresh()
        self.app._update_bottom_bar_info()
        # Mostrar nombre del perfil en el log, no el UUID
        name = profile_id
        for p in self.app._profiles:
            if p.get("id") == profile_id:
                name = p.get("name", profile_id)
                break
        self.app.log(f"Perfil seleccionado: {name}")

    # ── Eliminar ──────────────────────────────────────────────────

    def _on_delete(self, profile_id: str) -> None:
        try:
            profiles.delete(profile_id)
            if self.app._selected_profile_id == profile_id:
                self.app._selected_profile_id = None
            self.refresh()
            self.app._update_bottom_bar_info()
            self.app.log(f"Perfil eliminado: {profile_id}")
        except Exception as e:
            self.app.log(f"Error al eliminar perfil: {e}", "error")

    # ── Nuevo perfil ──────────────────────────────────────────────

    def _on_new_profile(self) -> None:
        if not self.app._all_versions:
            self.app.log("Espera — cargando lista de versiones de Minecraft...", "warning")
            return
        from src.gui.dialogs import NewProfileDialog
        NewProfileDialog(self.app, self.app._all_versions, self._on_profile_created)

    def _on_profile_created(self, data: Dict) -> None:
        # FIX-065: pasar game_dir del diálogo a profiles.add()
        new_profile = profiles.add(
            name=data.get("name", "Nuevo perfil"),
            mc_version=data.get("mc_version", "1.21.1"),
            loader=data.get("loader", "vanilla"),
            loader_version=data.get("loader_version"),
            ram_mb=data.get("ram_mb", 4096),
            username=data.get("username", "Player"),
            game_dir=data.get("game_dir"),
        )
        self.app._selected_profile_id = new_profile.get("id")
        self.refresh()
        self.app._update_bottom_bar_info()
        self.app.log(f"Nuevo perfil creado: {data.get('name')}", "success")

    # ── Abrir detalle de instancia ────────────────────────────────

    def _on_open(self, profile_id: str) -> None:
        """Navega a la vista de detalle de la instancia."""
        self.app.open_instance_detail(profile_id)
