"""Accès aux ressources embarquées (icône, images)."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon


def resource_path(relative: str) -> Path:
    """Chemin d'une ressource, en source comme dans l'exécutable PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def app_icon() -> QIcon:
    """Icône de l'application (PNG multi-résolutions)."""
    return QIcon(str(resource_path("assets/icon.png")))
