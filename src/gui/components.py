"""
Minecraft Launcher - Reusable UI Components
Adapted from Next.js/React design to Python customtkinter
"""

import tkinter as tk
import customtkinter as ctk
import threading
from PIL import Image, ImageDraw
import io
import urllib.request
from typing import Callable, Optional, Dict, Any, List

# FIX-J: Importar COLORS y LOADER_COLORS desde config en vez de duplicarlos aquí.
# Si config no está disponible en el entorno (tests aislados, etc.), se usa el
# fallback local definido abajo — eliminar el fallback cuando el import funcione.
try:
    from src.utils.config import COLORS, LOADER_COLORS
    from src.launcher.mods import format_downloads as _format_downloads
except ImportError:
    _format_downloads = None  # fallback definido en ModCard._format_downloads

# Iconos PNG — importación opcional: si no están disponibles se degradan
# de forma elegante usando los emojis / textos de respaldo ya existentes.
try:
    from src.gui.icons import get as _ico
except ImportError:
    def _ico(name, size=(18, 18)):  # type: ignore[misc]
        return None
    # Fallback para ejecución aislada / tests
    COLORS = {
        "bg":          "#f0f1f5",
        "panel":       "#ffffff",
        "panel_light": "#f7f8fc",
        "border":      "#dde0ec",
        "accent":      "#3b7dd8",
        "accent_dim":  "#e8f0fd",
        "accent2":     "#7c3aed",
        "text":        "#1a1d2e",
        "text_dim":    "#7480a0",
        "success":     "#16a34a",
        "error":       "#dc2626",
        "warning":     "#d97706",
        "play":        "#eef4ff",
        "play_hover":  "#d5e6ff",
    }
    LOADER_COLORS = {
        "vanilla":  "#2d8a3e",
        "fabric":   "#b07040",
        "forge":    "#c05820",
        "neoforge": "#c06800",
    }


# FIX-F: Función helper requerida por ToggleSwitch para obtener el tk.Tk raíz
# real, evitando el crash de CTkFrame._root() en customtkinter 5.2.2.
# REGLA 3 del contexto: tk.BooleanVar(master=CTkFrame) → crash garantizado.
def _find_root(widget) -> tk.Tk:
    """Sube por la jerarquía de widgets hasta encontrar el tk.Tk / ctk.CTk raíz."""
    w = widget
    while not isinstance(w, (tk.Tk, ctk.CTk)):
        w = w.master
    return w


# ---------------------------------------------------------------------------
# GlassFrame
# ---------------------------------------------------------------------------

class GlassFrame(ctk.CTkFrame):
    """
    A styled frame with glass-like appearance matching the launcher design.
    Used as base container for cards and panels.
    """
    def __init__(
        self,
        master: Any,
        fg_color: str = None,
        border_color: str = None,
        border_width: int = 1,
        corner_radius: int = 12,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=fg_color or COLORS["panel"],
            border_color=border_color or COLORS["border"],
            border_width=border_width,
            corner_radius=corner_radius,
            **kwargs
        )


# ---------------------------------------------------------------------------
# AvatarWidget
# ---------------------------------------------------------------------------

# FIX-A: Hereda CTkFrame (no CTkLabel).
# REGLA 9: CTkLabel con image + fg_color tiene bugs de render en CTK 5.2.2.
# Patrón correcto: CTkFrame exterior + CTkLabel interno para la imagen.
class AvatarWidget(ctk.CTkFrame):
    """
    Displays a player avatar image (Minecraft head style).
    Falls back to a colored placeholder if image fails to load.
    """
    def __init__(
        self,
        master: Any,
        size: int = 40,
        username: str = "Steve",
        **kwargs
    ):
        self.size = size
        self.username = username

        super().__init__(
            master,
            width=size,
            height=size,
            fg_color=COLORS["panel_light"],
            corner_radius=8,
            **kwargs
        )
        self.grid_propagate(False)
        self.pack_propagate(False)

        # Placeholder creado antes del label para tener una imagen lista
        self._placeholder = self._create_placeholder()
        self._avatar_image = None

        # Label interno que muestra la imagen (evita bug fg_color en CTkLabel)
        self._img_label = ctk.CTkLabel(
            self,
            text="",
            image=self._placeholder,
            fg_color="transparent",
            width=size,
            height=size,
        )
        self._img_label.place(relx=0.5, rely=0.5, anchor="center")

        # FIX-B: _load_avatar en thread daemon para no bloquear el hilo principal.
        # REGLA 10: cualquier descarga de red SIEMPRE en Thread.
        threading.Thread(target=self._load_avatar, daemon=True).start()

    def _create_placeholder(self) -> ctk.CTkImage:
        """Create a colored placeholder."""
        img = Image.new("RGB", (self.size * 2, self.size * 2), COLORS["accent_dim"])
        draw = ImageDraw.Draw(img)
        face_color = COLORS["accent"]
        draw.rectangle(
            [self.size // 2, self.size // 2, self.size * 3 // 2, self.size * 3 // 2],
            fill=face_color
        )
        return ctk.CTkImage(light_image=img, dark_image=img, size=(self.size, self.size))

    def _load_avatar(self):
        """Descarga el avatar desde mc-heads.net (se ejecuta en thread)."""
        try:
            url = f"https://mc-heads.net/avatar/{self.username}/{self.size * 2}"
            with urllib.request.urlopen(url, timeout=3) as response:
                data = response.read()
            img = Image.open(io.BytesIO(data))
            ctk_img = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(self.size, self.size)
            )
            self._avatar_image = ctk_img  # mantener referencia

            # FIX-C: actualizar UI desde el hilo principal con self.after().
            # REGLA 5: NUNCA actualizar widgets directamente desde un Thread.
            def _update():
                try:
                    self._img_label.configure(image=ctk_img)
                except Exception:
                    pass  # Widget destruido — ignorar
            self.after(0, _update)

        except Exception:
            pass  # Mantener placeholder en caso de error

    def refresh(self, username: str = None):
        """Actualiza el avatar con un nuevo username."""
        if username:
            self.username = username
        self._img_label.configure(image=self._placeholder)
        threading.Thread(target=self._load_avatar, daemon=True).start()


# ---------------------------------------------------------------------------
# PlayButton
# ---------------------------------------------------------------------------

class PlayButton(ctk.CTkButton):
    """
    The main PLAY button with special styling and loading/locked states.
    """
    def __init__(
        self,
        master: Any,
        command: Callable = None,
        **kwargs
    ):
        self._is_launching = False
        self._is_locked = False
        self._original_command = command

        super().__init__(
            master,
            text="PLAY",
            command=self._handle_click,
            width=120,
            height=44,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=COLORS["success"],
            hover_color="#00cc6a",
            text_color="#000000",
            corner_radius=12,
            **kwargs
        )

    def _handle_click(self):
        if not self._is_launching and not self._is_locked and self._original_command:
            self._original_command()

    def set_launching(self, launching: bool):
        """Cambia el botón al estado de lanzamiento."""
        self._is_launching = launching
        if launching:
            self.configure(
                text="Launching...",
                fg_color=COLORS["play"],
                hover_color=COLORS["play_hover"],
                state="disabled"
            )
        else:
            self._is_locked = False
            self.configure(
                text="PLAY",
                fg_color=COLORS["success"],
                hover_color="#00cc6a",
                state="normal"
            )

    def set_playing(self, playing: bool):
        """Cambia el botón al estado 'Playing' mientras Minecraft está abierto."""
        self._is_launching = playing
        if playing:
            self.configure(
                text="Playing",
                fg_color="#7c3aed",
                hover_color="#7c3aed",
                state="disabled"
            )
        else:
            self._is_launching = False
            self._is_locked = False
            self.configure(
                text="PLAY",
                fg_color=COLORS["success"],
                hover_color="#00cc6a",
                state="normal"
            )

    # FIX-H: Método set_locked requerido por main_window.py.
    # main_window llama set_locked(True, reason="no_profile") y
    # set_locked(True, reason="installing") — sin este método hay AttributeError.
    def set_locked(self, locked: bool, reason: str = "installing"):
        """
        Bloquea o desbloquea el botón con un mensaje acorde al motivo.
        reason: "installing" | "no_profile"
        """
        self._is_locked = locked
        if locked:
            label = "⏳ INSTALANDO..." if reason == "installing" else "Sin perfil"
            self.configure(
                text=label,
                fg_color=COLORS["panel_light"],
                hover_color=COLORS["panel_light"],
                state="disabled"
            )
        else:
            self.configure(
                text="PLAY",
                fg_color=COLORS["success"],
                hover_color="#00cc6a",
                state="normal"
            )

    @property
    def is_launching(self) -> bool:
        return self._is_launching


# ---------------------------------------------------------------------------
# ProgressBar
# ---------------------------------------------------------------------------

# FIX-G: Usa CTkProgressBar nativo en vez del hack CTkFrame + .place().
# REGLA (BUG-051): el hack de .place() para el fill produce altura incorrecta.
class ProgressBar(ctk.CTkFrame):
    """
    Progress bar usando CTkProgressBar nativo.
    """
    def __init__(
        self,
        master: Any,
        width: int = 400,
        height: int = 8,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self._progress_val = 0.0

        self._bar = ctk.CTkProgressBar(
            self,
            width=width,
            height=height,
            corner_radius=4,
            fg_color=COLORS["panel_light"],
            progress_color=COLORS["accent"],
        )
        self._bar.set(0)
        self._bar.pack(fill="x")

    def set_progress(self, value: float):
        """Set progress value (0.0 to 1.0)."""
        self._progress_val = max(0.0, min(1.0, value))
        self._bar.set(self._progress_val)

    def get_progress(self) -> float:
        return self._progress_val


# ---------------------------------------------------------------------------
# ProgressBarWithLabel
# ---------------------------------------------------------------------------

class ProgressBarWithLabel(ctk.CTkFrame):
    """Progress bar with text label showing percentage or status."""
    def __init__(
        self,
        master: Any,
        width: int = 400,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            **kwargs
        )

        self._label = ctk.CTkLabel(
            self,
            text="0%",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"]
        )
        self._label.pack(anchor="w", pady=(0, 4))

        self._bar = ProgressBar(self, width=width)
        self._bar.pack(fill="x")

    def set_progress(self, value: float, label: str = None):
        """Set progress and optionally update label."""
        self._bar.set_progress(value)
        if label:
            self._label.configure(text=label)
        else:
            self._label.configure(text=f"{int(value * 100)}%")


# ---------------------------------------------------------------------------
# NewsCard
# ---------------------------------------------------------------------------

class NewsCard(ctk.CTkFrame):
    """
    Card component for displaying Minecraft news/patch notes.
    Shows title, version badge, release type, and date.
    SIN botón .place() overlay — REGLA 8: tapa visualmente todo el contenido.
    """
    def __init__(
        self,
        master: Any,
        title: str,
        version: str,
        release_type: str = "release",
        date: str = "",
        on_click: Callable = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=COLORS["panel"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12,
            **kwargs
        )

        self._on_click = on_click

        # Configure grid
        self.grid_columnconfigure(0, weight=1)

        # Content container
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew", padx=16, pady=12)
        content.grid_columnconfigure(0, weight=1)

        # Header row with title and badge
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w")

        # FIX: badge usa CTkFrame + CTkLabel para evitar bug fg_color en CTkLabel
        # REGLA 7: para badges con fondo de color usar CTkFrame + CTkLabel adentro.
        badge_color = COLORS["success"] if release_type.lower() == "release" else COLORS["warning"]
        badge_frame = ctk.CTkFrame(
            header,
            fg_color=badge_color,
            corner_radius=4,
            width=70,
            height=20,
        )
        badge_frame.grid(row=0, column=1, sticky="e", padx=(8, 0))
        badge_frame.grid_propagate(False)
        ctk.CTkLabel(
            badge_frame,
            text=release_type.upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#000000",
            fg_color="transparent",
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Version and date row
        info_frame = ctk.CTkFrame(content, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        version_label = ctk.CTkLabel(
            info_frame,
            text=version,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["accent"],
            anchor="w"
        )
        version_label.pack(side="left")

        if date:
            date_label = ctk.CTkLabel(
                info_frame,
                text=f"  •  {date}",
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text_dim"],
                anchor="w"
            )
            date_label.pack(side="left")

        # FIX-D: Eliminado el botón .place(relwidth=1, relheight=1).
        # REGLA 8: ese overlay tapa todo el contenido aunque sea transparente.
        # on_click no se usa actualmente en la UI — se elimina el overlay.
        # Si en el futuro se necesita click, agregar un CTkButton explícito
        # en el layout normal (no con .place()).


# ---------------------------------------------------------------------------
# LogConsole
# ---------------------------------------------------------------------------

class LogConsole(ctk.CTkFrame):
    """
    Read-only text console for displaying launcher logs.
    Features auto-scroll and clear button.
    """
    # OPT-007: límite de líneas para evitar consumo infinito de memoria
    MAX_LINES = 800

    def __init__(
        self,
        master: Any,
        max_lines: int = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=COLORS["panel"],
            corner_radius=12,
            **kwargs
        )
        if max_lines is not None:
            self.MAX_LINES = max_lines

        # Header with clear button
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 8))

        title = ctk.CTkLabel(
            header,
            text="Console Log",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"]
        )
        title.pack(side="left")

        _ic_x = _ico("x", (14, 14))
        _x_kwargs: Dict[str, Any] = (
            {"image": _ic_x, "compound": "left"} if _ic_x else {}
        )
        self._clear_btn = ctk.CTkButton(
            header,
            text="  Limpiar" if _ic_x else "Limpiar",
            width=80,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["panel_light"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_dim"],
            command=self.clear,
            **_x_kwargs,
        )
        self._clear_btn.pack(side="right")

        # Text area
        self._textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=COLORS["bg"],
            text_color=COLORS["text"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=8,
            wrap="word"
        )
        self._textbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._textbox.configure(state="disabled")

    def log(self, message: str, level: str = "info"):
        """Add a log message with optional level coloring."""
        from datetime import datetime
        self._textbox.configure(state="normal")

        timestamp = datetime.now().strftime("%H:%M:%S")

        prefix = ""
        if level == "error":
            prefix = "[ERROR] "
        elif level == "warning":
            prefix = "[WARN] "
        elif level == "success":
            prefix = "[OK] "

        self._textbox.insert("end", f"[{timestamp}] {prefix}{message}\n")

        # OPT-007: recortar líneas excedentes para no consumir memoria sin límite
        line_count = int(self._textbox.index("end-1c").split(".")[0])
        if line_count > self.MAX_LINES:
            excess = line_count - self.MAX_LINES
            self._textbox.delete("1.0", f"{excess + 1}.0")

        self._textbox.configure(state="disabled")
        self._textbox.see("end")

    def clear(self):
        """Clear all log messages."""
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")


# ---------------------------------------------------------------------------
# ProfileCard
# ---------------------------------------------------------------------------

class ProfileCard(ctk.CTkFrame):
    """
    Card component for displaying a game profile/instance.
    NO .place() overlay — select button at bottom to avoid covering content.

    on_select  → selecciona el perfil como activo para jugar (fila 0, ancho completo)
    on_open    → abre la vista de detalle de instancia (fila 1, izquierda)
    on_delete  → elimina el perfil (fila 1, derecha)
    """
    def __init__(
        self,
        master: Any,
        profile: Dict[str, Any],
        on_select: Callable = None,
        on_open: Callable = None,
        on_delete: Callable = None,
        is_selected: bool = False,
        **kwargs
    ):
        border_color = COLORS["accent"] if is_selected else COLORS["border"]
        bg = COLORS["accent_dim"] if is_selected else COLORS["panel"]

        super().__init__(
            master,
            fg_color=bg,
            border_color=border_color,
            border_width=2 if is_selected else 1,
            corner_radius=12,
            **kwargs
        )

        loader = profile.get("loader", "vanilla").lower()
        loader_color = LOADER_COLORS.get(loader, COLORS["text_dim"])
        loader_icons = {"vanilla": "⬜", "fabric": "🌿", "forge": "🔨", "neoforge": "🔥"}
        icon = loader_icons.get(loader, "⬜")

        # ── Content area ──────────────────────────────────────────────
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=12)
        inner.columnconfigure(1, weight=1)

        # Loader icon badge (CTkFrame con label — evita bug fg_color en CTkLabel)
        # REGLA 7: usar CTkFrame + CTkLabel interno para badges con color de fondo.
        badge_frame = ctk.CTkFrame(inner, fg_color=loader_color,
                                    corner_radius=6, width=36, height=36)
        badge_frame.grid(row=0, column=0, rowspan=2, padx=(0, 10), sticky="nw")
        badge_frame.grid_propagate(False)
        ctk.CTkLabel(badge_frame, text=icon, font=ctk.CTkFont(size=18),
                     fg_color="transparent",
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Profile name
        ctk.CTkLabel(inner,
                     text=profile.get("name", "Sin nombre"),
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COLORS["text"], anchor="w",
        ).grid(row=0, column=1, sticky="w")

        # Info subtitle
        mc_ver = profile.get("mc_version", "?")
        ram_gb = profile.get("ram_mb", 2048) // 1024
        info = f"MC {mc_ver}  •  {loader.capitalize()}  •  {ram_gb} GB"
        ctk.CTkLabel(inner,
                     text=info,
                     font=ctk.CTkFont(size=11),
                     text_color=loader_color, anchor="w",
        ).grid(row=1, column=1, sticky="w")

        # Last played
        lp = profile.get("last_played")
        if lp:
            ctk.CTkLabel(inner,
                         text=f"Último: {lp[:16]}",
                         font=ctk.CTkFont(size=10),
                         text_color=COLORS["text_dim"], anchor="w",
            ).grid(row=2, column=1, sticky="w", pady=(2, 0))

        # ── Action buttons ────────────────────────────────────────────
        sep = ctk.CTkFrame(self, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", padx=14)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(8, 12))
        actions.columnconfigure(0, weight=1)

        # Iconos para los botones de acción
        _ic_sel    = _ico("play",   (14, 14))
        _ic_folder = _ico("folder", (14, 14))
        _ic_del    = _ico("trash",  (14, 14))

        # Fila 0: Seleccionar para jugar (ancho completo)
        _sel_kwargs: Dict[str, Any] = (
            {"image": _ic_sel, "compound": "left"} if _ic_sel else {}
        )
        ctk.CTkButton(actions,
                      text="  Seleccionar para jugar" if _ic_sel else "▶  Seleccionar para jugar",
                      height=30, font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color=COLORS["play"], hover_color=COLORS["play_hover"],
                      text_color=COLORS["accent"], border_color=COLORS["accent"],
                      border_width=1, corner_radius=6,
                      command=lambda: on_select(profile["id"]) if on_select else None,
                      **_sel_kwargs,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        # Fila 1: Abrir instancia | Borrar
        _open_kwargs: Dict[str, Any] = (
            {"image": _ic_folder, "compound": "left"} if _ic_folder else {}
        )
        ctk.CTkButton(actions,
                      text="  Abrir" if _ic_folder else "📂 Abrir",
                      height=28, font=ctk.CTkFont(size=11),
                      fg_color=COLORS["panel_light"], hover_color=COLORS["accent_dim"],
                      text_color=COLORS["text"], corner_radius=6,
                      command=lambda: on_open(profile["id"]) if on_open else None,
                      **_open_kwargs,
        ).grid(row=1, column=0, sticky="ew", padx=(0, 4))

        _del_kwargs: Dict[str, Any] = (
            {"image": _ic_del, "compound": "left"} if _ic_del else {}
        )
        ctk.CTkButton(actions,
                      text="  Borrar" if _ic_del else "✕ Borrar",
                      height=28, font=ctk.CTkFont(size=11),
                      fg_color=COLORS["panel_light"], hover_color=COLORS["error"],
                      text_color=COLORS["text_dim"], corner_radius=6,
                      command=lambda: on_delete(profile["id"]) if on_delete else None,
                      **_del_kwargs,
        ).grid(row=1, column=1, sticky="ew", padx=(4, 0))


# ---------------------------------------------------------------------------
# ModCard
# ---------------------------------------------------------------------------

class ModCard(ctk.CTkFrame):
    """
    Card for displaying mod search results.
    Shows icon, name, description, downloads, and install button.
    """
    def __init__(
        self,
        master: Any,
        mod_data: Dict[str, Any],
        on_install: Callable = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=COLORS["panel"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12,
            **kwargs
        )

        self._mod = mod_data
        self._on_install = on_install
        self._installed = False
        self._installing = False

        # Main container
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=12)
        content.grid_columnconfigure(1, weight=1)

        # Mod icon — carga async desde URL si está disponible.
        # FIX-SCROLL: _icon_label se mete dentro de un CTkFrame de tamaño fijo
        # con grid_propagate(False). Sin este contenedor, al scrollear rápido
        # el CTkScrollableFrame no recorta la imagen al área del widget y
        # la imagen "se escapa" visualmente sobre las cards vecinas.
        icon_url = mod_data.get("icon_url", "") or mod_data.get("icon", "")
        # Se guarda como self._icon_container para que _load_icon pueda llamar
        # update_idletasks() y forzar la reconciliación del canvas offset del scroll.
        self._icon_container = ctk.CTkFrame(
            content,
            width=50,
            height=50,
            fg_color=COLORS["panel_light"],
            corner_radius=8,
        )
        self._icon_container.grid(row=0, column=0, rowspan=3, padx=(0, 12), sticky="n", pady=(2, 0))
        self._icon_container.grid_propagate(False)

        self._icon_label = ctk.CTkLabel(
            self._icon_container,
            text="📦",
            font=ctk.CTkFont(size=28),
            fg_color="transparent",
            width=50,
            height=50,
        )
        self._icon_label.place(relx=0.5, rely=0.5, anchor="center")
        self._icon_ctk_image = None

        if icon_url and icon_url.startswith("http"):
            threading.Thread(
                target=self._load_icon,
                args=(icon_url,),
                daemon=True
            ).start()

        # Name and description
        name = ctk.CTkLabel(
            content,
            text=mod_data.get("title") or mod_data.get("name", "Unknown Mod"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
            anchor="w"
        )
        name.grid(row=0, column=1, sticky="w")

        desc = mod_data.get("description", "")[:80]
        if len(mod_data.get("description", "")) > 80:
            desc += "..."

        desc_label = ctk.CTkLabel(
            content,
            text=desc,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"],
            anchor="w",
            wraplength=300
        )
        desc_label.grid(row=1, column=1, sticky="w")

        # Bottom info row
        info_frame = ctk.CTkFrame(content, fg_color="transparent")
        info_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        # Downloads count
        downloads = mod_data.get("downloads", 0)
        dl_text = self._format_downloads(downloads)

        dl_label = ctk.CTkLabel(
            info_frame,
            text=f"Downloads: {dl_text}",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"]
        )
        dl_label.pack(side="left")

        # Install button
        _ic_dl = _ico("download", (14, 14))
        _dl_kwargs: Dict[str, Any] = (
            {"image": _ic_dl, "compound": "left"} if _ic_dl else {}
        )
        self._install_btn = ctk.CTkButton(
            content,
            text="  Instalar" if _ic_dl else "Instalar",
            width=90,
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_dim"],
            text_color="#000000",
            command=self._handle_install,
            **_dl_kwargs,
        )
        self._install_btn.grid(row=0, column=2, rowspan=2, padx=(12, 0))

    def _format_downloads(self, count: int) -> str:
        # OPT-004: reutilizar mods.format_downloads si está disponible
        if _format_downloads is not None:
            return _format_downloads(count)
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            return f"{count / 1_000:.1f}K"
        return str(count)

    # FIX-E: _load_icon movido DENTRO de ModCard (antes estaba indentado dentro
    # de NewsCard por error — BUG-047). ModCard.start() llamaba self._load_icon()
    # pero el método no existía en ModCard → AttributeError garantizado.
    def _load_icon(self, url: str) -> None:
        """Descarga y muestra el ícono del mod desde una URL (se ejecuta en thread)."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CTK-Launcher/3.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            img = img.resize((50, 50), Image.LANCZOS)
            # Convertir RGBA a RGB con fondo oscuro
            bg = Image.new("RGB", img.size, (19, 19, 42))  # color panel_light
            bg.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
            ctk_img = ctk.CTkImage(bg, size=(50, 50))
            self._icon_ctk_image = ctk_img  # mantener referencia

            # FIX-I: try/except DENTRO de la lambda de after(), no fuera.
            # El try/except exterior solo captura errores al registrar el after,
            # no los que ocurren cuando la lambda ejecuta (widget ya destruido).
            def _update():
                try:
                    self._icon_label.configure(image=ctk_img, text="")
                    # FIX-SCROLL-2: CTkScrollableFrame usa un canvas interno.
                    # Cuando after() dispara durante un scroll, tkinter puede
                    # renderizar la imagen en la posicion Y original del canvas
                    # (sin offset de scroll), creando un ghost en posicion
                    # incorrecta. update_idletasks() fuerza al canvas a
                    # reconciliar la posicion real del widget con el offset
                    # actual del scroll antes de dibujar la imagen.
                    self._icon_container.update_idletasks()
                except Exception:
                    pass  # Widget destruido — ignorar
            self.after(0, _update)

        except Exception:
            pass  # Mantener 📦 como fallback en cualquier error

    def _handle_install(self):
        if self._installed or self._installing:
            return
        if self._on_install:
            self._installing = True
            self._install_btn.configure(text="Instalando...", state="disabled")
            self._on_install(self._mod, self)

    def set_installed(self):
        self._installed = True
        self._installing = False
        self._install_btn.configure(
            text="Instalado ✓",
            fg_color=COLORS["panel_light"],
            state="disabled"
        )


# ---------------------------------------------------------------------------
# NavButton
# ---------------------------------------------------------------------------

class NavButton(ctk.CTkButton):
    """
    Navigation button for the sidebar.
    Shows icon (CTkImage o emoji) y label con active/inactive states.
    Acepta ctk_image (CTkImage PNG) o icon (string emoji) — PNG tiene prioridad.
    """
    def __init__(
        self,
        master: Any,
        text: str,
        icon: str = "",
        ctk_image: Optional[ctk.CTkImage] = None,
        is_active: bool = False,
        command: Callable = None,
        **kwargs
    ):
        self._is_active = is_active
        self._ctk_image = ctk_image  # referencia para evitar GC

        fg = COLORS["accent_dim"] if is_active else "transparent"
        text_color = COLORS["accent"] if is_active else COLORS["text_dim"]
        hover = COLORS["panel_light"]

        # Si hay imagen PNG usar texto limpio; si no, prefijo emoji
        if ctk_image is not None:
            display_text = f"  {text}"
            img_kwargs: Dict[str, Any] = {"image": ctk_image, "compound": "left"}
        else:
            display_text = f"{icon}  {text}" if icon else text
            img_kwargs = {}

        super().__init__(
            master,
            text=display_text,
            command=command,
            font=ctk.CTkFont(size=13, weight="bold" if is_active else "normal"),
            fg_color=fg,
            hover_color=hover,
            text_color=text_color,
            anchor="w",
            height=40,
            corner_radius=8,
            **img_kwargs,
            **kwargs
        )

    def set_active(self, active: bool):
        self._is_active = active
        if active:
            self.configure(
                fg_color=COLORS["accent_dim"],
                text_color=COLORS["accent"],
                font=ctk.CTkFont(size=13, weight="bold")
            )
        else:
            self.configure(
                fg_color="transparent",
                text_color=COLORS["text_dim"],
                font=ctk.CTkFont(size=13, weight="normal")
            )


# ---------------------------------------------------------------------------
# DropdownSelector
# ---------------------------------------------------------------------------

class DropdownSelector(ctk.CTkFrame):
    """
    Custom dropdown/combobox with styled appearance.
    """
    def __init__(
        self,
        master: Any,
        values: List[str],
        default: str = None,
        on_change: Callable = None,
        width: int = 140,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._values = values
        self._on_change = on_change
        self._current = default or (values[0] if values else "")

        self._dropdown = ctk.CTkOptionMenu(
            self,
            values=values,
            command=self._handle_change,
            width=width,
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["panel_light"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_dim"],
            dropdown_fg_color=COLORS["panel"],
            dropdown_hover_color=COLORS["panel_light"],
            text_color=COLORS["text"],
            dropdown_text_color=COLORS["text"]
        )
        self._dropdown.pack()

        if default:
            self._dropdown.set(default)

    def _handle_change(self, value: str):
        self._current = value
        if self._on_change:
            self._on_change(value)

    def get(self) -> str:
        return self._current

    def set(self, value: str):
        if value in self._values:
            self._current = value
            self._dropdown.set(value)


# ---------------------------------------------------------------------------
# SearchBar
# ---------------------------------------------------------------------------

class SearchBar(ctk.CTkFrame):
    """
    Search input with icon and clear functionality.
    """
    def __init__(
        self,
        master: Any,
        placeholder: str = "Search...",
        on_search: Callable = None,
        width: int = 300,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._on_search = on_search

        container = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel_light"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=8
        )
        container.pack(fill="x")

        # Search icon label
        icon = ctk.CTkLabel(
            container,
            text="🔍",
            font=ctk.CTkFont(size=14),
            width=30
        )
        icon.pack(side="left", padx=(8, 0))

        # Input entry
        self._entry = ctk.CTkEntry(
            container,
            placeholder_text=placeholder,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            border_width=0,
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["text_dim"],
            width=width - 60
        )
        self._entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)

        # Search button
        self._search_btn = ctk.CTkButton(
            container,
            text="Search",
            width=60,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_dim"],
            text_color="#000000",
            corner_radius=6,
            command=self._do_search
        )
        self._search_btn.pack(side="right", padx=4, pady=4)

    def _do_search(self):
        if self._on_search:
            self._on_search(self._entry.get())

    def get(self) -> str:
        return self._entry.get()

    def clear(self):
        self._entry.delete(0, "end")


# ---------------------------------------------------------------------------
# ToggleSwitch
# ---------------------------------------------------------------------------

class ToggleSwitch(ctk.CTkFrame):
    """
    Toggle switch with label for boolean settings.
    """
    def __init__(
        self,
        master: Any,
        label: str,
        initial: bool = False,
        on_change: Callable = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._on_change = on_change

        # FIX-F: tk.BooleanVar debe recibir el tk.Tk raíz, NO un CTkFrame.
        # REGLA 3: BooleanVar(master=CTkFrame) → crash CTkFrame._root() en CTK 5.2.2.
        self._var = tk.BooleanVar(master=_find_root(master), value=initial)

        # Label
        lbl = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text"]
        )
        lbl.pack(side="left")

        # Switch
        self._switch = ctk.CTkSwitch(
            self,
            text="",
            variable=self._var,
            command=self._handle_change,
            onvalue=True,
            offvalue=False,
            fg_color=COLORS["panel_light"],
            progress_color=COLORS["accent"],
            button_color=COLORS["text"],
            button_hover_color=COLORS["accent"]
        )
        self._switch.pack(side="right")

    def _handle_change(self):
        if self._on_change:
            self._on_change(self._var.get())

    def get(self) -> bool:
        return self._var.get()

    def set(self, value: bool):
        self._var.set(value)


# ---------------------------------------------------------------------------
# SettingsCard
# ---------------------------------------------------------------------------

class SettingsCard(GlassFrame):
    """
    Card component for settings sections with icon and title.
    """
    def __init__(
        self,
        master: Any,
        title: str,
        description: str = "",
        icon: str = "⚙️",
        **kwargs
    ):
        super().__init__(master, **kwargs)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 8))

        # FIX: badge de ícono usa CTkFrame + CTkLabel para evitar bug fg_color.
        # REGLA 7: NO usar CTkLabel(fg_color=color_no_transparent) directamente.
        icon_frame = ctk.CTkFrame(
            header,
            fg_color=COLORS["accent_dim"],
            corner_radius=8,
            width=36,
            height=36,
        )
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(
            icon_frame,
            text=icon,
            font=ctk.CTkFont(size=20),
            fg_color="transparent",
        ).place(relx=0.5, rely=0.5, anchor="center")

        # Title and description
        text_frame = ctk.CTkFrame(header, fg_color="transparent")
        text_frame.pack(side="left", padx=(12, 0))

        title_label = ctk.CTkLabel(
            text_frame,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
            anchor="w"
        )
        title_label.pack(anchor="w")

        if description:
            desc_label = ctk.CTkLabel(
                text_frame,
                text=description,
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text_dim"],
                anchor="w"
            )
            desc_label.pack(anchor="w")

        # Content area
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=16, pady=(0, 16))
