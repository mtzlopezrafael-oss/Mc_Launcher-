"""Entry point — parchea tkinter ANTES de importar customtkinter."""

from __future__ import annotations

import sys
import threading
import tkinter as tk

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


_app = None   # MainWindow activa (para avisar de errores en hilos)


def _handle_thread_exception(args) -> None:
    """threading.excepthook — excepción no capturada en hilo secundario."""
    if args.exc_type is None or issubclass(args.exc_type, SystemExit):
        return
    thread_name = args.thread.name if args.thread else "?"
    _log.critical(
        f"Excepción no capturada en hilo '{thread_name}'",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
    # Un error en un hilo de fondo no tumba el launcher: avisar en la consola
    # de la app. NO crear un tk.Tk() desde este hilo (Tk no es thread-safe).
    if _app is not None:
        try:
            _app.log(f"Error interno ({args.exc_type.__name__}: {args.exc_value}). "
                     "Detalles en el archivo de log.", "error")
        except Exception:
            pass


def _handle_tk_callback_exception(self, exc_type, exc_value, exc_tb) -> None:
    """
    Tk.report_callback_exception — errores dentro de callbacks de botones,
    after(), etc. Por defecto Tk los imprime en stderr, que en el EXE
    (console=False) no existe: se perdían sin dejar rastro.
    """
    _log.error("Excepción en callback de Tk",
               exc_info=(exc_type, exc_value, exc_tb))
    try:
        self.log(f"Error: {exc_type.__name__}: {exc_value}", "error")
    except Exception:
        pass


# Registrar los hooks globales
sys.excepthook          = _handle_exception
threading.excepthook    = _handle_thread_exception   # Python 3.8+
tk.Tk.report_callback_exception = _handle_tk_callback_exception

# ──────────────────────────────────────────────────────────────────────────

from src.gui.main_window import MainWindow


def main() -> None:
    global _app
    _log.info("Iniciando ventana principal")
    try:
        app = MainWindow()
        _app = app
        app.mainloop()
        _log.info("Launcher cerrado normalmente")
    except Exception:
        _log.critical("Fallo fatal al iniciar MainWindow", exc_info=True)
        raise


if __name__ == "__main__":
    main()
