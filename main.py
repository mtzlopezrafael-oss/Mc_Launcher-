from __future__ import annotations

"""Entry point — parchea tkinter ANTES de importar customtkinter."""

import sys
import threading
import traceback
import tkinter as tk
from pathlib import Path

# ── Patch 1: nametowidget ──────────────────────────────────────────────────
_orig_nametowidget = tk.Misc.nametowidget
def _safe_nametowidget(self, name):
    try:
        return _orig_nametowidget(self, name)
    except TypeError:
        return self
tk.Misc.nametowidget = _safe_nametowidget

# ── Patch 2: _report_exception ─────────────────────────────────────────────
_orig_report = tk.Misc._report_exception
def _safe_report(self):
    try:
        return _orig_report(self)
    except TypeError:
        pass
tk.Misc._report_exception = _safe_report

# ── Patch 3: _root en BaseWidget ───────────────────────────────────────────
_orig_init = tk.BaseWidget.__init__
def _patched_init(self, master, widgetname, cnf=None, kw=None, extra=()):
    _orig_init(self, master, widgetname, cnf or {}, kw or {}, extra)
    if not callable(self.__dict__.get('_root', self._root)):
        del self.__dict__['_root']
tk.BaseWidget.__init__ = _patched_init

# ──────────────────────────────────────────────────────────────────────────
# Logging — se inicializa ANTES de importar cualquier módulo del launcher
# ──────────────────────────────────────────────────────────────────────────
from src.utils.config import LAUNCHER_DIR, LAUNCHER_VERSION
from src.utils.logger import setup_logging, get_logger, get_log_file

LOG_DIR  = LAUNCHER_DIR / "logs"
LOG_FILE = setup_logging(version=LAUNCHER_VERSION, log_dir=LOG_DIR)

_log = get_logger("launcher.main")


# ── Crash handler — muestra diálogo y escribe al log ───────────────────────

def _show_crash_dialog(exc_type, exc_value, exc_tb) -> None:
    """
    Muestra un diálogo de error nativo cuando ocurre una excepción no capturada.
    Usa tkinter puro (sin CTK) para funcionar incluso si el launcher no arrancó.
    """
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log_path = get_log_file()
    log_info = str(log_path) if log_path else "No disponible"

    try:
        root = tk.Tk()
        root.withdraw()   # Ocultar ventana principal vacía

        msg = (
            f"El launcher encontró un error inesperado y no puede continuar.\n\n"
            f"El error ha sido guardado en el archivo de log:\n"
            f"  {log_info}\n\n"
            f"Puedes enviar ese archivo para recibir soporte.\n\n"
            f"Detalle técnico:\n{exc_type.__name__}: {exc_value}"
        )
        import tkinter.messagebox as mb
        mb.showerror(
            title="MC Launcher — Error inesperado",
            message=msg,
            parent=None,
        )
        root.destroy()
    except Exception:
        pass   # Si el diálogo falla, al menos el log ya fue escrito


def _handle_exception(exc_type, exc_value, exc_tb) -> None:
    """sys.excepthook — excepción no capturada en hilo principal."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _log.critical(
        "Excepción no capturada en hilo principal",
        exc_info=(exc_type, exc_value, exc_tb),
    )
    _show_crash_dialog(exc_type, exc_value, exc_tb)


def _handle_thread_exception(args) -> None:
    """threading.excepthook — excepción no capturada en hilo secundario."""
    if args.exc_type is None or issubclass(args.exc_type, SystemExit):
        return
    _log.critical(
        f"Excepción no capturada en hilo '{args.thread.name}'",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
    _show_crash_dialog(args.exc_type, args.exc_value, args.exc_traceback)


# Registrar ambos hooks globales
sys.excepthook          = _handle_exception
threading.excepthook    = _handle_thread_exception   # Python 3.8+

# ──────────────────────────────────────────────────────────────────────────

from src.gui.main_window import MainWindow


def main() -> None:
    _log.info("Iniciando ventana principal")
    try:
        app = MainWindow()
        app.mainloop()
        _log.info("Launcher cerrado normalmente")
    except Exception:
        _log.critical("Fallo fatal al iniciar MainWindow", exc_info=True)
        raise


if __name__ == "__main__":
    main()
