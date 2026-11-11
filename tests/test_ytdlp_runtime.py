"""Tests de la surcharge utilisateur de yt-dlp (sans réseau ni Qt)."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

from app import ytdlp_runtime as runtime


def _make_wheel(
    path: Path,
    version: str,
    *,
    ejs: str | None = "0.8.0",
    metadata: str = "Metadata-Version: 2.1\n",
) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("yt_dlp/__init__.py", "")
        archive.writestr("yt_dlp/version.py", f"__version__ = '{version}'\n")
        archive.writestr(f"yt_dlp-{version}.dist-info/METADATA", metadata)
        if ejs is not None:
            archive.writestr("yt_dlp_ejs/__init__.py", "from ._version import version\n")
            archive.writestr("yt_dlp_ejs/_version.py", f"__version__ = version = '{ejs}'\n")
    return path


def test_version_comparison_is_numeric() -> None:
    assert runtime.is_newer("2026.11.01", "2026.10.26")
    assert not runtime.is_newer("2026.10.26", "2026.10.26")
    assert not runtime.is_newer("2026.9.30", "2026.10.26")
    assert runtime.is_newer("2026.10.26.1", "2026.10.26")


def test_read_version_supports_both_file_styles(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "version.py").write_text("__version__ = '2026.11.1'\n", encoding="utf-8")
    assert runtime._read_version(plain) == "2026.11.1"

    scm = tmp_path / "scm"
    scm.mkdir()
    (scm / "version.py").write_text("__version__ = version = '0.9.0'\n", encoding="utf-8")
    assert runtime._read_version(scm) == "0.9.0"

    assert runtime._read_version(tmp_path / "missing") is None


def test_install_from_wheels_creates_cache(tmp_path: Path) -> None:
    wheel = _make_wheel(tmp_path / "yt.whl", "2026.11.1")

    version = runtime.install_from_wheels([wheel], root=tmp_path / "cache")

    assert version == "2026.11.1"
    current = tmp_path / "cache" / "current"
    assert (current / "yt_dlp" / "__init__.py").is_file()
    assert (current / "yt_dlp" / "version.py").read_text(encoding="utf-8") == "__version__ = '2026.11.1'\n"
    assert (current / "yt_dlp_ejs" / "__init__.py").is_file()
    assert not (tmp_path / "cache" / "staging").exists()


def test_install_replaces_previous_version(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    runtime.install_from_wheels([_make_wheel(tmp_path / "v1.whl", "2026.10.1")], root=root)
    runtime.install_from_wheels([_make_wheel(tmp_path / "v2.whl", "2026.11.1")], root=root)

    assert runtime.cached_version(root) == "2026.11.1"
    assert not (root / "previous").exists()
    assert not (root / "staging").exists()


def test_install_keeps_previous_cache_on_invalid_wheel(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    runtime.install_from_wheels([_make_wheel(tmp_path / "v1.whl", "2026.10.1")], root=root)

    bad = tmp_path / "bad.whl"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("readme.txt", "rien")

    with pytest.raises(RuntimeError):
        runtime.install_from_wheels([bad], root=root)

    assert runtime.cached_version(root) == "2026.10.1"
    assert not (root / "staging").exists()


def test_install_rejects_path_traversal(tmp_path: Path) -> None:
    wheel = tmp_path / "evil.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("yt_dlp/__init__.py", "")
        archive.writestr("yt_dlp/../../evil.py", "boom")

    with pytest.raises(RuntimeError):
        runtime.install_from_wheels([wheel], root=tmp_path / "cache")


def test_ejs_requirement_is_read_from_wheel_metadata(tmp_path: Path) -> None:
    wheel = _make_wheel(
        tmp_path / "yt.whl",
        "2026.11.1",
        metadata=(
            "Metadata-Version: 2.1\n"
            "Provides-Extra: default\n"
            "Requires-Dist: yt-dlp-ejs==0.9.0; extra == 'default'\n"
        ),
    )

    assert runtime._ejs_requirement(wheel) == "0.9.0"


def test_pick_wheel_prefers_universal_wheel() -> None:
    metadata = {
        "info": {"version": "2026.11.1"},
        "urls": [
            {"packagetype": "sdist", "filename": "yt_dlp-2026.11.1.tar.gz",
             "digests": {"sha256": "sdist"}},
            {"packagetype": "bdist_wheel", "filename": "yt_dlp-2026.11.1-py3-none-any.whl",
             "url": "https://files/wheel.whl", "digests": {"sha256": "wheel"}},
        ],
    }

    assert runtime._pick_wheel(metadata) == ("https://files/wheel.whl", "wheel", "2026.11.1")


def test_pick_wheel_raises_without_universal_wheel() -> None:
    with pytest.raises(RuntimeError):
        runtime._pick_wheel({"info": {"version": "1.0"}, "urls": []})


def test_download_and_install_uses_pinned_ejs_version(monkeypatch, tmp_path: Path) -> None:
    asked: dict[str, str | None] = {}

    def fake_wheel_info(package: str, version: str | None = None):
        asked[package] = version
        return "https://files/x.whl", "sha", "2026.11.1"

    def fake_download(_url: str, destination: Path, _sha: str) -> None:
        destination.write_bytes(b"wheel")

    monkeypatch.setattr(runtime, "_wheel_info", fake_wheel_info)
    monkeypatch.setattr(runtime, "_download", fake_download)
    monkeypatch.setattr(runtime, "_ejs_requirement", lambda _wheel: "0.9.0")
    monkeypatch.setattr(runtime, "install_from_wheels", lambda _wheels: "2026.11.1")

    assert runtime.download_and_install() == "2026.11.1"
    assert asked == {"yt-dlp": None, "yt-dlp-ejs": "0.9.0"}


def test_cached_is_active_requires_frozen_and_newer(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "cache"
    runtime.install_from_wheels([_make_wheel(tmp_path / "v.whl", "2026.11.1")], root=root)
    monkeypatch.setattr(runtime, "bundled_version", lambda: "2026.10.26")

    monkeypatch.delattr(sys, "frozen", raising=False)
    assert not runtime.cached_is_active(root)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert runtime.cached_is_active(root)

    monkeypatch.setattr(runtime, "bundled_version", lambda: "2026.12.1")
    assert not runtime.cached_is_active(root)


def test_activate_cached_is_noop_outside_frozen_build(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert not runtime.activate_cached()


def test_revert_removes_user_cache(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    runtime.install_from_wheels([_make_wheel(tmp_path / "v.whl", "2026.11.1")], root=root)

    assert runtime.revert_to_bundled(root)
    assert not (root / "current").exists()
    assert not runtime.revert_to_bundled(root)
