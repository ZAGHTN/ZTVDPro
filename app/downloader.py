"""Téléchargement via yt-dlp (API Python) dans un thread dédié."""
from __future__ import annotations

import logging
import os
import re
import shutil
import time
from typing import Any, cast
from urllib.parse import urlparse

from app.config import bundled_deno_path
from app.logger import logger

import yt_dlp
from PySide6.QtCore import QThread, Signal

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Domaines explicitement pris en charge par l'interface.
# Les sous-domaines (m.youtube.com, www.facebook.com, ...) sont acceptés.
SUPPORTED_DOMAINS: tuple[str, ...] = (
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "dailymotion.com",
)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# Solveur JavaScript officiel de yt-dlp pour les challenges « n » de YouTube.
# Sans ce composant, certains formats récents peuvent être absents. Le script
# est téléchargé depuis le dépôt officiel yt-dlp/ejs puis mis en cache.
REMOTE_COMPONENTS: tuple[str, ...] = ("ejs:github",)


def js_runtime_options() -> dict:
    """Configuration ``js_runtimes`` transmise à yt-dlp.

    Priorité : Deno embarqué (chemin explicite), Deno du ``PATH``, puis Node.js
    du ``PATH``. Sans runtime détecté, on laisse yt-dlp appliquer son défaut
    (Deno), qui signalera simplement l'absence de runtime.
    """
    runtimes: dict[str, dict] = {}

    bundled_deno = bundled_deno_path()
    if bundled_deno:
        runtimes["deno"] = {"path": bundled_deno}
    elif shutil.which("deno"):
        runtimes["deno"] = {}

    if shutil.which("node"):
        runtimes["node"] = {}

    return {"js_runtimes": runtimes} if runtimes else {}


def is_valid_url(url: str) -> bool:
    """Vérifie que l'URL est http(s) et appartient à un domaine supporté.

    Le hostname est comparé exactement (ou via un sous-domaine), jamais par
    simple recherche de sous-chaîne : ``https://evil.com/?x=youtube.com`` est
    donc rejeté.
    """
    url = (url or "").strip()
    if not url or any(ch.isspace() for ch in url) or "\\" in url:
        return False

    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        _ = parsed.port  # lève ValueError si le port est invalide
    except ValueError:
        return False

    if parsed.scheme.lower() not in ("http", "https") or not host:
        return False

    return any(host == domain or host.endswith(f".{domain}") for domain in SUPPORTED_DOMAINS)


class DownloaderError(Exception):
    """Exception de base pour le module downloader."""
    pass


class InvalidURLError(DownloaderError):
    """Exception levée lorsque l'URL est invalide."""
    pass


class FfmpegNotFoundError(DownloaderError):
    """Exception levée lorsque Ffmpeg est introuvable."""
    pass


def clean(text: object) -> str:
    return _ANSI.sub("", str(text)).strip()


def _is_webm_merge_failure(exc: Exception) -> bool:
    """Vrai si l'erreur ressemble à un échec de fusion/post-traitement WEBM.

    On évite ainsi de relancer tout le téléchargement après une erreur réseau
    ou une URL invalide, qui échouerait de la même façon en MKV.
    """
    text = clean(exc).lower()
    return "postprocessing" in text or "merge" in text or "webm" in text


class _Cancelled(Exception):
    pass


class _YdlLogger:
    """Adaptateur yt-dlp : journal fichier + remontée vers l'interface Qt."""

    def __init__(self, emit=None):
        self._emit = emit
        self._last_message: str | None = None

    def _send(self, level: int, msg: object) -> None:
        text = clean(msg)
        if not text:
            return
        logger.log(level, "yt-dlp: %s", text)
        if self._emit is None or text == self._last_message:
            return
        self._last_message = text
        self._emit(text)

    def debug(self, msg):
        self._send(logging.DEBUG, msg)

    def info(self, msg):
        self._send(logging.INFO, msg)

    def warning(self, msg):
        self._send(logging.WARNING, msg)

    def error(self, msg):
        self._send(logging.ERROR, msg)


def build_analysis_options(ffmpeg_location: str | None = None) -> dict:
    """Options yt-dlp pour une analyse, sans téléchargement.

    Passer ``ffmpeg_location`` évite le faux avertissement « ffmpeg not found »
    émis par yt-dlp pendant la sélection des formats.
    """
    opts: dict = {
        "noplaylist": True,
        "noprogress": True,
        "skip_download": True,
        "http_headers": {"User-Agent": _USER_AGENT},
        "remote_components": list(REMOTE_COMPONENTS),
    }
    opts.update(js_runtime_options())
    if ffmpeg_location:
        opts["ffmpeg_location"] = ffmpeg_location
    return opts


def build_options(out_dir: str, height: int, container: str, ffmpeg_location: str | None) -> dict:
    """Construit les options yt-dlp pour garantir la meilleure qualité image/son avec support multi-plateforme robuste."""
    opts: dict = {
        # dossier passé via « paths » : un « % » dans le chemin ne sera pas lu comme un champ de template
        "paths": {"home": out_dir},
        "outtmpl": "%(title).150B [%(id)s].%(ext)s",
        "noplaylist": True,
        "noprogress": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "postprocessors": [],
        # La clé racine « User-Agent » n'est pas lue par yt-dlp : les en-têtes
        # HTTP doivent être passés dans « http_headers ».
        "http_headers": {"User-Agent": _USER_AGENT},
        "remote_components": list(REMOTE_COMPONENTS),
    }
    opts.update(js_runtime_options())
    if ffmpeg_location:
        opts["ffmpeg_location"] = ffmpeg_location

    if container == "mp3":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] += [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
            {"key": "FFmpegMetadata", "add_metadata": True},
        ]
        return opts

    # Format robuste avec repli pour les sites sans flux séparés (Pexels, Pixabay, Dailymotion)
    if height:
        opts["format"] = f"bv*[height<={height}]+ba/b[height<={height}]/best[height<={height}]/bv*+ba/b/best"
    else:
        opts["format"] = "bv*+ba/b/best"

    opts["merge_output_format"] = container

    if container == "webm":
        opts["format_sort"] = ["res", "vcodec:vp9", "acodec:opus"]
    elif container == "mkv":
        opts["format_sort"] = ["res"]
    else:  # mp4, mov, avi : privilégier H.264 + AAC (compatibilité maximale)
        opts["format_sort"] = ["res", "vcodec:h264", "acodec:m4a"]

    if container == "avi":
        opts["postprocessors"].append({"key": "FFmpegVideoConvertor", "preferedformat": "avi"})
    elif container in ("mov", "mp4", "mkv"):  # remux sans ré-encodage (fichier déjà fusionné)
        opts["postprocessors"].append({"key": "FFmpegVideoRemuxer", "preferedformat": container})
    opts["postprocessors"].append({"key": "FFmpegMetadata", "add_metadata": True})
    return opts


class DownloadWorker(QThread):
    progress = Signal(object)      # dict : percent, speed, eta, done, total, stream, file
    step = Signal(str, object)     # (clé de traduction, dict de paramètres)
    log = Signal(str)              # sortie brute de yt-dlp
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    paused = Signal()              # transfert interrompu, données partielles conservées

    def __init__(self, url, out_dir, height, container, ffmpeg_location, parent=None):
        super().__init__(parent)
        self.url, self.out_dir = url, out_dir
        self.height, self.container, self.ffmpeg_location = height, container, ffmpeg_location
        self._cancel = False
        self._pause = False
        self._stream_idx = 0
        self._current_file = None
        self._last_emit = 0.0
        self._last_pp_event: tuple[str, str] | None = None

    def cancel(self) -> None:
        self._cancel = True

    def pause(self) -> None:
        """Interrompt le transfert ; les fichiers .part sont conservés pour la reprise."""
        self._pause = True

    # -- hooks yt-dlp ---------------------------------------------------------
    def _progress_hook(self, d: dict) -> None:
        if self._cancel or self._pause:
            raise _Cancelled()
        name = os.path.basename(d.get("filename") or "")
        status = d.get("status")
        if status == "downloading":
            if name != self._current_file:
                self._current_file = name
                self._stream_idx += 1
                self.step.emit("step_stream_start", {"n": self._stream_idx, "file": name})
            now = time.monotonic()
            if now - self._last_emit < 0.1:
                return
            self._last_emit = now
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            self.progress.emit({
                "percent": (done / total * 100) if total else 0.0,
                "speed": d.get("speed") or 0, "eta": d.get("eta"),
                "done": done, "total": total, "stream": self._stream_idx, "file": name,
                "title": (d.get("info_dict") or {}).get("title") or name,
            })
        elif status == "finished":
            self.step.emit("step_stream_done", {"file": name})

    def _pp_hook(self, d: dict) -> None:
        if self._cancel:
            raise _Cancelled()
        key = {"started": "step_pp_start", "finished": "step_pp_done"}.get(str(d.get("status")))
        if key:
            event = (key, d.get("postprocessor", "?"))
            if event == self._last_pp_event:  # yt-dlp peut appeler le hook deux fois
                return
            self._last_pp_event = event
            self.step.emit(key, {"name": event[1]})

    # -- thread ---------------------------------------------------------------
    def _run_once(self, container: str) -> str:
        """Exécute un téléchargement complet et retourne le chemin produit."""
        opts = build_options(self.out_dir, self.height, container, self.ffmpeg_location)
        opts.update({
            "logger": _YdlLogger(self.log.emit),
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._pp_hook],
        })
        with yt_dlp.YoutubeDL(cast(Any, opts)) as ydl:
            info = ydl.extract_info(self.url, download=True)
            if not info:
                return ""
            downloads = info.get("requested_downloads") or []
            path = downloads[0].get("filepath") if downloads else None
            return path or ydl.prepare_filename(info)

    def run(self) -> None:
        try:
            self.step.emit("step_start", {"url": self.url})
            try:
                path = self._run_once(self.container)
            except Exception as exc:
                # Un site peut refuser le conteneur WEBM (pas de VP9/AV1 + Opus).
                # MKV accepte quasiment tous les codecs : un seul nouvel essai.
                if (self.container != "webm" or self._cancel or self._pause
                        or isinstance(exc, _Cancelled) or not _is_webm_merge_failure(exc)):
                    raise
                logger.warning("Échec du téléchargement WEBM (%s) ; nouvel essai en MKV", clean(exc))
                self.step.emit("step_fallback_mkv", {})
                self._stream_idx = 0
                self._current_file = None
                path = self._run_once("mkv")
            self.succeeded.emit(path)
        except Exception as exc:
            if self._cancel:
                self.cancelled.emit()
            elif self._pause:
                self.paused.emit()
            elif isinstance(exc, _Cancelled):
                self.cancelled.emit()
            else:
                self.failed.emit(clean(exc))


def summarize_info(info: Any) -> dict:
    """Extrait de l'info yt-dlp les éléments utiles à l'interface."""
    if info.get("_type") == "playlist":
        first = next((e for e in (info.get("entries") or []) if e), None)
        if first:
            info = first
    heights = [int(f["height"]) for f in (info.get("formats") or [])
               if f.get("height") and f.get("vcodec") != "none"]
    return {
        "title": info.get("title") or "",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "duration": info.get("duration"),
        "max_height": max(heights) if heights else 0,
        "extractor": info.get("extractor_key") or info.get("extractor") or "",
        "is_live": bool(info.get("is_live")),
    }


class AnalyzeWorker(QThread):
    """Analyse une URL (sans rien télécharger) et remonte les étapes de yt-dlp."""

    log = Signal(str)
    analyzed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, url: str, ffmpeg_location: str | None = None, parent=None):
        super().__init__(parent)
        self.url = url
        self.ffmpeg_location = ffmpeg_location
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def _on_log(self, msg: str) -> None:
        if self._cancel:
            raise _Cancelled()  # interrompt l'extraction au prochain message de yt-dlp
        self.log.emit(msg)

    def run(self) -> None:
        opts = build_analysis_options(self.ffmpeg_location)
        opts["logger"] = _YdlLogger(self._on_log)
        try:
            with yt_dlp.YoutubeDL(cast(Any, opts)) as ydl:
                info = ydl.extract_info(self.url, download=False)
                data = ydl.sanitize_info(info) if info else {}
            if self._cancel:
                self.cancelled.emit()
            else:
                self.analyzed.emit(summarize_info(data))
        except Exception as exc:
            if self._cancel or isinstance(exc, _Cancelled):
                self.cancelled.emit()
            else:
                self.failed.emit(clean(exc))
