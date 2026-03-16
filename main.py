from __future__ import annotations

"""Entry point — parchea tkinter ANTES de importar customtkinter."""

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
# Garantiza que _root() siempre sea callable aunque CTkFrame lo sobreescriba
_orig_init = tk.BaseWidget.__init__
def _patched_init(self, master, widgetname, cnf=None, kw=None, extra=()):
    _orig_init(self, master, widgetname, cnf or {}, kw or {}, extra)
    # Proteger _root si fue sobreescrito por CTkFrame
    if not callable(self.__dict__.get('_root', self._root)):
        del self.__dict__['_root']
tk.BaseWidget.__init__ = _patched_init

# ──────────────────────────────────────────────────────────────────────────

from src.gui.main_window import MainWindow


def main() -> None:
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()