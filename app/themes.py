"""Thèmes clair et sombre (feuilles de style Qt)."""
from __future__ import annotations

PALETTES = {
    "light": dict(bg="#f4f5f9", card="#ffffff", text="#1f2430", muted="#6b7280",
                  border="#d8dce6", accent="#4f6df5", accent_h="#3d59e0",
                  input="#ffffff", hover="#eceef6", on_accent="#ffffff"),
    "dark": dict(bg="#14161c", card="#1d2029", text="#e8eaf0", muted="#98a0b3",
                 border="#2e3342", accent="#6f8bff", accent_h="#8aa0ff",
                 input="#161922", hover="#262a37", on_accent="#10131a"),
}

_TEMPLATE = """
QWidget {{ background: {bg}; color: {text}; font-size: 13px; }}
QMainWindow, QDialog, QMessageBox {{ background: {bg}; }}
QLabel {{ background: transparent; }}
QLabel#muted {{ color: {muted}; }}
QFrame#card {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}
QFrame#card QLabel, QFrame#card QWidget#row {{ background: transparent; }}
QMenuBar {{ background: {card}; border-bottom: 1px solid {border}; }}
QMenuBar::item {{ padding: 6px 12px; background: transparent; }}
QMenuBar::item:selected {{ background: {hover}; border-radius: 6px; }}
QMenu {{ background: {card}; border: 1px solid {border}; padding: 4px; }}
QMenu::item {{ padding: 6px 24px; border-radius: 6px; }}
QMenu::item:selected {{ background: {accent}; color: {on_accent}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 8px; }}
QLineEdit, QComboBox, QPlainTextEdit {{
    background: {input}; border: 1px solid {border}; border-radius: 8px; padding: 7px 10px;
    selection-background-color: {accent}; selection-color: {on_accent};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border: 1px solid {accent}; }}
QComboBox QAbstractItemView {{
    background: {card}; border: 1px solid {border};
    selection-background-color: {accent}; selection-color: {on_accent};
}}
QPushButton {{ background: {card}; border: 1px solid {border}; border-radius: 8px; padding: 7px 16px; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton:disabled {{ color: {muted}; }}
QPushButton#primary {{ background: {accent}; color: {on_accent}; border: none; font-weight: 600; padding: 9px 26px; }}
QPushButton#primary:hover {{ background: {accent_h}; }}
QPushButton#primary:disabled {{ background: {border}; color: {muted}; }}
QProgressBar {{ background: {input}; border: 1px solid {border}; border-radius: 8px;
    text-align: center; min-height: 22px; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 7px; }}
QToolButton#section {{ background: transparent; border: none; font-weight: 600; padding: 6px 4px; text-align: left; }}
QToolButton#section:hover {{ color: {accent}; }}
QToolTip {{ background: {card}; color: {text}; border: 1px solid {border}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def build_qss(theme: str) -> str:
    return _TEMPLATE.format(**PALETTES.get(theme, PALETTES["light"]))
