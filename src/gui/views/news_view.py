from __future__ import annotations

"""Vista de noticias / patch notes de Minecraft."""

import threading
import customtkinter as ctk
from typing import Dict, List, TYPE_CHECKING

from src.gui.components import COLORS, NewsCard
from src.utils.news import fetch_patch_notes

try:
    from src.gui.icons import get as _ico
except ImportError:
    def _ico(name, size=(18, 18)):  # type: ignore[misc]
        return None

if TYPE_CHECKING:
    from src.gui.main_window import MainWindow


class NewsView(ctk.CTkFrame):
    """Página de noticias — carga y muestra patch notes."""

    def __init__(self, parent: ctk.CTkFrame, app: MainWindow) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self) -> None:
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(24, 16))

        ctk.CTkLabel(
            header,
            text="Noticias de Minecraft",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS["text"],
        ).pack(side="left")

        _ic_ref = _ico("refresh", (16, 16))
        _ref_kw = {"image": _ic_ref, "compound": "left"} if _ic_ref else {}
        ctk.CTkButton(
            header,
            text="  Actualizar" if _ic_ref else "↺ Actualizar",
            width=110,
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["panel_light"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self.refresh,
            **_ref_kw,
        ).pack(side="right")

        # Scrollable news list
        self._news_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["panel_light"],
            scrollbar_button_hover_color=COLORS["border"],
        )
        self._news_scroll.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self._container = ctk.CTkFrame(self._news_scroll, fg_color="transparent")
        self._container.pack(fill="both", expand=True)

    # ── Refresh ───────────────────────────────────────────────────

    def refresh(self) -> None:
        """Descarga las noticias en un hilo y actualiza la UI."""

        def fetch():
            try:
                news = fetch_patch_notes(limit=8)
            except Exception:
                news = []
            try:
                self.after(0, lambda: self._display(news))
            except Exception:
                pass

        threading.Thread(target=fetch, daemon=True).start()

    def _display(self, news: List[Dict]) -> None:
        for w in self._container.winfo_children():
            w.destroy()

        if not news:
            ctk.CTkLabel(
                self._container,
                text="No hay noticias disponibles.",
                font=ctk.CTkFont(size=14),
                text_color=COLORS["text_dim"],
            ).pack(pady=50)
            return

        for item in news:
            NewsCard(
                self._container,
                title=item.get("title", "Sin título"),
                version=item.get("version", ""),
                release_type=item.get("type", "release"),
                date=item.get("date", ""),
            ).pack(fill="x", pady=4)
