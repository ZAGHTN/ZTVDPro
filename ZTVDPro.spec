# -*- mode: python ; coding: utf-8 -*-
"""Configuration PyInstaller de ZTVD Pro (build « onedir »).

Usage :
    .venv\\Scripts\\python.exe -m PyInstaller --noconfirm --clean ZTVDPro.spec

Le dossier produit ``dist\\ZTVDPro\\`` contient l'exécutable, ffmpeg/ffprobe,
le solveur EJS embarqué (paquet ``yt-dlp-ejs``) et, si disponible, Deno.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

PROJECT_ROOT = Path(SPECPATH).resolve()  # noqa: F821 - fourni par PyInstaller
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import deno_build_source  # noqa: E402

datas: list[tuple[str, str]] = []
binaries: list[tuple[str, str]] = []
hiddenimports: list[str] = []

# --- yt-dlp et son solveur EJS officiel -----------------------------------
# collect_all embarque les modules, les données (scripts JS vendus) et les
# imports cachés. yt-dlp-ejs est optionnel : s'il est absent, l'application
# retombe sur le téléchargement ejs:github déjà autorisé dans le code.
for package in ("yt_dlp", "yt_dlp_ejs"):
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    except Exception as exc:  # pragma: no cover - dépend de l'environnement de build
        if package == "yt_dlp_ejs":
            print(f"[spec] Paquet {package} introuvable ({exc}); repli sur ejs:github.")
            continue
        raise
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

# --- ffmpeg / ffprobe ------------------------------------------------------
# ffplay.exe n'est pas embarqué : inutile pour l'application et ~220 Mo.
ffmpeg_bin = PROJECT_ROOT / "src" / "ffmpeg" / "bin"
for exe in ("ffmpeg.exe", "ffprobe.exe"):
    source = ffmpeg_bin / exe
    if not source.is_file():
        raise SystemExit(
            f"[spec] Fichier manquant : {source}\n"
            "        Placez ffmpeg.exe et ffprobe.exe dans src\\ffmpeg\\bin."
        )
    binaries.append((str(source), "ffmpeg/bin"))

# --- icône de l'application -------------------------------------------------
assets_dir = PROJECT_ROOT / "assets"
icon_file = assets_dir / "icon.ico"
if icon_file.is_file():
    datas.append((str(assets_dir / "icon.png"), "assets"))
    print(f"[spec] Icône embarquée : {icon_file}")
else:
    print(f"[spec] Icône introuvable ({icon_file}) : icône par défaut.")

# --- Deno (optionnel) ------------------------------------------------------
# ZTVD_EMBED_DENO=0 (ou build.ps1 -NoDeno) désactive l'embarquement.
embed_deno = os.environ.get("ZTVD_EMBED_DENO", "1").strip().lower() not in (
    "0", "false", "no", "off",
)
if embed_deno:
    deno = deno_build_source(PROJECT_ROOT)
    if deno:
        binaries.append((deno, "deno"))
        print(f"[spec] Deno embarqué : {deno}")
    else:
        print("[spec] Deno introuvable (PATH, src\\deno) : il ne sera pas embarqué.")
else:
    print("[spec] Embarquement de Deno désactivé.")

analysis = Analysis(  # noqa: F821 - fourni par PyInstaller
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="ZTVDPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_file) if icon_file.is_file() else None,
)

collect = COLLECT(  # noqa: F821
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ZTVDPro",
)
