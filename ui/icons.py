"""
Ultra PDF Editor - toolbar icons drawn with QPainter.

The toolbar used emoji and symbol characters as button labels. Segoe UI has
none of them, so the first time Qt measured each one it searched the system
fonts for a fallback: ~0.75 s of the ~1.6 s startup went into building the
toolbars. These icons are simple vector drawings in a 24x24 grid, painted in
the theme's text colour (white when a tool button is checked), so
they follow the app's light/dark theme and need no font or image file.
"""

import math
from collections.abc import Callable

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QIconEngine, QPainter, QPainterPath, QPen, QPixmap

Draw = Callable[[QPainter], None]


def _arrow_head(p: QPainter, tip: QPointF, angle_deg: float, size: float = 4.5):
    a = math.radians(angle_deg)
    for side in (-1, 1):
        b = a + math.pi + side * math.radians(35)
        p.drawLine(tip, QPointF(tip.x() + size * math.cos(b), tip.y() + size * math.sin(b)))


def _open(p):
    path = QPainterPath()
    path.moveTo(3, 7)
    path.lineTo(9, 7)
    path.lineTo(11, 9)
    path.lineTo(20, 9)
    path.lineTo(20, 19)
    path.lineTo(3, 19)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(3, 12), QPointF(20, 12))


def _save(p):
    path = QPainterPath()
    path.moveTo(4, 4)
    path.lineTo(17, 4)
    path.lineTo(20, 7)
    path.lineTo(20, 20)
    path.lineTo(4, 20)
    path.closeSubpath()
    p.drawPath(path)
    p.drawRect(QRectF(8, 4, 8, 5))
    p.drawRect(QRectF(7, 13, 10, 7))


def _save_as(p):
    _save(p)
    p.drawLine(QPointF(12, 14), QPointF(12, 19))
    _arrow_head(p, QPointF(12, 19), 90, 3)


def _curve_arrow(p, mirror: bool):
    path = QPainterPath()
    if not mirror:
        path.moveTo(7, 9)
        path.lineTo(15, 9)
        path.cubicTo(21, 9, 21, 19, 15, 19)
        path.lineTo(9, 19)
        p.drawPath(path)
        _arrow_head(p, QPointF(5, 9), 180)
        p.drawLine(QPointF(5, 9), QPointF(7, 9))
    else:
        path.moveTo(17, 9)
        path.lineTo(9, 9)
        path.cubicTo(3, 9, 3, 19, 9, 19)
        path.lineTo(15, 19)
        p.drawPath(path)
        _arrow_head(p, QPointF(19, 9), 0)
        p.drawLine(QPointF(17, 9), QPointF(19, 9))


def _rotate(p, clockwise: bool):
    rect = QRectF(5, 5, 14, 14)
    if clockwise:
        p.drawArc(rect, 90 * 16, -300 * 16)
        _arrow_head(p, QPointF(12, 5), 0, 4)
    else:
        p.drawArc(rect, 90 * 16, 300 * 16)
        _arrow_head(p, QPointF(12, 5), 180, 4)


def _print(p):
    p.drawRect(QRectF(7, 3, 10, 6))
    p.drawRoundedRect(QRectF(3, 9, 18, 8), 2, 2)
    p.drawRect(QRectF(7, 14, 10, 7))


def _triangle(p, pointing_right: bool, x0: float = 8, x1: float = 16):
    path = QPainterPath()
    if pointing_right:
        path.moveTo(x0, 6)
        path.lineTo(x1, 12)
        path.lineTo(x0, 18)
    else:
        path.moveTo(x1, 6)
        path.lineTo(x0, 12)
        path.lineTo(x1, 18)
    path.closeSubpath()
    p.fillPath(path, p.pen().color())


def _first(p):
    p.drawLine(QPointF(6, 6), QPointF(6, 18))
    _triangle(p, False, 8, 17)


def _last(p):
    p.drawLine(QPointF(18, 6), QPointF(18, 18))
    _triangle(p, True, 7, 16)


def _select(p):
    path = QPainterPath()
    path.moveTo(6, 3)
    path.lineTo(6, 19)
    path.lineTo(10, 15)
    path.lineTo(13, 21)
    path.lineTo(15, 20)
    path.lineTo(12, 14)
    path.lineTo(18, 14)
    path.closeSubpath()
    p.drawPath(path)


def _hand(p):
    for x, top in ((8, 7), (11, 4), (14, 5), (17, 8)):
        p.drawLine(QPointF(x, top), QPointF(x, 13))
    path = QPainterPath()
    path.moveTo(5, 12)
    path.lineTo(8, 16)
    path.cubicTo(8, 20, 10, 21, 13, 21)
    path.cubicTo(17, 21, 18, 18, 18, 14)
    path.lineTo(17, 8)
    p.drawPath(path)


def _text_select(p):
    p.drawLine(QPointF(12, 4), QPointF(12, 20))
    p.drawLine(QPointF(9, 4), QPointF(15, 4))
    p.drawLine(QPointF(9, 20), QPointF(15, 20))


def _highlight(p):
    path = QPainterPath()
    path.moveTo(14, 4)
    path.lineTo(19, 9)
    path.lineTo(11, 17)
    path.lineTo(6, 12)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(6, 12), QPointF(4, 17))
    p.drawLine(QPointF(4, 17), QPointF(8, 17))
    p.drawLine(QPointF(3, 21), QPointF(21, 21))


def _letter(p, char: str):
    font = p.font()
    font.setFamily("Segoe UI")
    font.setPixelSize(15)
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(0, 0, 24, 21), Qt.AlignmentFlag.AlignCenter, char)


def _underline(p):
    _letter(p, "U")
    p.drawLine(QPointF(6, 21), QPointF(18, 21))


def _strikethrough(p):
    _letter(p, "S")
    p.drawLine(QPointF(4, 11.5), QPointF(20, 11.5))


def _text_box(p):
    p.drawRect(QRectF(3, 4, 18, 16))
    p.drawLine(QPointF(8, 8), QPointF(16, 8))
    p.drawLine(QPointF(12, 8), QPointF(12, 16))


def _sticky_note(p):
    path = QPainterPath()
    path.moveTo(4, 4)
    path.lineTo(20, 4)
    path.lineTo(20, 15)
    path.lineTo(15, 20)
    path.lineTo(4, 20)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(15, 20), QPointF(15, 15))
    p.drawLine(QPointF(15, 15), QPointF(20, 15))
    p.drawLine(QPointF(8, 9), QPointF(16, 9))
    p.drawLine(QPointF(8, 13), QPointF(13, 13))


def _rectangle(p):
    p.drawRect(QRectF(4, 6, 16, 12))


def _circle(p):
    p.drawEllipse(QRectF(4, 4, 16, 16))


def _line(p):
    p.drawLine(QPointF(5, 19), QPointF(19, 5))


def _arrow(p):
    p.drawLine(QPointF(4, 12), QPointF(20, 12))
    _arrow_head(p, QPointF(20, 12), 0, 5)


def _freehand(p):
    path = QPainterPath()
    path.moveTo(17, 3)
    path.lineTo(21, 7)
    path.lineTo(9, 19)
    path.lineTo(4, 20)
    path.lineTo(5, 15)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(15, 5), QPointF(19, 9))


def _stamp(p):
    p.drawRoundedRect(QRectF(9, 3, 6, 8), 2, 2)
    p.drawLine(QPointF(12, 11), QPointF(12, 14))
    p.drawRoundedRect(QRectF(4, 14, 16, 4), 1, 1)
    p.drawLine(QPointF(5, 21), QPointF(19, 21))


_DRAW: dict[str, Draw] = {
    "open": _open,
    "save": _save,
    "save_as": _save_as,
    "undo": lambda p: _curve_arrow(p, False),
    "redo": lambda p: _curve_arrow(p, True),
    "rotate_ccw": lambda p: _rotate(p, False),
    "rotate_cw": lambda p: _rotate(p, True),
    "print": _print,
    "first": _first,
    "prev": lambda p: _triangle(p, False),
    "next": lambda p: _triangle(p, True),
    "last": _last,
    "select": _select,
    "hand": _hand,
    "text_select": _text_select,
    "highlight": _highlight,
    "underline": _underline,
    "strikethrough": _strikethrough,
    "text_box": _text_box,
    "sticky_note": _sticky_note,
    "rectangle": _rectangle,
    "circle": _circle,
    "line": _line,
    "arrow": _arrow,
    "freehand": _freehand,
    "stamp": _stamp,
}


class _DrawnIconEngine(QIconEngine):
    def __init__(self, draw: Draw):
        super().__init__()
        self._draw = draw

    def paint(self, painter: QPainter, rect, mode, state):
        from .theme import current_theme

        if state == QIcon.State.On:
            color = QColor("white")  # checked tool buttons have a blue fill
        elif mode == QIcon.Mode.Disabled:
            color = QColor("#9a9a9a")
        else:
            color = QColor("#e8e8e8" if current_theme() == "dark" else "#333333")
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(rect.x(), rect.y())
        painter.scale(rect.width() / 24.0, rect.height() / 24.0)
        pen = QPen(color, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        self._draw(painter)
        painter.restore()

    def pixmap(self, size: QSize, mode, state) -> QPixmap:
        pix = QPixmap(size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        self.paint(painter, pix.rect(), mode, state)
        painter.end()
        return pix

    def clone(self) -> "QIconEngine":
        return _DrawnIconEngine(self._draw)


def icon(name: str) -> QIcon:
    """The toolbar icon called ``name`` (see ``_DRAW``)."""
    return QIcon(_DrawnIconEngine(_DRAW[name]))


ICON_NAMES = tuple(_DRAW)
