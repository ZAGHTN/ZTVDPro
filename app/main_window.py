"""Fenêtre principale."""
from __future__ import annotations

import os
import platform
import sys
import time

import PySide6
from PySide6.QtCore import QProcess, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QStandardItemModel
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import __version__, i18n
from .config import FORMATS, QUALITIES, check_ffmpeg, default_output_dir
from .downloader import AnalyzeWorker, DownloadWorker, is_valid_url
from .i18n import LANGUAGES, tr
from .logger import logger
from .resources import app_icon
from .system import reveal_in_file_manager
from .themes import build_qss
from .updater import InstallWorker, UpdateWorker, installed_version, is_frozen, is_newer
from .widgets import CollapsibleSection
from .ytdlp_runtime import cached_is_active, revert_to_bundled


def human_size(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"


def quality_label(height: int) -> str:
    """Libellé de la plus haute qualité de la liste qui tient dans `height`."""
    best: tuple[str, int] | None = None
    for label, h in QUALITIES:
        if h and h <= height + 8 and (best is None or h > best[1]):
            best = (label, h)
    return best[0] if best else f"{height}p"


def human_eta(seconds) -> str:
    if seconds is None:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class MainWindow(QMainWindow):
    # Threads qui n'ont pas répondu à l'annulation : conservés pour éviter que
    # Qt ne détruise un objet encore en cours d'exécution.
    _ORPHAN_THREADS: list = []

    def __init__(self, settings: QSettings):
        super().__init__()
        self.setWindowIcon(app_icon())
        self.settings = settings
        self.worker = None
        self.update_worker: UpdateWorker | None = None
        self._pending_latest = ""
        self._silent_update = False
        self._dl_title = ""  # titre dynamique pendant un téléchargement
        self._state = "idle"  # idle | running | pausing | paused
        self._pending_pause = False
        self.analyzer: AnalyzeWorker | None = None
        self._analysis: dict | None = None  # résultat de la dernière analyse
        self._analysis_started = 0.0
        self._pref_quality = 4  # qualité choisie par l'utilisateur (1080p par défaut)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(500)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._last_path = ""  # dernier fichier téléchargé avec succès
        self._last_dir = ""
        self._job: dict | None = None  # paramètres du téléchargement (pour la reprise)
        self._expanded_height = 720  # hauteur à restaurer quand la section est dépliée

        self.resize(780, 720)
        self._build_menu()
        self._build_ui()
        self.url_edit.textChanged.connect(lambda _text: self._clear_analysis())
        self._load_settings()
        self.retranslate()

        self.steps_section.toggled.connect(self._on_steps_toggled)
        if not self.steps_section.is_expanded():
            self._shrink_to_fit()

        if self.act_auto_update.isChecked() and not is_frozen():
            QTimer.singleShot(2000, lambda: self.check_updates(silent=True))

    # ------------------------------------------------------------------ menus
    def _build_menu(self) -> None:
        bar = self.menuBar()
        self.m_file = bar.addMenu("")
        self.act_quit = QAction(self)
        self.act_quit.triggered.connect(self.close)
        self.m_file.addAction(self.act_quit)

        self.m_settings = bar.addMenu("")
        self.m_lang = self.m_settings.addMenu("")
        self.lang_group = QActionGroup(self)
        self.lang_actions: dict[str, QAction] = {}
        for code, name in LANGUAGES.items():
            act = QAction(name, self)
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, c=code: self.set_language(c))
            self.lang_group.addAction(act)
            self.m_lang.addAction(act)
            self.lang_actions[code] = act

        self.m_theme = self.m_settings.addMenu("")
        self.theme_group = QActionGroup(self)
        self.act_light = QAction(self)
        self.act_dark = QAction(self)
        for _act in (self.act_light, self.act_dark):
            _act.setCheckable(True)
        for act, name in ((self.act_light, "light"), (self.act_dark, "dark")):
            act.triggered.connect(lambda _=False, n=name: self.set_theme(n))
            self.theme_group.addAction(act)
            self.m_theme.addAction(act)

        self.m_tools = bar.addMenu("")
        self.act_update = QAction(self)
        self.act_update.triggered.connect(lambda _checked=False: self.check_updates(silent=False))
        self.act_revert = QAction(self)
        self.act_revert.triggered.connect(lambda _checked=False: self.revert_ytdlp())
        self.act_auto_update = QAction(self)
        self.act_auto_update.setCheckable(True)
        self.m_tools.addAction(self.act_update)
        self.m_tools.addAction(self.act_revert)
        self.m_tools.addAction(self.act_auto_update)

        self.m_help = bar.addMenu("")
        self.act_about = QAction(self)
        self.act_about.triggered.connect(self.show_about)
        self.m_help.addAction(self.act_about)

    # --------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # --- carte des paramètres
        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self.lbl_url, self.lbl_quality, self.lbl_format = QLabel(), QLabel(), QLabel()
        self.lbl_output, self.lbl_ffmpeg = QLabel(), QLabel()

        self.url_edit = QLineEdit()
        self.url_edit.setClearButtonEnabled(True)
        self.btn_paste = QPushButton()
        self.btn_paste.clicked.connect(self.paste_url)
        self.btn_analyze = QPushButton()
        self.btn_analyze.clicked.connect(self.analyze_url)
        self.info_lbl = QLabel()
        self.info_lbl.setObjectName("muted")
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setTextFormat(Qt.TextFormat.PlainText)  # titres arbitraires : pas de HTML
        self.info_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.info_lbl.setVisible(False)

        self.quality_combo = QComboBox()
        self.quality_combo.activated.connect(self._on_quality_activated)
        self.format_combo = QComboBox()
        for label, value in FORMATS:
            self.format_combo.addItem(label, value)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)

        self.output_edit = QLineEdit()
        self.btn_out = QPushButton()
        self.btn_out.clicked.connect(self.choose_output)

        self.ffmpeg_edit = QLineEdit()
        self.ffmpeg_edit.textChanged.connect(self.refresh_ffmpeg_status)
        self.btn_ff = QPushButton()
        self.btn_ff.clicked.connect(self.choose_ffmpeg)
        self.ffmpeg_status = QLabel()
        self.ffmpeg_status.setObjectName("muted")

        url_buttons = QHBoxLayout()
        url_buttons.setSpacing(6)
        url_buttons.addWidget(self.btn_paste)
        url_buttons.addWidget(self.btn_analyze)

        grid.addWidget(self.lbl_url, 0, 0)
        grid.addWidget(self.url_edit, 0, 1)
        grid.addLayout(url_buttons, 0, 2)
        grid.addWidget(self.info_lbl, 1, 1, 1, 2)
        grid.addWidget(self.lbl_quality, 2, 0)
        grid.addWidget(self.quality_combo, 2, 1, 1, 2)
        grid.addWidget(self.lbl_format, 3, 0)
        grid.addWidget(self.format_combo, 3, 1, 1, 2)
        grid.addWidget(self.lbl_output, 4, 0)
        grid.addWidget(self.output_edit, 4, 1)
        grid.addWidget(self.btn_out, 4, 2)
        grid.addWidget(self.lbl_ffmpeg, 5, 0)
        grid.addWidget(self.ffmpeg_edit, 5, 1)
        grid.addWidget(self.btn_ff, 5, 2)
        grid.addWidget(self.ffmpeg_status, 6, 1, 1, 2)
        outer.addWidget(card)

        # --- boutons d'action
        actions = QHBoxLayout()
        self.btn_download = QPushButton()
        self.btn_download.setObjectName("primary")
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self.start_download)
        self.btn_pause = QPushButton()
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_open = QPushButton()
        self.btn_open.setEnabled(False)  # activé à la fin d'un téléchargement réussi
        self.btn_open.clicked.connect(self.open_download_folder)
        self.btn_cancel = QPushButton()
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_download)
        actions.addStretch(1)
        actions.addWidget(self.btn_download)
        actions.addWidget(self.btn_pause)
        actions.addWidget(self.btn_cancel)
        actions.addWidget(self.btn_open)
        actions.addStretch(1)
        outer.addLayout(actions)

        # --- progression
        self.progress_card = QFrame()
        self.progress_card.setObjectName("card")
        pl = QVBoxLayout(self.progress_card)
        pl.setContentsMargins(16, 14, 16, 14)
        self.grp_progress_lbl = QLabel()
        self.grp_progress_lbl.setStyleSheet("font-weight:600;")
        self.status_lbl = QLabel()
        self.status_lbl.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.stats_lbl = QLabel()
        self.stats_lbl.setObjectName("muted")
        pl.addWidget(self.grp_progress_lbl)
        pl.addWidget(self.status_lbl)
        pl.addWidget(self.progress_bar)
        pl.addWidget(self.stats_lbl)
        outer.addWidget(self.progress_card)

        # --- étapes (repliable)
        self.steps_section = CollapsibleSection()
        steps_body = QWidget()
        steps_layout = QVBoxLayout(steps_body)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        steps_layout.setSpacing(6)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setMinimumHeight(170)
        self.btn_clear_log = QPushButton()
        self.btn_clear_log.setEnabled(False)
        self.btn_clear_log.clicked.connect(self.log_view.clear)
        self.log_view.textChanged.connect(
            lambda: self.btn_clear_log.setEnabled(not self.log_view.document().isEmpty()))
        header = QHBoxLayout()
        header.addStretch(1)
        header.addWidget(self.btn_clear_log)
        steps_layout.addLayout(header)
        steps_layout.addWidget(self.log_view)
        self.steps_section.set_content(steps_body)
        outer.addWidget(self.steps_section)
        outer.addStretch(1)

    # ----------------------------------------------------------- settings/i18n
    def _int_setting(self, key: str, default: int, minimum: int, maximum: int) -> int:
        """Lit un entier de QSettings en tolérant les valeurs absentes ou corrompues."""
        try:
            value = int(str(self.settings.value(key, default)))
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, value))

    def _load_settings(self) -> None:
        s = self.settings
        self.output_edit.setText(str(s.value("output_dir", default_output_dir())))
        self.ffmpeg_edit.setText(str(s.value("ffmpeg_dir", "")))
        self.format_combo.setCurrentIndex(
            self._int_setting("format_idx", 0, 0, len(FORMATS) - 1))
        self._quality_idx = self._int_setting("quality_idx", 4, 0, len(QUALITIES) - 1)
        self._pref_quality = self._quality_idx
        self.act_auto_update.setChecked(str(s.value("auto_update", "true")).lower() == "true")
        self.lang_actions[i18n.current_language()].setChecked(True)
        (self.act_dark if str(s.value("theme", "light")) == "dark" else self.act_light).setChecked(True)
        self.steps_section.set_expanded(str(s.value("steps_open", "false")).lower() == "true")

    def _save_settings(self) -> None:
        s = self.settings
        s.setValue("lang", i18n.current_language())
        s.setValue("theme", "dark" if self.act_dark.isChecked() else "light")
        s.setValue("output_dir", self.output_edit.text())
        s.setValue("ffmpeg_dir", self.ffmpeg_edit.text())
        s.setValue("quality_idx", self._pref_quality)
        s.setValue("format_idx", self.format_combo.currentIndex())
        s.setValue("auto_update", self.act_auto_update.isChecked())
        s.setValue("steps_open", self.steps_section.is_expanded())

    def set_language(self, code: str) -> None:
        i18n.set_language(code)
        QApplication.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight)
        self.lang_actions[code].setChecked(True)
        self.retranslate()

    def set_theme(self, name: str) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(build_qss(name))
        (self.act_dark if name == "dark" else self.act_light).setChecked(True)

    def retranslate(self) -> None:
        self.refresh_title()
        self.m_file.setTitle(tr("menu_file"))
        self.act_quit.setText(tr("menu_quit"))
        self.m_settings.setTitle(tr("menu_settings"))
        self.m_lang.setTitle(tr("menu_language"))
        self.m_theme.setTitle(tr("menu_theme"))
        self.act_light.setText(tr("theme_light"))
        self.act_dark.setText(tr("theme_dark"))
        self.m_tools.setTitle(tr("menu_tools"))
        self.act_update.setText(tr("menu_update"))
        self.act_revert.setText(tr("upd_revert"))
        self.act_revert.setVisible(cached_is_active())
        self.act_auto_update.setText(tr("menu_auto_update"))
        self.m_help.setTitle(tr("menu_help"))
        self.act_about.setText(tr("menu_about"))

        self.lbl_url.setText(tr("lbl_url"))
        self.url_edit.setPlaceholderText(tr("ph_url"))
        self.btn_paste.setText(tr("btn_paste"))
        self.lbl_quality.setText(tr("lbl_quality"))
        self.lbl_format.setText(tr("lbl_format"))
        tip = tr("tip_analyze_first")
        self.quality_combo.setToolTip(tip)
        self.format_combo.setToolTip(tip)
        self.lbl_output.setText(tr("lbl_output"))
        self.output_edit.setPlaceholderText(tr("ph_output"))
        self.lbl_ffmpeg.setText(tr("lbl_ffmpeg"))
        self.ffmpeg_edit.setPlaceholderText(tr("ph_ffmpeg"))
        self.btn_out.setText(tr("btn_browse"))
        self.btn_ff.setText(tr("btn_browse"))
        self.btn_download.setText(tr("btn_download"))
        self.btn_cancel.setText(tr("btn_cancel"))
        self.btn_pause.setText(tr("btn_resume") if self._state == "paused" else tr("btn_pause"))
        self.btn_open.setText(tr("btn_open_folder"))
        self.btn_analyze.setText(tr("btn_analyze"))
        self.btn_clear_log.setText(tr("btn_clear_log"))
        self.grp_progress_lbl.setText(tr("grp_progress"))
        self.steps_section.set_title(tr("grp_steps"))
        self.steps_section.refresh_arrow()
        if self._state == "idle":
            self.status_lbl.setText(tr("status_ready"))
        elif self._state == "paused":
            self.status_lbl.setText(tr("status_paused"))

        # qualités : reconstruction en conservant la sélection
        idx = self.quality_combo.currentIndex() if self.quality_combo.count() else self._quality_idx
        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        for label, height in QUALITIES:
            self.quality_combo.addItem(tr("q_best") if height == 0 else label, height)
        self.quality_combo.setCurrentIndex(max(0, idx))
        self.quality_combo.blockSignals(False)
        self._on_format_changed()
        self.refresh_ffmpeg_status()
        self._refresh_analysis()

    # ---------------------------------------------------------------- helpers
    def _format_enabled(self) -> bool:
        """Le format n'est modifiable qu'au repos et après une analyse réussie."""
        return self._state == "idle" and self._analysis is not None

    def _quality_enabled(self) -> bool:
        """La qualité n'est modifiable qu'avec un format vidéo analysé."""
        return self._format_enabled() and self.format_combo.currentData() != "mp3"

    def _update_selector_state(self) -> None:
        """Grise qualité et format tant que le lien n'a pas été analysé."""
        self.format_combo.setEnabled(self._format_enabled())
        self.quality_combo.setEnabled(self._quality_enabled())

    def _on_format_changed(self) -> None:
        # la qualité vidéo n'a pas de sens pour l'audio seul, et les deux listes
        # doivent rester figées avant l'analyse ou pendant un téléchargement
        self._update_selector_state()

    def refresh_ffmpeg_status(self) -> None:
        ok, loc = check_ffmpeg(self.ffmpeg_edit.text())
        if not ok:
            self.ffmpeg_status.setText(tr("ffmpeg_missing"))
        elif loc:
            self.ffmpeg_status.setText(tr("ffmpeg_ok_path", path=loc))
        else:
            self.ffmpeg_status.setText(tr("ffmpeg_ok_system"))

    def _on_steps_toggled(self, expanded: bool) -> None:
        """Replie : la fenêtre rétrécit. Déplie : la hauteur précédente est rétablie."""
        if self.isMaximized() or self.isFullScreen():
            return
        if expanded:
            self.resize(self.width(), self._expanded_height)
        else:
            self._expanded_height = self.height()
            QTimer.singleShot(0, self._shrink_to_fit)

    def _shrink_to_fit(self) -> None:
        central = self.centralWidget()
        central_layout = central.layout() if central is not None else None
        if central_layout is not None:
            central_layout.invalidate()
            central_layout.activate()
        window_layout = self.layout()
        if window_layout is not None:
            window_layout.invalidate()
            window_layout.activate()
        self.resize(self.width(), self.minimumSizeHint().height())

    def refresh_title(self) -> None:
        """Titre de la fenêtre : « <x%> <nom de la vidéo> » pendant un téléchargement."""
        self.setWindowTitle(self._dl_title or tr("app_title"))

    def paste_url(self) -> None:
        self.url_edit.setText(QGuiApplication.clipboard().text().strip())

    def choose_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("dlg_select_output"), self.output_edit.text())
        if d:
            self.output_edit.setText(d)

    def choose_ffmpeg(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("dlg_select_ffmpeg"), self.ffmpeg_edit.text())
        if d:
            self.ffmpeg_edit.setText(d)

    def log_line(self, text: str, prefix: str = "") -> None:
        if text:
            self.log_view.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {prefix}{text}")

    def error(self, message: str) -> None:
        box = QMessageBox(QMessageBox.Icon.Warning, tr("err_title"), message, parent=self)
        box.setTextFormat(Qt.TextFormat.PlainText)  # messages d'erreur issus de sites distants : pas de HTML
        box.exec()

    def _set_state(self, state: str) -> None:
        """États : idle | analyzing | running | pausing | paused. Met à jour boutons et champs."""
        self._state = state
        busy = state != "idle"
        self.btn_download.setEnabled(not busy)
        self.btn_analyze.setEnabled(not busy)
        self.btn_pause.setEnabled(state in ("running", "paused"))
        self.btn_pause.setText(tr("btn_resume") if state == "paused" else tr("btn_pause"))
        self.btn_cancel.setEnabled(busy)
        for w in (self.url_edit, self.format_combo, self.output_edit, self.ffmpeg_edit,
                  self.btn_paste, self.btn_out, self.btn_ff):
            w.setEnabled(not busy)
        self._update_selector_state()

    # --------------------------------------------------------------- download
    def start_download(self) -> None:
        url = self.url_edit.text().strip()
        if not url.lower().startswith(("https://", "http://")):
            return self.error(tr("err_url"))
        if not is_valid_url(url):
            return self.error(tr("err_domain"))
        ok, location = check_ffmpeg(self.ffmpeg_edit.text())
        if not ok:
            return self.error(tr("err_ffmpeg"))
        out_dir = self.output_edit.text().strip() or default_output_dir()
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as exc:
            return self.error(str(exc))

        self.log_view.clear()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0%")
        self.stats_lbl.clear()
        self.status_lbl.setText(tr("status_starting"))
        self._save_settings()

        self._last_path = self._last_dir = ""
        self.btn_open.setEnabled(False)
        self._job = {
            "url": url, "out_dir": out_dir,
            "height": self.quality_combo.currentData() or 0,
            "container": self.format_combo.currentData(), "location": location,
        }
        self._launch()

    def _launch(self) -> None:
        """Démarre (ou reprend) le téléchargement décrit par self._job."""
        job = self._job
        if job is None:
            return
        self._pending_pause = False
        self.worker = DownloadWorker(job["url"], job["out_dir"], job["height"],
                                     job["container"], job["location"], self)
        self.worker.progress.connect(self.on_progress)
        self.worker.step.connect(self.on_step)
        self.worker.log.connect(lambda t: self.log_line(t))
        self.worker.succeeded.connect(self.on_success)
        self.worker.failed.connect(self.on_failure)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.paused.connect(self.on_paused)
        self.worker.finished.connect(self._on_thread_finished)
        self._set_state("running")
        self.worker.start()

    def toggle_pause(self) -> None:
        if self._state == "running" and self.worker is not None:
            self.worker.pause()
            self._set_state("pausing")
            self.status_lbl.setText(tr("status_pausing"))
        elif self._state == "paused":
            self.log_line(tr("step_resume"), "▶ ")
            self.status_lbl.setText(tr("status_starting"))
            self._dl_title = ""
            self.refresh_title()
            self._launch()  # yt-dlp reprend les fichiers .part existants

    def cancel_download(self) -> None:
        if self._state == "paused":  # aucun thread actif : on remet simplement à zéro
            self._job = None
            self._dl_title = ""
            self.refresh_title()
            self.status_lbl.setText(tr("status_cancelled"))
            self.log_line(tr("step_cancelled"), "■ ")
            self._set_state("idle")
        elif self._state == "analyzing" and self.analyzer is not None:
            self.analyzer.cancel()
            self.btn_cancel.setEnabled(False)
        elif self.worker is not None:
            self.worker.cancel()
            self.btn_cancel.setEnabled(False)

    # ---------------------------------------------------------------- analyse
    def analyze_url(self) -> None:
        url = self.url_edit.text().strip()
        if not url.lower().startswith(("https://", "http://")):
            return self.error(tr("err_url"))
        if not is_valid_url(url):
            return self.error(tr("err_domain"))
        self._clear_analysis()
        self.log_view.clear()
        self.stats_lbl.clear()
        self.progress_bar.setRange(0, 0)  # barre « occupée » : yt-dlp ne donne pas de pourcentage
        self.status_lbl.setText(tr("status_analyzing"))
        self.log_line(tr("step_analyze_start", url=url), "🔎 ")
        self._analysis_started = time.monotonic()
        self._elapsed_timer.start()
        # ffmpeg n'est pas requis pour analyser, mais transmettre son emplacement
        # évite le faux avertissement « ffmpeg not found » de yt-dlp.
        _, ffmpeg_location = check_ffmpeg(self.ffmpeg_edit.text())
        self.analyzer = AnalyzeWorker(url, ffmpeg_location, self)
        self.analyzer.log.connect(self.on_analyze_log)
        self.analyzer.analyzed.connect(self.on_analyze_done)
        self.analyzer.failed.connect(self.on_analyze_failed)
        self.analyzer.cancelled.connect(self.on_analyze_cancelled)
        self.analyzer.finished.connect(self._on_analyzer_finished)
        self._set_state("analyzing")
        self.analyzer.start()

    def _tick_elapsed(self) -> None:
        elapsed = human_eta(time.monotonic() - self._analysis_started)
        self.stats_lbl.setText(f"{tr('elapsed')}: {elapsed}")

    def _reset_bar(self) -> None:
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0%")

    def on_analyze_log(self, text: str) -> None:
        if not text:
            return
        self.log_line(text)
        short = text if len(text) <= 90 else text[:87] + "…"
        self.status_lbl.setText(tr("status_analyzing_detail", msg=short))

    def on_analyze_done(self, info: dict) -> None:
        self._analysis = info
        self._refresh_analysis()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(1000)
        self.progress_bar.setFormat("100%")
        self.status_lbl.setText(tr("status_analysis_done"))
        self.log_line(tr("step_analyze_done", title=info.get("title") or "?"), "✔ ")

    def on_analyze_failed(self, msg: str) -> None:
        self._reset_bar()
        self.status_lbl.setText(tr("status_analysis_failed"))
        self.log_line(tr("step_error", msg=msg), "✘ ")
        self.steps_section.set_expanded(True)
        self.error(msg)

    def on_analyze_cancelled(self) -> None:
        self._reset_bar()
        self.status_lbl.setText(tr("status_analysis_cancelled"))
        self.log_line(tr("step_cancelled"), "■ ")

    def _on_analyzer_finished(self) -> None:
        self._tick_elapsed()
        self._elapsed_timer.stop()
        analyzer, self.analyzer = self.analyzer, None
        if analyzer is not None:
            analyzer.deleteLater()
        self._set_state("idle")

    def _clear_analysis(self) -> None:
        self._analysis = None
        self._refresh_analysis()

    def _refresh_analysis(self) -> None:
        """Affiche le résumé de l'analyse et limite la liste des qualités à ce qui existe."""
        info = self._analysis
        if not info:
            self.info_lbl.clear()
            self.info_lbl.setVisible(False)
        else:
            parts = []
            if info.get("uploader"):
                parts.append(str(info["uploader"]))
            if info.get("duration"):
                parts.append(human_eta(info["duration"]))
            if info.get("max_height"):
                parts.append(f"{tr('max_quality')}: {quality_label(int(info['max_height']))}")
            text = str(info.get("title") or "?")
            if parts:
                text += "\n" + " • ".join(parts)
            self.info_lbl.setText(text)
            self.info_lbl.setVisible(True)
        self._apply_quality_limit()
        self._update_selector_state()

    def _on_quality_activated(self, index: int) -> None:
        self._pref_quality = index  # choix explicite de l'utilisateur

    def _apply_quality_limit(self) -> None:
        """Grise les qualités supérieures à la meilleure disponible (sinon tout est actif)."""
        model = self.quality_combo.model()
        if not isinstance(model, QStandardItemModel):
            return
        max_h = int((self._analysis or {}).get("max_height") or 0)
        count = self.quality_combo.count()
        for i in range(count):
            height = int(self.quality_combo.itemData(i) or 0)
            item = model.item(i)
            if item is not None:
                item.setEnabled(not max_h or height == 0 or height <= max_h + 8)

        def enabled(i: int) -> bool:
            it = model.item(i)
            return it is not None and it.isEnabled()

        target = self._pref_quality if 0 <= self._pref_quality < count else 0
        if not enabled(target):  # repli : la plus haute qualité réellement disponible
            target = next((i for i in range(count)
                           if enabled(i) and int(self.quality_combo.itemData(i) or 0) != 0), 0)
        self.quality_combo.setCurrentIndex(target)

    def open_download_folder(self) -> None:
        """Ouvre le dossier du dernier téléchargement (fichier sélectionné si possible)."""
        target = self._last_path if self._last_path and os.path.exists(self._last_path) else self._last_dir
        if target and not reveal_in_file_manager(target):
            self.error(tr("err_open_folder", path=target))

    def on_progress(self, p: dict) -> None:
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(int(p["percent"] * 10))
        self.progress_bar.setFormat(f"{p['percent']:.1f}%")
        self.status_lbl.setText(tr("status_downloading", file=p["file"]))
        self._dl_title = f"{p['percent']:.0f}% {p.get('title') or p['file']}"
        self.refresh_title()
        size = f"{human_size(p['done'])} / {human_size(p['total'])}" if p["total"] else human_size(p["done"])
        self.stats_lbl.setText(
            f"{tr('speed')}: {human_size(p['speed'])}/s   •   {tr('eta')}: {human_eta(p['eta'])}   •   {tr('size')}: {size}")

    def on_step(self, key: str, params: dict) -> None:
        self.log_line(tr(key, **params), "▶ ")
        if key == "step_pp_start":
            self.progress_bar.setRange(0, 0)  # animation « occupé »
            self.status_lbl.setText(tr("status_processing"))
            if self._state == "running":
                self.btn_pause.setEnabled(False)  # on ne met pas ffmpeg en pause
        elif key == "step_pp_done":
            self.progress_bar.setRange(0, 1000)
            self.progress_bar.setValue(1000)
            if self._state == "running":
                self.btn_pause.setEnabled(True)

    def on_success(self, path: str) -> None:
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(1000)
        self.progress_bar.setFormat("100%")
        self.status_lbl.setText(tr("status_done"))
        self.log_line(tr("step_finished", path=path), "✔ ")
        self._last_path = path
        self._last_dir = self._job["out_dir"] if self._job else self.output_edit.text()
        self.btn_open.setEnabled(True)

    def on_failure(self, msg: str) -> None:
        self.progress_bar.setRange(0, 1000)
        self.status_lbl.setText(tr("status_failed"))
        self.log_line(tr("step_error", msg=msg), "✘ ")
        self.steps_section.set_expanded(True)
        self.error(msg)

    def on_paused(self) -> None:
        self._pending_pause = True
        self.status_lbl.setText(tr("status_paused"))
        self.log_line(tr("step_pause"), "⏸ ")
        if self._dl_title:
            self._dl_title = "⏸ " + self._dl_title
            self.refresh_title()

    def on_cancelled(self) -> None:
        self.progress_bar.setRange(0, 1000)
        self.status_lbl.setText(tr("status_cancelled"))
        self.log_line(tr("step_cancelled"), "■ ")

    def _on_thread_finished(self) -> None:
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.deleteLater()
        if self._pending_pause:  # pause demandée : on garde job, titre et progression
            self._pending_pause = False
            self._set_state("paused")
            return
        self._dl_title = ""
        self.refresh_title()
        self._job = None
        self._set_state("idle")

    # ----------------------------------------------------------------- update
    def check_updates(self, silent: bool = False) -> None:
        if self.worker is not None or self.analyzer is not None:
            if not silent:
                self.error(tr("upd_busy"))
            return
        if self.update_worker is not None:
            return
        self._silent_update = silent
        self.statusBar().showMessage(tr("upd_checking"))
        self.update_worker = UpdateWorker("check", self)
        self.update_worker.check_done.connect(self._on_check_done)
        self.update_worker.error.connect(self._on_update_error)
        self.update_worker.finished.connect(self._clear_update_worker)
        self.update_worker.start()

    def _clear_update_worker(self) -> None:
        w, self.update_worker = self.update_worker, None
        if w:
            w.deleteLater()

    def _on_check_done(self, latest: str) -> None:
        current = installed_version()
        self.statusBar().clearMessage()
        if not is_newer(latest, current):
            if not self._silent_update:
                QMessageBox.information(self, tr("upd_title"), tr("upd_uptodate", current=current))
            return
        reply = QMessageBox.question(self, tr("upd_title"), tr("upd_available", current=current, latest=latest))
        if reply == QMessageBox.StandardButton.Yes:
            self._pending_latest = latest
            QTimer.singleShot(0, self._start_upgrade)

    def _start_upgrade(self) -> None:
        if self.update_worker is not None:  # le thread « check » se termine
            QTimer.singleShot(100, self._start_upgrade)
            return
        self.statusBar().showMessage(tr("upd_running"))
        self.btn_download.setEnabled(False)
        if is_frozen():
            # pas de pip dans l'exe : installation dans le dossier utilisateur
            self.update_worker = InstallWorker(self)
        else:
            self.update_worker = UpdateWorker("upgrade", self)
        self.update_worker.upgrade_done.connect(self._on_upgrade_done)
        self.update_worker.error.connect(self._on_update_error)
        self.update_worker.finished.connect(self._clear_update_worker)
        self.update_worker.start()

    def _on_upgrade_done(self, latest: str) -> None:
        self.statusBar().clearMessage()
        self.btn_download.setEnabled(self._state == "idle")
        version = latest or self._pending_latest
        if is_frozen():
            self.act_revert.setVisible(cached_is_active())
            reply = QMessageBox.question(
                self, tr("upd_title"), tr("upd_done_restart", latest=version))
            if reply == QMessageBox.StandardButton.Yes:
                self._restart_app()
            return
        QMessageBox.information(self, tr("upd_title"), tr("upd_done", latest=version))

    def _restart_app(self) -> None:
        """Relance l'exe compilé avec ses arguments d'origine."""
        if not is_frozen():
            return
        self._save_settings()
        if QProcess.startDetached(sys.executable, sys.argv[1:]):
            QApplication.quit()
            return
        self.error(tr("upd_restart_failed"))

    def revert_ytdlp(self) -> None:
        """Supprime la surcharge téléchargée et revient à la version intégrée."""
        if not cached_is_active():
            return
        reply = QMessageBox.question(self, tr("upd_title"), tr("upd_revert_ask"))
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            removed = revert_to_bundled()
        except OSError as exc:
            return self.error(str(exc))
        self.act_revert.setVisible(cached_is_active())
        if not removed:
            return
        reply = QMessageBox.question(self, tr("upd_title"), tr("upd_revert_done"))
        if reply == QMessageBox.StandardButton.Yes:
            self._restart_app()

    def _on_update_error(self, msg: str) -> None:
        self.statusBar().clearMessage()
        self.btn_download.setEnabled(self._state == "idle")
        if not self._silent_update or self._pending_latest:
            self.error(tr("upd_failed", msg=msg) if self._pending_latest else tr("upd_check_failed", msg=msg))

    # ------------------------------------------------------------------ misc
    def show_about(self) -> None:
        QMessageBox.about(self, tr("about_title"), tr(
            "about_body", app=__version__, ytdlp=installed_version(),
            py=platform.python_version(), qt=PySide6.__version__))

    # ----------------------------------------------------- fermeture sécurisée
    def _download_active(self) -> bool:
        """Vrai si un téléchargement est en cours, en cours de pause, ou en pause."""
        if self._state == "paused":
            return True
        return self.worker is not None and self.worker.isRunning()

    def _upgrade_active(self) -> bool:
        w = self.update_worker
        return w is not None and w.isRunning() and w.mode == "upgrade"

    def _ask_stop_download(self, paused: bool = False) -> bool:
        """Demande confirmation ; True si l'utilisateur accepte d'annuler le téléchargement."""
        text = tr("quit_download_paused" if paused else "quit_download_running")
        box = QMessageBox(QMessageBox.Icon.Question, tr("quit_title"), text, parent=self)
        quit_btn = box.addButton(tr("btn_quit_anyway"), QMessageBox.ButtonRole.DestructiveRole)
        stay_btn = box.addButton(tr("btn_stay"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(stay_btn)
        box.exec()
        return box.clickedButton() is quit_btn

    def confirm_quit(self) -> bool:
        """Retourne True si la fermeture de la fenêtre peut continuer."""
        if self._upgrade_active():
            # interrompre pip en plein milieu pourrait corrompre l'installation
            QMessageBox.information(self, tr("quit_title"), tr("quit_update_running"))
            return False
        return not self._download_active() or self._ask_stop_download(paused=self._state == "paused")

    @classmethod
    def _release_orphan(cls, thread) -> None:
        """Retire un thread orphelin dès qu'il se termine, puis le détruit."""
        try:
            cls._ORPHAN_THREADS.remove(thread)
        except ValueError:
            pass
        thread.deleteLater()

    @classmethod
    def _stop_thread(cls, thread, timeout_ms: int) -> None:
        """Attend la fin coopérative d'un thread, sans jamais le tuer.

        ``QThread.terminate()`` peut corrompre les fichiers partiels de yt-dlp et
        faire planter Qt. En cas de dépassement, le thread est conservé en
        arrière-plan jusqu'à sa fin réelle.
        """
        if thread is None or not thread.isRunning():
            return
        thread.requestInterruption()
        if thread.wait(timeout_ms):
            return
        logger.warning(
            "Thread %s encore actif après %d ms ; abandon coopératif (pas de terminate()).",
            type(thread).__name__, timeout_ms,
        )
        cls._ORPHAN_THREADS.append(thread)
        thread.finished.connect(lambda t=thread: cls._release_orphan(t))

    @staticmethod
    def _clear_clipboard_if_ours(url: str, clipboard=None) -> bool:
        """Vide le presse-papiers s'il contient encore l'URL de la fenêtre.

        L'application ne copie jamais rien : effacer un contenu étranger
        supprimerait les données d'une autre application. On ne nettoie donc
        que la valeur que l'utilisateur a collée pour ce téléchargement.

        Retourne ``True`` si le presse-papiers a effectivement été vidé.
        """
        if not url or not url.strip():
            return False
        if clipboard is None:
            if QGuiApplication.instance() is None:
                return False
            try:
                clipboard = QGuiApplication.clipboard()
            except RuntimeError:
                return False
        if clipboard is None:
            return False
        try:
            if clipboard.text().strip() != url.strip():
                return False
            clipboard.clear()
            return True
        except RuntimeError:
            # Presse-papiers déjà détruit ou possédé par une autre application
            # pendant la fermeture : rien de plus à faire, on ne bloque pas.
            logger.warning("Presse-papiers indisponible à la fermeture ; contenu non vidé.")
            return False

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self.confirm_quit():
            event.ignore()
            return
        self._save_settings()
        url = self.url_edit.text().strip()
        if self.worker is not None:
            self.worker.cancel()
            self._stop_thread(self.worker, 15000)
        if self.analyzer is not None:
            self.analyzer.cancel()
            self._stop_thread(self.analyzer, 10000)
        self._stop_thread(self.update_worker, 5000)  # simple vérification de version
        self._clear_clipboard_if_ours(url)
        super().closeEvent(event)
