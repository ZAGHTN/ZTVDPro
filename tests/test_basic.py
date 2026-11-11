"""Tests unitaires pour app/config.py et app/i18n.py."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from app.config import (
    FORMATS,
    QUALITIES,
    bundled_deno_path,
    check_ffmpeg,
    deno_build_source,
)
from app.i18n import TRANSLATIONS, current_language, is_rtl, set_language, tr


def test_qualities_and_formats() -> None:
    assert QUALITIES[0] == ("best", 0)
    assert any(label == "1080p (Full HD)" for label, _ in QUALITIES)
    assert [value for _, value in FORMATS] == ["mp4", "mkv", "webm", "mov", "avi", "mp3"]


def test_i18n_basic() -> None:
    try:
        set_language("fr")
        assert current_language() == "fr"
        assert not is_rtl()
        assert tr("btn_download") == "Télécharger"

        set_language("ar")
        assert current_language() == "ar"
        assert is_rtl()
        assert tr("btn_download") == "تحميل"

        set_language("xx")
        assert current_language() == "en"
        assert tr("btn_download") == "Download"
    finally:
        set_language("en")


def test_translations_have_same_keys() -> None:
    english = set(TRANSLATIONS["en"])
    assert set(TRANSLATIONS["fr"]) == english
    assert set(TRANSLATIONS["ar"]) == english


def test_translation_formatting() -> None:
    set_language("en")
    assert tr("status_downloading", file="video.mp4") == "Downloading… video.mp4"


def test_ffmpeg_check_empty_folder() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ok, location = check_ffmpeg(tmp)
    assert ok is False
    assert location is None


def test_ffmpeg_check_invalid_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "not-ffmpeg.txt"
        fake.write_text("x", encoding="utf-8")
        ok, location = check_ffmpeg(str(fake))
    assert ok is False
    assert location is None


def test_bundled_deno_path_finds_packaged_runtime(monkeypatch, tmp_path) -> None:
    deno_dir = tmp_path / "deno"
    deno_dir.mkdir()
    deno = deno_dir / ("deno.exe" if os.name == "nt" else "deno")
    deno.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert bundled_deno_path() == str(deno)


def test_bundled_deno_path_finds_runtime_next_to_executable(monkeypatch, tmp_path) -> None:
    deno = tmp_path / ("deno.exe" if os.name == "nt" else "deno")
    deno.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert bundled_deno_path() == str(deno)


def test_bundled_deno_path_absent_in_development(monkeypatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    assert bundled_deno_path() is None


def test_deno_build_source_prefers_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.config.shutil.which",
        lambda name: r"C:\deno\deno.exe" if name == "deno" else None,
    )

    assert deno_build_source(tmp_path) == r"C:\deno\deno.exe"


def test_deno_build_source_falls_back_to_src_deno(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.config.shutil.which", lambda name: None)
    deno = tmp_path / "src" / "deno" / ("deno.exe" if os.name == "nt" else "deno")
    deno.parent.mkdir(parents=True)
    deno.write_text("", encoding="utf-8")

    assert deno_build_source(tmp_path) == str(deno)


def test_deno_build_source_absent(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.config.shutil.which", lambda name: None)

    assert deno_build_source(tmp_path) is None
