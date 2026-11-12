"""Génère les captures d'écran du README (mode Qt offscreen).

    .venv\\Scripts\\python.exe tools\\make_screenshot.py

Les captures montrent un état analysé mais aucun téléchargement réel : l'URL et
les métadonnées sont fictives, et les chemins affichés sont neutres.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from app import i18n
from app.themes import build_qss

OUTPUT = ROOT / "docs" / "screenshots"

# URL et métadonnées fictives : aucun contenu réel n'est représenté.
DEMO_URL = "https://www.youtube.com/watch?v=ZTVDProDemo"
DEMO_INFO = {
    "title": "Vidéo de démonstration — ZTVD Pro",
    "uploader": "Chaîne d'exemple",
    "duration": 754,
    "max_height": 2160,
}


def _prepare(window, app: QApplication) -> None:
    """Place la fenêtre dans l'état « URL analysée » sans lancer yt-dlp."""
    window.output_edit.setText(r"C:\Users\Public\Videos\ZTVD Pro")
    window.url_edit.setText(DEMO_URL)
    window.on_analyze_done(dict(DEMO_INFO))
    window.status_lbl.setText(i18n.tr("status_analysis_done"))
    window.stats_lbl.setText(f"{i18n.tr('elapsed')}: 00:03")
    window.progress_bar.setRange(0, 1000)
    window.progress_bar.setValue(1000)
    window.progress_bar.setFormat("100%")
    window.log_view.clear()
    fixed_lines = [
        ("10:24:31", "🔎 ", i18n.tr("step_analyze_start", url=DEMO_URL)),
        ("10:24:32", "", f"[youtube] Extracting URL: {DEMO_URL}"),
        ("10:24:32", "", "[youtube] ZTVDProDemo: Downloading webpage"),
        ("10:24:33", "", "[youtube] ZTVDProDemo: Downloading player 0123abcd"),
        ("10:24:33", "", "[youtube] ZTVDProDemo: Downloading initial data API JSON"),
        ("10:24:34", "", "[info] ZTVDProDemo: Downloading 1 format(s): 313+251"),
        ("10:24:34", "", "[info] Available subtitles: fr, en"),
        ("10:24:35", "✔ ", i18n.tr("step_analyze_done", title=DEMO_INFO["title"])),
    ]
    for stamp, prefix, text in fixed_lines:
        window.log_view.appendPlainText(f"[{stamp}] {prefix}{text}")
    # La détection réelle renverrait un chemin local : on affiche volontairement
    # le message neutre « trouvé dans le PATH ».
    window.ffmpeg_status.setText(i18n.tr("ffmpeg_ok_system"))
    window.steps_section.set_expanded(True)
    for _ in range(8):
        app.processEvents()


def main() -> int:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        tempfile.mkdtemp(prefix="ztvd-screenshot-"),
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ZTVDProScreenshot")
    app.setOrganizationName("ZTVDProScreenshot")
    app.setStyle("Fusion")

    from app.main_window import MainWindow

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for theme, lang, name in (("light", "fr", "main.png"), ("dark", "fr", "main-dark.png")):
        settings = QSettings()
        settings.setValue("auto_update", "false")
        settings.setValue("theme", theme)
        settings.setValue("lang", lang)
        settings.sync()

        i18n.set_language(lang)
        app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        app.setStyleSheet(build_qss(theme))

        window = MainWindow(settings)
        window.resize(1000, 900)
        window.show()
        _prepare(window, app)
        # Ajuste la hauteur au contenu réel pour éviter une zone vide en bas.
        window.resize(1000, max(700, window.sizeHint().height()))
        for _ in range(4):
            app.processEvents()

        image = window.grab().toImage()
        target = OUTPUT / name
        if not image.save(str(target)):
            print(f"Échec de l'écriture : {target}")
            return 1
        print(f"Capture générée : {target} ({image.width()}x{image.height()})")
        window.close()
        app.processEvents()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
