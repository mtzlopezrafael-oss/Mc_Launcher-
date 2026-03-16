from __future__ import annotations

"""Vistas de página del launcher — cada vista es un CTkFrame autocontenido."""

from src.gui.views.home_view import HomeView
from src.gui.views.news_view import NewsView
from src.gui.views.log_view import LogView
from src.gui.views.settings_view import SettingsView
from src.gui.views.instance_detail_view import InstanceDetailView

__all__ = ["HomeView", "NewsView", "LogView", "SettingsView", "InstanceDetailView"]
