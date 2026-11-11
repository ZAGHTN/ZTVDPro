"""ZTVD Pro – point d'entrée."""
import sys

from PySide6.QtCore import QLocale, QSettings, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app import APP_NAME, i18n
from app.themes import build_qss


def main() -> int:
    from app.ytdlp_runtime import activate_cached

    # Avant tout import de yt_dlp : active une éventuelle mise à jour
    # téléchargée dans le dossier utilisateur (version compilée uniquement).
    activate_cached()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("ZT Videos Downloader")
    app.setStyle("Fusion")

    settings = QSettings()
    default_lang = QLocale.system().name()[:2]
    lang = str(settings.value("lang", default_lang if default_lang in i18n.LANGUAGES else "en"))
    i18n.set_language(lang)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight)
    app.setStyleSheet(build_qss(str(settings.value("theme", "light"))))

    try:
        from app.main_window import MainWindow  # importe yt-dlp
    except ModuleNotFoundError as exc:
        if exc.name != "yt_dlp":
            raise
        QMessageBox.critical(None, APP_NAME, i18n.tr("err_ytdlp_missing"))
        return 1

    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
