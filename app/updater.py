"""Mise à jour de yt-dlp (vérification PyPI + pip)."""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request

from PySide6.QtCore import QThread, Signal

PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"


def installed_version() -> str:
    try:
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return "?"


def _parse(version: str) -> tuple[int, ...]:
    parts = []
    for p in version.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    try:
        return _parse(latest) > _parse(current)
    except Exception:
        return latest != current


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


class UpdateWorker(QThread):
    """mode='check'   -> check_done(latest) | error(msg)
       mode='upgrade' -> upgrade_done(latest) | error(msg)"""

    mode: str
    check_done = Signal(str)
    upgrade_done = Signal(str)
    error = Signal(str)

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode

    @staticmethod
    def fetch_latest() -> str:
        req = urllib.request.Request(PYPI_URL, headers={"User-Agent": "ZTVDPro"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)["info"]["version"]

    def run(self) -> None:
        try:
            if self.mode == "check":
                self.check_done.emit(self.fetch_latest())
                return
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                capture_output=True, text=True, timeout=900, **kwargs,
            )
            if proc.returncode != 0:
                self.error.emit((proc.stderr or proc.stdout or "pip error").strip()[-1500:])
                return
            self.upgrade_done.emit(self.fetch_latest())
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class InstallWorker(UpdateWorker):
    """Installe une version récente de yt-dlp dans le cache utilisateur.

    Utilisé dans la version compilée : ``pip`` n'y est pas disponible, on
    télécharge donc les wheels PyPI dans ``%LOCALAPPDATA%``.
    """

    def __init__(self, parent=None):
        super().__init__("upgrade", parent)

    def run(self) -> None:
        try:
            from .ytdlp_runtime import download_and_install

            self.upgrade_done.emit(download_and_install())
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
