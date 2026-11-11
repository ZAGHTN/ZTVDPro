"""Tests de l'état de l'interface et de la lecture des réglages."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app import i18n
from app.config import FORMATS, QUALITIES
from app.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def window(qapp: QApplication, tmp_path: Path):
    settings = QSettings(str(tmp_path / "ztvd.ini"), QSettings.Format.IniFormat)
    settings.setValue("auto_update", "false")
    settings.sync()
    win = MainWindow(settings)
    try:
        yield win
    finally:
        win.close()
        i18n.set_language("en")


def test_invalid_settings_fall_back_to_defaults(window: MainWindow) -> None:
    settings = window.settings
    settings.setValue("format_idx", "pas-un-entier")
    settings.setValue("quality_idx", "9999")
    settings.sync()

    window._load_settings()

    assert window.format_combo.currentIndex() == 0
    assert window._quality_idx == len(QUALITIES) - 1
    assert window._pref_quality == len(QUALITIES) - 1


def test_negative_settings_are_clamped(window: MainWindow) -> None:
    window.settings.setValue("format_idx", -42)
    window.settings.setValue("quality_idx", "-7")

    window._load_settings()

    assert window.format_combo.currentIndex() == 0
    assert window._quality_idx == 0


def test_quality_is_disabled_while_downloading_and_after_retranslate(window: MainWindow) -> None:
    window._analysis = {"title": "Demo"}
    window._refresh_analysis()
    assert window._quality_enabled()

    window._set_state("running")
    assert not window.quality_combo.isEnabled()

    # Un changement de langue reconstruit la liste des qualités : elle doit
    # rester grisée tant que le téléchargement est actif.
    window.set_language("fr")
    assert not window.quality_combo.isEnabled()

    window._set_state("analyzing")
    assert not window.quality_combo.isEnabled()

    window._set_state("idle")
    assert window.quality_combo.isEnabled()


def test_quality_is_disabled_for_audio_only(window: MainWindow) -> None:
    mp3_index = window.format_combo.findData("mp3")
    assert mp3_index >= 0

    window.format_combo.setCurrentIndex(mp3_index)

    assert not window.quality_combo.isEnabled()
    assert window.format_combo.currentData() == "mp3"
    assert len(FORMATS) == window.format_combo.count()


def test_selectors_are_disabled_until_the_link_is_analyzed(window: MainWindow) -> None:
    assert not window.format_combo.isEnabled()
    assert not window.quality_combo.isEnabled()

    window._analysis = {"title": "Demo"}
    window._refresh_analysis()

    assert window.format_combo.isEnabled()
    assert window.quality_combo.isEnabled()

    # Changer l'URL efface l'analyse : les listes redeviennent inactives.
    window._clear_analysis()

    assert not window.format_combo.isEnabled()
    assert not window.quality_combo.isEnabled()


class _FakeClipboard:
    """Presse-papiers factice : évite de toucher au vrai presse-papiers en test."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.cleared = False

    def text(self) -> str:
        return self._text

    def clear(self) -> None:
        self._text = ""
        self.cleared = True


def test_clipboard_is_cleared_when_it_still_holds_the_url() -> None:
    clipboard = _FakeClipboard("  https://youtu.be/abc  ")

    assert MainWindow._clear_clipboard_if_ours("https://youtu.be/abc", clipboard)
    assert clipboard.cleared
    assert clipboard.text() == ""


def test_clipboard_is_preserved_when_it_holds_something_else() -> None:
    clipboard = _FakeClipboard("notes personnelles")

    assert not MainWindow._clear_clipboard_if_ours("https://youtu.be/abc", clipboard)
    assert not clipboard.cleared
    assert clipboard.text() == "notes personnelles"


def test_clipboard_is_ignored_for_empty_url() -> None:
    clipboard = _FakeClipboard("https://youtu.be/abc")

    assert not MainWindow._clear_clipboard_if_ours("   ", clipboard)
    assert not clipboard.cleared


class _FakeSignal:
    def __init__(self) -> None:
        self._slots = []

    def connect(self, slot) -> None:
        self._slots.append(slot)

    def emit(self) -> None:
        for slot in list(self._slots):
            slot()


class _FakeThread:
    def __init__(self, finishes: bool) -> None:
        self.finished = _FakeSignal()
        self.interrupt_requested = False
        self.terminated = False
        self.deleted = False
        self._finishes = finishes

    def isRunning(self) -> bool:  # noqa: N802
        return True

    def requestInterruption(self) -> None:  # noqa: N802
        self.interrupt_requested = True

    def wait(self, _timeout_ms: int) -> bool:
        return self._finishes

    def terminate(self) -> None:
        self.terminated = True

    def deleteLater(self) -> None:  # noqa: N802
        self.deleted = True


def test_stop_thread_never_calls_terminate(qapp: QApplication) -> None:
    thread = _FakeThread(finishes=False)
    MainWindow._ORPHAN_THREADS.clear()

    MainWindow._stop_thread(thread, 1)

    assert thread.interrupt_requested
    assert not thread.terminated
    assert thread in MainWindow._ORPHAN_THREADS

    thread.finished.emit()

    assert thread not in MainWindow._ORPHAN_THREADS
    assert thread.deleted


def test_stop_thread_does_not_orphan_finished_thread(qapp: QApplication) -> None:
    thread = _FakeThread(finishes=True)
    MainWindow._ORPHAN_THREADS.clear()

    MainWindow._stop_thread(thread, 1)

    assert thread.interrupt_requested
    assert not thread.terminated
    assert thread not in MainWindow._ORPHAN_THREADS
    assert not thread.deleted  # détruit par _on_thread_finished, pas ici

