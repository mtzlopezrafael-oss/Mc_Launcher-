from __future__ import annotations

"""Diálogos modales — NewProfileDialog."""

import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from src.utils.config import (
    COLORS, LOADER_IDS, LOADER_ICONS, LOADER_COLORS,
    RAM_OPTIONS_MB, DEFAULT_RAM_MB, format_ram_label,
)
from src.launcher import loaders


def _c(k: str) -> str:
    return COLORS.get(k, k)


class _BaseDialog(ctk.CTkToplevel):
    """Base para diálogos modales."""
    def __init__(self, master, title: str, width: int = 460, height: int = 500) -> None:
        super().__init__(master)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.configure(fg_color=_c("bg"))
        self.grab_set()
        self.focus_set()
        # Centrar sobre el padre
        self.after(10, self._center)

    def _center(self) -> None:
        master = self.master
        x = master.winfo_x() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_y() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


class NewProfileDialog(_BaseDialog):
    """
    Diálogo para crear un nuevo perfil de instancia.
    Llama on_create(profile_data: dict) al confirmar.
    """

    def __init__(self, master, versions: List[str], on_create: Callable[[Dict], None]) -> None:
        super().__init__(master, "Nuevo Perfil", width=480, height=540)
        self._versions = versions
        self._on_create = on_create
        self._loader_versions: List[str] = []
        self._pending_loader: str = "vanilla"
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        # Título
        ctk.CTkLabel(self, text="Nuevo Perfil",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=_c("accent"),
        ).grid(row=0, column=0, pady=(20, 16), padx=24, sticky="w")

        form = ctk.CTkFrame(self, fg_color=_c("panel"), border_color=_c("border"),
                            border_width=1, corner_radius=12)
        form.grid(row=1, column=0, padx=16, sticky="ew")
        form.columnconfigure(1, weight=1)

        def lbl(text, r):
            ctk.CTkLabel(form, text=text, text_color=_c("accent"),
                         font=ctk.CTkFont(size=11, weight="bold"), anchor="w",
            ).grid(row=r, column=0, padx=(16, 8), pady=6, sticky="w")

        # Nombre
        lbl("NOMBRE", 0)
        self._name = ctk.CTkEntry(form, fg_color=_c("panel_light"),
                                   border_color=_c("accent"), text_color=_c("text"),
                                   corner_radius=8, height=34)
        self._name.grid(row=0, column=1, padx=(0, 16), pady=6, sticky="ew")
        self._name.insert(0, "Mi Instancia")

        # Usuario
        lbl("USUARIO", 1)
        self._username = ctk.CTkEntry(form, fg_color=_c("panel_light"),
                                       border_color=_c("border"), text_color=_c("text"),
                                       corner_radius=8, height=34)
        self._username.grid(row=1, column=1, padx=(0, 16), pady=6, sticky="ew")
        self._username.insert(0, "Player")

        # MC Version
        lbl("VERSIÓN MC", 2)
        self._mc_version = ctk.CTkOptionMenu(
            form, values=self._versions or ["1.21.1"],
            fg_color=_c("panel_light"), button_color=_c("accent_dim"),
            button_hover_color=_c("accent"), text_color=_c("text"),
            dropdown_fg_color=_c("panel"), dropdown_text_color=_c("text"),
            corner_radius=8, height=34, command=self._on_version_change,
        )
        self._mc_version.grid(row=2, column=1, padx=(0, 16), pady=6, sticky="ew")

        # Loader
        lbl("LOADER", 3)
        self._loader_frame = ctk.CTkFrame(form, fg_color="transparent")
        self._loader_frame.grid(row=3, column=1, padx=(0, 16), pady=6, sticky="ew")
        self._loader_btns: Dict[str, ctk.CTkButton] = {}
        for i, lid in enumerate(LOADER_IDS):
            b = ctk.CTkButton(
                self._loader_frame,
                text=f"{LOADER_ICONS[lid]} {lid.capitalize()}",
                width=90, height=30,
                fg_color=_c("panel_light"), hover_color=_c("accent_dim"),
                text_color=_c("text"), corner_radius=6,
                command=lambda l=lid: self._select_loader(l),
            )
            b.grid(row=0, column=i, padx=2)
            self._loader_btns[lid] = b
        self._selected_loader = "vanilla"

        # Loader version
        lbl("VER. LOADER", 4)
        self._loader_ver = ctk.CTkOptionMenu(
            form, values=["latest"],
            fg_color=_c("panel_light"), button_color=_c("accent_dim"),
            button_hover_color=_c("accent"), text_color=_c("text"),
            dropdown_fg_color=_c("panel"), dropdown_text_color=_c("text"),
            corner_radius=8, height=34, state="disabled",
        )
        self._loader_ver.grid(row=4, column=1, padx=(0, 16), pady=6, sticky="ew")
        # Aplicar selección inicial DESPUÉS de que _loader_ver existe
        self._select_loader("vanilla")

        # RAM
        lbl("MEMORIA RAM", 5)
        self._ram = ctk.CTkOptionMenu(
            form,
            values=[format_ram_label(mb) for mb in RAM_OPTIONS_MB],
            fg_color=_c("panel_light"), button_color=_c("accent_dim"),
            button_hover_color=_c("accent"), text_color=_c("text"),
            dropdown_fg_color=_c("panel"), dropdown_text_color=_c("text"),
            corner_radius=8, height=34,
        )
        self._ram.grid(row=5, column=1, padx=(0, 16), pady=6, sticky="ew")
        self._ram.set(format_ram_label(DEFAULT_RAM_MB))

        # Directorio de instalación
        lbl("DIRECTORIO", 6)
        dir_row = ctk.CTkFrame(form, fg_color="transparent")
        dir_row.grid(row=6, column=1, padx=(0, 16), pady=6, sticky="ew")
        dir_row.columnconfigure(1, weight=1)
        self._game_dir: str = ""
        self._dir_btn = ctk.CTkButton(dir_row, text="📁", width=32, height=32,
                                       fg_color=_c("panel_light"), hover_color=_c("accent_dim"),
                                       corner_radius=6, command=self._pick_dir)
        self._dir_btn.grid(row=0, column=0, padx=(0, 6))
        self._dir_lbl = ctk.CTkLabel(dir_row, text="Por defecto (~/.ctk-mc-launcher/instances/...)",
                                      text_color=_c("text_dim"), font=ctk.CTkFont(size=10), anchor="w")
        self._dir_lbl.grid(row=0, column=1, sticky="ew")

        # Botones
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=2, column=0, pady=16, padx=16, sticky="ew")
        btns.columnconfigure((0, 1), weight=1)

        ctk.CTkButton(btns, text="Cancelar", height=38,
                      fg_color=_c("panel_light"), hover_color=_c("border"),
                      text_color=_c("text"), corner_radius=8,
                      command=self.destroy,
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(btns, text="✅  Crear Perfil", height=38,
                      fg_color=_c("play"), hover_color=_c("play_hover"),
                      text_color=_c("accent"), border_color=_c("accent"),
                      border_width=1, corner_radius=8,
                      command=self._confirm,
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def _select_loader(self, loader_id: str) -> None:
        self._selected_loader = loader_id
        for lid, btn in self._loader_btns.items():
            if lid == loader_id:
                color = LOADER_COLORS.get(lid, _c("accent_dim"))
                btn.configure(fg_color=color, text_color="#000000")
            else:
                btn.configure(fg_color=_c("panel_light"), text_color=_c("text"))
        # Cargar versiones del loader en background
        if loader_id == "vanilla":
            self._loader_ver.configure(values=["N/A"], state="disabled")
            self._loader_ver.set("N/A")
        else:
            self._loader_ver.configure(values=["Cargando..."], state="disabled")
            mc_ver = self._mc_version.get()
            # Guardar el loader activo para descartar respuestas de requests anteriores
            self._pending_loader = loader_id
            threading.Thread(target=self._fetch_loader_versions,
                             args=(loader_id, mc_ver), daemon=True).start()

    def _on_version_change(self, _=None) -> None:
        if self._selected_loader != "vanilla":
            self._select_loader(self._selected_loader)

    def _fetch_loader_versions(self, loader_id: str, mc_ver: str) -> None:
        # stable_only=False para mostrar todas las versiones disponibles
        versions = loaders.get_versions(loader_id, mc_ver, stable_only=False)
        labels = versions if versions else ["latest"]
        # Solo aplicar si este request sigue siendo el actual (evitar datos stale)
        def _apply():
            if self._pending_loader == loader_id:
                self._set_loader_versions(labels)
        try:
            self.after(0, _apply)
        except Exception:
            pass  # Dialog destroyed while loading

    def _set_loader_versions(self, versions: List[str]) -> None:
        self._loader_ver.configure(values=versions, state="normal")
        self._loader_ver.set(versions[0])

    def _pick_dir(self) -> None:
        from tkinter import filedialog
        chosen = filedialog.askdirectory(title="Selecciona directorio de la instancia")
        if chosen:
            self._game_dir = chosen
            short = chosen[-32:] if len(chosen) > 32 else chosen
            self._dir_lbl.configure(text="…" + short if len(chosen) > 32 else short,
                                     text_color=_c("text"))

    def _confirm(self) -> None:
        name = self._name.get().strip() or "Mi Instancia"
        username = self._username.get().strip() or "Player"
        mc_version = self._mc_version.get()
        loader = self._selected_loader
        loader_ver_raw = self._loader_ver.get()
        loader_version = None if loader_ver_raw in ("N/A", "latest", "Cargando...") else loader_ver_raw

        ram_label = self._ram.get()
        try:
            parts = ram_label.split()
            ram_mb = int(parts[0]) * 1024 if "GB" in ram_label else int(parts[0])
        except (IndexError, ValueError):
            ram_mb = config.DEFAULT_RAM_MB

        data = {
            "name":           name,
            "username":       username,
            "mc_version":     mc_version,
            "loader":         loader,
            "loader_version": loader_version,
            "ram_mb":         ram_mb,
            "game_dir":       self._game_dir or None,
        }
        self.destroy()
        self._on_create(data)


