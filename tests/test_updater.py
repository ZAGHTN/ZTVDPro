"""Tests de la comparaison de versions de yt-dlp."""
from app.updater import is_newer


def test_is_newer_compares_numeric_parts() -> None:
    assert is_newer("2026.11.1", "2026.10.26")
    assert is_newer("2026.10.26.1", "2026.10.26")
    assert not is_newer("2026.10.26", "2026.10.26")
    assert not is_newer("2026.9.30", "2026.10.26")
