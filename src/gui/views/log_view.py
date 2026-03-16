from __future__ import annotations

"""Vista de la consola de log."""

import customtkinter as ctk
from typing import TYPE_CHECKING

from src.gui.components import LogConsole

if TYPE_CHECKING:
    from src.gui.main_window import MainWindow


class LogView(ctk.CTkFrame):
    """Página del log — envuelve LogConsole."""

    def __init__(self, parent: ctk.CTkFrame, app: MainWindow) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._console = LogConsole(self)
        self._console.pack(fill="both", expand=True, padx=24, pady=24)

    def log(self, message: str, level: str = "info") -> None:
        """Añade un mensaje al log. Llamado por MainWindow.log()."""
        self._console.log(message, level)
