"""Tests du module de journalisation."""
from pathlib import Path

from app.logger import default_log_dir


def test_log_dir_can_be_overridden(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZTVD_LOG_DIR", str(tmp_path))
    assert default_log_dir() == tmp_path
