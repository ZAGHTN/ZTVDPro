"""Surcharge de ``yt-dlp`` dans un dossier utilisateur (version compilée).

La version compilée embarque ``yt-dlp`` en lecture seule. Pour la garder à jour
sans réinstaller l'application, on télécharge les wheels officielles depuis PyPI,
on les extrait dans ``%LOCALAPPDATA%\\ZTVDPro\\ytdlp\\current`` puis on place ce
dossier en tête de ``sys.path`` au démarrage suivant. La version intégrée reste
utilisée si le cache est absent, plus ancien ou invalide.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Iterable

from .logger import logger

PYPI_BASE = "https://pypi.org/pypi"
USER_AGENT = "ZTVDPro"
_PACKAGE_TOPS = ("yt_dlp", "yt_dlp_ejs")
_VERSION_RE = re.compile(r"^__version__\s*=\s*(?:version\s*=\s*)?['\"]([^'\"]+)['\"]", re.MULTILINE)


# --------------------------------------------------------------------- chemins
def cache_root() -> Path:
    """Dossier inscriptible qui reçoit la surcharge de yt-dlp."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "ZTVDPro" / "ytdlp"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ZTVDPro" / "ytdlp"
    else:
        base = os.environ.get("XDG_CACHE_HOME")
        return (Path(base) if base else Path.home() / ".cache") / "ZTVDPro" / "ytdlp"
    return Path(tempfile.gettempdir()) / "ZTVDPro" / "ytdlp"


def current_dir(root: Path | None = None) -> Path:
    """Paquet actif du cache (``<cache>/current``)."""
    return (root or cache_root()) / "current"


# --------------------------------------------------------------------- versions
def version_tuple(version: str) -> tuple[int, ...]:
    parts = []
    for part in version.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if digits:
            parts.append(int(digits))
        else:
            parts.append(0)
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    try:
        return version_tuple(latest) > version_tuple(current)
    except Exception:  # noqa: BLE001 - comparaison de secours
        return latest != current


def _read_version(package_dir: Path) -> str | None:
    """Lit ``__version__`` dans ``<package_dir>/version.py`` (yt-dlp)."""
    path = package_dir / "version.py"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def bundled_version() -> str | None:
    """Version de yt-dlp intégrée à l'application compilée."""
    root = getattr(sys, "_MEIPASS", None)
    return _read_version(Path(root) / "yt_dlp") if root else None


def cached_version(root: Path | None = None) -> str | None:
    """Version de yt-dlp présente dans le cache utilisateur."""
    return _read_version(current_dir(root) / "yt_dlp")


def cached_is_active(root: Path | None = None) -> bool:
    """Vrai si le cache contient une version plus récente que celle intégrée."""
    if not getattr(sys, "frozen", False):
        return False
    cached, bundled = cached_version(root), bundled_version()
    if not cached or not bundled:
        return False
    return is_newer(cached, bundled)


# ------------------------------------------------------------------- activation
def _purge_modules() -> None:
    for name in [n for n in sys.modules if n in _PACKAGE_TOPS or n.split(".", 1)[0] in _PACKAGE_TOPS]:
        sys.modules.pop(name, None)


def _drop_sys_path(path: Path) -> None:
    target = str(path)
    while target in sys.path:
        sys.path.remove(target)


def activate_cached() -> bool:
    """Active la surcharge utilisateur avant le premier import de ``yt_dlp``.

    Doit être appelée au tout début de ``main()``, avant ``app.main_window``.
    En cas d'échec (paquet incomplet, import cassé), on revient proprement à la
    version intégrée.
    """
    if not getattr(sys, "frozen", False):
        return False
    if not cached_is_active():
        return False

    root = current_dir()
    sys.path.insert(0, str(root))
    try:
        import yt_dlp
        import yt_dlp.version as yt_dlp_version

        module_path = Path(yt_dlp.__file__).resolve()
        if root.resolve() not in module_path.parents:
            raise RuntimeError("le paquet intégré a été chargé au lieu du cache")
        loaded = str(yt_dlp_version.__version__)
        if not is_newer(loaded, bundled_version() or "0"):
            raise RuntimeError(f"version en cache trop ancienne ({loaded})")
    except Exception as exc:  # noqa: BLE001 - on ne bloque jamais le démarrage
        logger.warning("Surcharge yt-dlp ignorée (%s) ; retour à la version intégrée.", exc)
        _drop_sys_path(root)
        _purge_modules()
        return False

    logger.info("yt-dlp %s chargé depuis %s (version intégrée : %s)", loaded, root, bundled_version())
    return True


# -------------------------------------------------------------------- téléchargement
def _fetch_json(url: str, timeout: float = 20.0) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _pick_wheel(metadata: dict) -> tuple[str, str, str]:
    """Retourne ``(url, sha256, version)`` de la wheel py3-none-any de PyPI."""
    version = str(metadata["info"]["version"])
    for file in metadata.get("urls") or []:
        filename = str(file.get("filename") or "")
        if file.get("packagetype") != "bdist_wheel":
            continue
        if not filename.endswith("-py3-none-any.whl"):
            continue
        sha256 = str((file.get("digests") or {}).get("sha256") or "")
        if not sha256:
            break
        return str(file["url"]), sha256, version
    raise RuntimeError(f"Aucune wheel py3-none-any publiée pour la version {version}.")


def _wheel_info(package: str, version: str | None = None) -> tuple[str, str, str]:
    suffix = f"/{version}" if version else ""
    metadata = _fetch_json(f"{PYPI_BASE}/{package}{suffix}/json")
    return _pick_wheel(metadata)


def _download(url: str, destination: Path, sha256: str) -> None:
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as handle:
        while chunk := response.read(1 << 16):
            digest.update(chunk)
            handle.write(chunk)
    actual = digest.hexdigest()
    if actual != sha256:
        destination.unlink(missing_ok=True)
        raise RuntimeError("Empreinte SHA-256 invalide : téléchargement interrompu.")


def _ejs_requirement(wheel: Path) -> str | None:
    """Lit la version épinglée de ``yt-dlp-ejs`` dans la wheel de yt-dlp."""
    try:
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if name.endswith(".dist-info/METADATA"):
                    text = archive.read(name).decode("utf-8", "replace")
                    match = re.search(r"^Requires-Dist:\s*yt-dlp-ejs==([^\s;]+)", text, re.MULTILINE)
                    if match:
                        return match.group(1)
    except (OSError, zipfile.BadZipFile):
        logger.warning("Impossible de lire les métadonnées de %s.", wheel)
    return None


def _safe_extract(wheel: Path, destination: Path) -> None:
    """Extrait uniquement les paquets ``yt_dlp``/``yt_dlp_ejs`` de la wheel."""
    root = destination.resolve()
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/"):
                continue
            parts = Path(name).parts
            if name.startswith("/") or ".." in parts:
                raise RuntimeError(f"Chemin non sûr dans la wheel : {info.filename}")
            top = name.split("/", 1)[0]
            if top not in _PACKAGE_TOPS:
                continue
            target = (destination / name).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"Chemin non sûr dans la wheel : {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)


def install_from_wheels(wheels: Iterable[Path], root: Path | None = None) -> str:
    """Installe des wheels déjà téléchargées et retourne la version installée.

    L'opération est atomique du point de vue de l'application : le dossier
    ``current`` précédent n'est supprimé qu'après la bascule réussie.
    """
    base = root or cache_root()
    base.mkdir(parents=True, exist_ok=True)
    staging = base / "staging"
    backup = base / "previous"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()

    try:
        for wheel in wheels:
            _safe_extract(Path(wheel), staging)
        version = _read_version(staging / "yt_dlp")
        if not version:
            raise RuntimeError("La wheel ne contient pas de paquet yt_dlp valide.")
        if not (staging / "yt_dlp" / "__init__.py").is_file():
            raise RuntimeError("Le paquet yt_dlp extrait est incomplet.")
        if not (staging / "yt_dlp_ejs" / "__init__.py").is_file():
            logger.warning("La surcharge ne contient pas yt-dlp-ejs : le solveur intégré sera utilisé.")

        current = base / "current"
        shutil.rmtree(backup, ignore_errors=True)
        if current.exists():
            current.rename(backup)
        try:
            staging.rename(current)
        except OSError:
            if backup.exists() and not current.exists():
                backup.rename(current)
            raise
        shutil.rmtree(backup, ignore_errors=True)
        return version
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def download_and_install(progress: Callable[[str], None] | None = None) -> str:
    """Télécharge la dernière version de yt-dlp (+ ejs épinglé) et l'installe.

    Retourne la version installée. Lève ``RuntimeError`` avec un message lisible
    en cas de problème réseau, d'empreinte invalide ou de wheel inattendue.
    """
    report = progress or (lambda _message: None)
    work = Path(tempfile.mkdtemp(prefix="ztvd-ytdlp-"))
    try:
        report("Téléchargement de yt-dlp…")
        url, sha256, _version = _wheel_info("yt-dlp")
        ytdlp_wheel = work / "yt-dlp.whl"
        _download(url, ytdlp_wheel, sha256)

        ejs_version = _ejs_requirement(ytdlp_wheel)
        report("Téléchargement du solveur yt-dlp-ejs…")
        ejs_url, ejs_sha256, _ejs_actual = _wheel_info("yt-dlp-ejs", ejs_version)
        ejs_wheel = work / "yt-dlp-ejs.whl"
        _download(ejs_url, ejs_wheel, ejs_sha256)

        report("Installation…")
        return install_from_wheels((ytdlp_wheel, ejs_wheel))
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ------------------------------------------------------------------------ retour
def revert_to_bundled(root: Path | None = None) -> bool:
    """Supprime la surcharge utilisateur ; la version intégrée reprend au redémarrage."""
    current = current_dir(root)
    if not current.exists():
        return False
    shutil.rmtree(current)
    return True
