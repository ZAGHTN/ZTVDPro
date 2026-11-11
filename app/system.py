"""Intégration avec le système (gestionnaire de fichiers)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def reveal_in_file_manager(path: str) -> bool:
    """Ouvre le dossier ; si `path` est un fichier, le sélectionne (Windows / macOS).

    Retourne False si l'ouverture a échoué.
    """
    p = Path(path)
    try:
        if p.is_file():
            if sys.platform == "win32":
                subprocess.Popen(["explorer", f"/select,{os.path.normpath(p)}"])
                return True
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(p)])
                return True
            p = p.parent  # Linux : pas de méthode universelle pour sélectionner un fichier
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
    except OSError:
        return False
