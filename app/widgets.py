"""Widgets personnalisés."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QSizePolicy, QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """Section repliable : un bouton-titre avec flèche + un contenu masquable."""

    toggled = Signal(bool)  # True = dépliée, False = repliée

    def __init__(self, title: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._btn = QToolButton()
        self._btn.setObjectName("section")
        self._btn.setCheckable(True)
        self._btn.setChecked(False)
        self._btn.setText(title)
        self._btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn.toggled.connect(self._on_toggled)

        self._body = QFrame()
        self._body.setVisible(False)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._btn)
        layout.addWidget(self._body)
        self.refresh_arrow()

    def set_content(self, widget: QWidget) -> None:
        self._body_layout.addWidget(widget)

    def set_title(self, title: str) -> None:
        self._btn.setText(title)

    def is_expanded(self) -> bool:
        return self._btn.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self._btn.setChecked(expanded)

    def refresh_arrow(self) -> None:
        if self._btn.isChecked():
            arrow = Qt.ArrowType.DownArrow
        elif self.layoutDirection() == Qt.LayoutDirection.RightToLeft:
            arrow = Qt.ArrowType.LeftArrow
        else:
            arrow = Qt.ArrowType.RightArrow
        self._btn.setArrowType(arrow)

    def _on_toggled(self, checked: bool) -> None:
        self._body.setVisible(checked)
        self.refresh_arrow()
        self.toggled.emit(checked)
