"""Génère ``assets/icon.png`` et ``assets/icon.ico``.

Le script n'utilise que PySide6 (déjà requis par l'application) et ne dépend
d'aucune ressource externe. Relancez-le après une modification du dessin :

    .venv\\Scripts\\python.exe tools\\make_icon.py
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QImageWriter,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(size: int) -> QImage:
    """Dessine l'icône à la résolution demandée."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s = float(size)

    # Fond arrondi avec dégradé bleu nuit → bleu clair.
    rect = QRectF(s * 0.04, s * 0.04, s * 0.92, s * 0.92)
    background = QPainterPath()
    background.addRoundedRect(rect, s * 0.22, s * 0.22)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#0f172a"))
    gradient.setColorAt(0.55, QColor("#1d4ed8"))
    gradient.setColorAt(1.0, QColor("#0ea5e9"))
    painter.fillPath(background, gradient)

    # Triangle « lecture ».
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#ffffff"))
    painter.drawPolygon(QPolygonF([
        QPointF(s * 0.33, s * 0.26),
        QPointF(s * 0.33, s * 0.62),
        QPointF(s * 0.64, s * 0.44),
    ]))

    # Flèche de téléchargement.
    painter.drawRoundedRect(QRectF(s * 0.70, s * 0.28, s * 0.085, s * 0.30), s * 0.04, s * 0.04)
    painter.drawPolygon(QPolygonF([
        QPointF(s * 0.61, s * 0.54),
        QPointF(s * 0.79, s * 0.54),
        QPointF(s * 0.70, s * 0.70),
    ]))

    # Bac de réception.
    painter.setPen(QPen(
        QColor("#ffffff"),
        max(1.0, s * 0.045),
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
    ))
    painter.drawLine(QPointF(s * 0.60, s * 0.79), QPointF(s * 0.80, s * 0.79))
    painter.end()
    return image


def _png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    writer = QImageWriter(buffer, b"PNG")
    if not writer.write(image):
        raise RuntimeError(f"Écriture PNG impossible : {writer.errorString()}")
    
    data = bytes(buffer.data().data())
    buffer.close()
    return data


def main() -> int:
    QGuiApplication(sys.argv)  # nécessaire pour les plugins graphiques Qt
    ASSETS.mkdir(exist_ok=True)

    images = {size: render(size) for size in SIZES}
    if not images[256].save(str(ASSETS / "icon.png")):
        raise RuntimeError("Écriture de assets/icon.png impossible")

    payloads = [(size, _png_bytes(images[size])) for size in SIZES]
    offset = 6 + 16 * len(payloads)
    with (ASSETS / "icon.ico").open("wb") as handle:
        # ICONDIR
        handle.write(struct.pack("<HHH", 0, 1, len(payloads)))
        # ICONDIRENTRY (les dimensions 256 sont encodées par 0)
        for size, payload in payloads:
            dimension = 0 if size >= 256 else size
            handle.write(struct.pack(
                "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(payload), offset))
            offset += len(payload)
        for _size, payload in payloads:
            handle.write(payload)

    print(f"Icône générée : {ASSETS / 'icon.png'} et {ASSETS / 'icon.ico'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
