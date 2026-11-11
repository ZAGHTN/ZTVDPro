"""Journalisation de l'application (fichier rotatif + console)."""
from __future__ import annotations

import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "ZTVDPro"
LOG_FILE_NAME = "ztvd_pro.log"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 3


def default_log_dir() -> Path:
    """Dossier de logs inscriptible, indépendant du répertoire courant."""
    override = os.environ.get("ZTVD_LOG_DIR")
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "ZTVDPro" / "logs"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "ZTVDPro"
    else:
        base = os.environ.get("XDG_STATE_HOME")
        return (Path(base) if base else Path.home() / ".local" / "state") / "ztvdpro" / "logs"

    return Path(tempfile.gettempdir()) / "ZTVDPro" / "logs"


def _make_file_handler(path: Path) -> logging.Handler | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return RotatingFileHandler(
            path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        return None


def setup_logger(log_file: str | os.PathLike[str] | None = None) -> logging.Logger:
    """Configure le logger applicatif une seule fois.

    Le fichier est placé dans un dossier utilisateur inscriptible, jamais dans
    le répertoire courant : une version empaquetée lancée depuis un dossier
    protégé (Program Files, par exemple) ne peut donc pas planter au démarrage.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:  # évite les doublons en cas de rechargement du module
        return logger

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    path = Path(log_file).expanduser() if log_file else default_log_dir() / LOG_FILE_NAME
    handlers: list[logging.Handler] = []

    file_handler = _make_file_handler(path)
    if file_handler is None and log_file is None:
        # Dernier recours : le dossier temporaire est toujours inscriptible.
        file_handler = _make_file_handler(Path(tempfile.gettempdir()) / "ZTVDPro" / LOG_FILE_NAME)
    if file_handler is not None:
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        handlers.append(console)

    if not handlers:
        handlers.append(logging.NullHandler())

    for handler in handlers:
        logger.addHandler(handler)
    return logger


logger = setup_logger()
