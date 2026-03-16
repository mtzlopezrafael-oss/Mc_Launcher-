from __future__ import annotations

"""Vista de ajustes del launcher."""

import os
import platform
import subprocess
import threading
import customtkinter as ctk
from typing import TYPE_CHECKING

from src.gui.components import COLORS, SettingsCard, ToggleSwitch
from src.utils.config import CURRENT_THEME

if TYPE_CHECKING:
    from src.gui.main_window import MainWindow


class SettingsView(ctk.CTkFrame):
    """Página de ajustes — comportamiento y about."""

    def __init__(self, parent: ctk.CTkFrame, app: MainWindow) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self) -> None:
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["panel_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=24)

        # Header
        ctk.CTkLabel(
            scroll,
            text="Ajustes",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", pady=(0, 20))

        # ── Tema visual ───────────────────────────────────────────
        theme_card = SettingsCard(
            scroll,
            title="Tema visual",
            description="Se reinicia el launcher para aplicar el cambio",
            icon="🎨",
        )
        theme_card.pack(fill="x", pady=(0, 16))

        theme_row = ctk.CTkFrame(theme_card.content, fg_color="transparent")
        theme_row.pack(fill="x")

        # Botones Claro / Oscuro
        btn_kw_active = dict(
            height=34, width=110,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent"],
            text_color="#ffffff",
            corner_radius=8,
        )
        btn_kw_inactive = dict(
            height=34, width=110,
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["panel_light"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_dim"],
            corner_radius=8,
        )

        self._btn_light = ctk.CTkButton(
            theme_row, text="☀️  Claro",
            command=lambda: self._on_theme_change("light"),
            **(btn_kw_active if CURRENT_THEME == "light" else btn_kw_inactive),
        )
        self._btn_light.pack(side="left", padx=(0, 8))

        self._btn_dark = ctk.CTkButton(
            theme_row, text="🌑  Oscuro",
            command=lambda: self._on_theme_change("dark"),
            **(btn_kw_active if CURRENT_THEME == "dark" else btn_kw_inactive),
        )
        self._btn_dark.pack(side="left")

        # ── Versiones ─────────────────────────────────────────────
        versions_card = SettingsCard(
            scroll,
            title="Versiones de Minecraft",
            description="Qué versiones aparecen al crear un perfil",
            icon="🎮",
        )
        versions_card.pack(fill="x", pady=(0, 16))

        self._snapshots_toggle = ToggleSwitch(
            versions_card.content,
            label="Mostrar snapshots y pre-releases",
            initial=self.app._show_snapshots,
            on_change=self._on_show_snapshots_change,
        )
        self._snapshots_toggle.pack(fill="x")

        # ── Comportamiento ────────────────────────────────────────
        close_card = SettingsCard(
            scroll,
            title="Comportamiento",
            description="Opciones del launcher",
            icon="🖥️",
        )
        close_card.pack(fill="x", pady=(0, 16))

        self._close_on_launch_toggle = ToggleSwitch(
            close_card.content,
            label="Cerrar launcher al iniciar el juego",
            initial=self.app._close_on_launch,
            on_change=self._on_close_on_launch_change,
        )
        self._close_on_launch_toggle.pack(fill="x")

        # ── Actualizaciones ──────────────────────────────────────
        update_card = SettingsCard(
            scroll,
            title="Actualizaciones",
            description="Comprueba si hay una nueva versión del launcher",
            icon="🔄",
        )
        update_card.pack(fill="x", pady=(0, 16))

        update_row = ctk.CTkFrame(update_card.content, fg_color="transparent")
        update_row.pack(fill="x")

        self._update_status_label = ctk.CTkLabel(
            update_row,
            text=f"Versión instalada: v{self.app.APP_VERSION}",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"],
        )
        self._update_status_label.pack(side="left")

        self._check_update_btn = ctk.CTkButton(
            update_row,
            text="Buscar actualizaciones",
            width=160, height=30,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["panel_light"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            corner_radius=8,
            command=self._on_check_update,
        )
        self._check_update_btn.pack(side="right")

        # Botón de instalación — visible solo si hay update disponible
        self._install_update_btn = ctk.CTkButton(
            update_card.content,
            text="⬇  Instalar actualización",
            height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent2"],
            text_color="#ffffff",
            corner_radius=8,
            command=self.app._on_install_update,
        )
        # Solo se muestra si ya hay update encontrado
        if self.app._update_info is not None:
            self._install_update_btn.pack(fill="x", pady=(8, 0))
            self._update_status_label.configure(
                text=f"🆕 v{self.app._update_info.version} disponible",
                text_color=COLORS["success"],
            )

        # ── Diagnósticos ─────────────────────────────────────────
        diag_card = SettingsCard(
            scroll,
            title="Diagnósticos",
            description="Logs de errores para reportar problemas al desarrollador",
            icon="🐛",
        )
        diag_card.pack(fill="x", pady=(0, 16))

        # Ruta del log actual
        from src.utils.logger import get_log_file, get_log_dir
        _log_file = get_log_file()
        _log_dir  = get_log_dir()
        _log_path_text = str(_log_file) if _log_file else "No disponible"

        self._diag_path_label = ctk.CTkLabel(
            diag_card.content,
            text=f"📄 {_log_path_text}",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
            anchor="w",
            wraplength=500,
        )
        self._diag_path_label.pack(anchor="w", pady=(0, 10))

        diag_btn_row = ctk.CTkFrame(diag_card.content, fg_color="transparent")
        diag_btn_row.pack(fill="x")

        ctk.CTkButton(
            diag_btn_row,
            text="📂  Abrir carpeta de logs",
            width=180, height=32,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["panel_light"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            corner_radius=8,
            command=self._open_log_folder,
        ).pack(side="left", padx=(0, 8))

        self._copy_log_btn = ctk.CTkButton(
            diag_btn_row,
            text="📋  Copiar log",
            width=130, height=32,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["panel_light"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            corner_radius=8,
            command=self._copy_log_to_clipboard,
        )
        self._copy_log_btn.pack(side="left")

        # ── Acerca de ────────────────────────────────────────────
        about_card = SettingsCard(
            scroll,
            title="Acerca de",
            description=f"MC Launcher v{self.app.APP_VERSION}",
            icon="ℹ️",
        )
        about_card.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            about_card.content,
            text="Un launcher moderno de Minecraft.\nDesarrollado con Python y customtkinter.",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"],
            justify="left",
        ).pack(anchor="w")

    # ── Callbacks ─────────────────────────────────────────────────

    def _on_theme_change(self, theme: str) -> None:
        if theme == CURRENT_THEME:
            return
        self.app.change_theme(theme)

    def _on_show_snapshots_change(self, value: bool) -> None:
        self.app.set_show_snapshots(value)

    def _on_close_on_launch_change(self, value: bool) -> None:
        self.app._close_on_launch = value
        self.app._save_setting("close_on_launch", value)
        self.app.log(f"Cerrar al iniciar: {'Sí' if value else 'No'}")

    def _on_check_update(self) -> None:
        """Busca actualizaciones manualmente desde Ajustes."""
        self._check_update_btn.configure(text="Buscando...", state="disabled")

        import threading
        from src.updater import check_for_updates
        from src.utils.config import UPDATE_VERSION_URL

        def _check():
            try:
                info = check_for_updates(self.app.APP_VERSION, UPDATE_VERSION_URL)
            except Exception:
                info = None

            def _apply():
                self._check_update_btn.configure(
                    text="Buscar actualizaciones", state="normal",
                )
                if info is not None:
                    self.app._update_info = info
                    self._update_status_label.configure(
                        text=f"🆕 v{info.version} disponible — {info.changelog[:60]}",
                        text_color=COLORS["success"],
                    )
                    self._install_update_btn.pack(fill="x", pady=(8, 0))
                    # También mostrar banner en sidebar
                    self.app._on_update_found(info)
                else:
                    self._update_status_label.configure(
                        text=f"✓ Estás en la versión más reciente (v{self.app.APP_VERSION})",
                        text_color=COLORS["text_dim"],
                    )
                    self.app.log("Ya tienes la versión más reciente")

            try:
                self.after(0, _apply)
            except Exception:
                pass

        threading.Thread(target=_check, daemon=True).start()

    # ── Diagnósticos ───────────────────────────────────────────────

    def _open_log_folder(self) -> None:
        """Abre la carpeta de logs en el explorador de archivos del SO."""
        from src.utils.logger import get_log_dir
        log_dir = get_log_dir()
        if log_dir is None or not log_dir.exists():
            self.app.log("No se encontró la carpeta de logs", "warning")
            return
        try:
            sys_name = platform.system()
            if sys_name == "Windows":
                os.startfile(str(log_dir))          # type: ignore[attr-defined]
            elif sys_name == "Darwin":
                subprocess.Popen(["open", str(log_dir)])
            else:
                subprocess.Popen(["xdg-open", str(log_dir)])
        except Exception as exc:
            self.app.log(f"No se pudo abrir la carpeta de logs: {exc}", "error")

    def _copy_log_to_clipboard(self) -> None:
        """
        Copia el contenido de las últimas 200 líneas del log al portapapeles.
        Muestra confirmación en el botón.
        """
        from src.utils.logger import read_log_tail
        content = read_log_tail(200)
        try:
            self.clipboard_clear()
            self.clipboard_append(content)
            # Feedback visual: cambia el texto del botón por 2 segundos
            self._copy_log_btn.configure(
                text="✓  Copiado",
                fg_color=COLORS["success"],
                text_color="#ffffff",
            )
            self.after(2000, lambda: self._copy_log_btn.configure(
                text="📋  Copiar log",
                fg_color=COLORS["panel_light"],
                text_color=COLORS["text"],
            ))
        except Exception as exc:
            self.app.log(f"No se pudo copiar el log: {exc}", "error")
