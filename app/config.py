"""Constantes et utilitaires de configuration."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# (libellé affiché, hauteur max en pixels ; 0 = meilleure qualité disponible)
QUALITIES: list[tuple[str, int]] = [
    ("best", 0),
    ("8K (4320p)", 4320),
    ("4K (2160p)", 2160),
    ("1440p (2K)", 1440),
    ("1080p (Full HD)", 1080),
    ("720p (HD)", 720),
    ("480p (SD)", 480),
    ("360p (SD)", 360),
    ("240p (SD)", 240),
    ("144p (SD)", 144),
]

# (libellé affiché, identifiant du conteneur)
FORMATS: list[tuple[str, str]] = [
    ("MP4", "mp4"),
    ("MKV", "mkv"),
    ("WEBM", "webm"),
    ("MOV", "mov"),
    ("AVI", "avi"),
    ("MP3 (audio)", "mp3"),
]


def _exe(name: str) -> str:
    return name + (".exe" if os.name == "nt" else "")


def default_output_dir() -> str:
    home = Path.home()
    for name in ("Videos", "Downloads"):
        candidate = home / name
        if candidate.is_dir():
            return str(candidate)
    return str(home)


def bundled_ffmpeg_dir() -> str | None:
    """Dossier du ffmpeg embarqué (build PyInstaller, ou src/ffmpeg/bin en développement)."""
    roots = []
    if getattr(sys, "frozen", False):
        roots.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)))
        roots.append(Path(sys.executable).parent)
    roots.append(Path(__file__).resolve().parent.parent)
    for root in roots:
        for sub in (("ffmpeg", "bin"), ("src", "ffmpeg", "bin")):
            candidate = root.joinpath(*sub)
            if (candidate / _exe("ffmpeg")).is_file() and (candidate / _exe("ffprobe")).is_file():
                return str(candidate)
    return None


def deno_build_source(project_root: str | Path) -> str | None:
    """Deno à embarquer lors de la compilation.

    Priorité au Deno installé dans le ``PATH``, puis à un binaire déposé
    manuellement dans ``src/deno/deno.exe`` (ou ``src/deno/bin/deno.exe``).
    Cela permet de compiler sans installer Deno.
    """
    found = shutil.which("deno")
    if found:
        return found

    root = Path(project_root)
    for sub in (("src", "deno"), ("src", "deno", "bin")):
        candidate = root.joinpath(*sub, _exe("deno"))
        if candidate.is_file():
            return str(candidate)
    return None


def bundled_deno_path() -> str | None:
    """Chemin du Deno embarqué (build PyInstaller) ou placé dans ``src/deno``.

    L'application l'utilise pour configurer ``js_runtimes`` de yt-dlp, afin que
    le runtime fourni avec l'exécutable soit trouvé même s'il n'est pas dans le
    ``PATH`` de l'utilisateur.
    """
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)))
        roots.append(Path(sys.executable).parent)
    roots.append(Path(__file__).resolve().parent.parent)

    for root in roots:
        for sub in ((), ("deno",), ("deno", "bin"), ("src", "deno"), ("src", "deno", "bin")):
            candidate = root.joinpath(*sub, _exe("deno"))
            if candidate.is_file():
                return str(candidate)
    return None


def check_ffmpeg(folder: str) -> tuple[bool, str | None]:
    """Retourne (ffmpeg_disponible, emplacement_a_donner_a_yt_dlp).

    - dossier renseigné : on cherche ffmpeg dedans (ou dans son sous-dossier bin/)
    - dossier vide : ffmpeg embarqué, sinon ffmpeg du PATH système
    """
    folder = (folder or "").strip()
    if folder:
        p = Path(folder).expanduser()
        if p.is_file():
            if p.name.lower().startswith("ffmpeg"):
                return True, str(p)
            return False, None
        for candidate in (p / _exe("ffmpeg"), p / "bin" / _exe("ffmpeg")):
            if candidate.is_file():
                return True, str(candidate.parent)
        return False, None
    bundled = bundled_ffmpeg_dir()
    if bundled:
        return True, bundled
    return shutil.which("ffmpeg") is not None, None
