"""Controller picture and binding rows for the Controls tab (the interface the universal button mapping will use)."""

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

from qtshim import GOLD, PARCHMENT, TEAL, font

# Wii U Pro Controller layout, in a 0..1 box: name -> (x, y, kind)
BUTTONS = {
    "ZL": (0.20, 0.07, "trigger"),
    "L": (0.24, 0.17, "shoulder"),
    "ZR": (0.80, 0.07, "trigger"),
    "R": (0.76, 0.17, "shoulder"),
    "minus": (0.41, 0.34, "small"),
    "home": (0.50, 0.40, "home"),
    "plus": (0.59, 0.34, "small"),
    "up": (0.27, 0.53, "dpad"),
    "left": (0.21, 0.62, "dpad"),
    "right": (0.33, 0.62, "dpad"),
    "down": (0.27, 0.71, "dpad"),
    "X": (0.77, 0.30, "face"),
    "Y": (0.70, 0.40, "face"),
    "A": (0.84, 0.40, "face"),
    "B": (0.77, 0.50, "face"),
    "lstick": (0.30, 0.38, "stick"),
    "rstick": (0.68, 0.63, "stick"),
}

# the rows of the binding list: (group, [(id, label)])
GROUPS = [
    ("Botones", [("A", "A"), ("B", "B"), ("X", "X"), ("Y", "Y")]),
    ("Gatillos", [("L", "L"), ("R", "R"), ("ZL", "ZL"), ("ZR", "ZR")]),
    ("Sistema", [("plus", "+ (Start)"), ("minus", "− (Select)"), ("home", "Home")]),
    ("Cruceta", [("up", "Arriba"), ("down", "Abajo"), ("left", "Izquierda"), ("right", "Derecha")]),
    ("Sticks", [("lstick", "Stick izquierdo (pulsar)"), ("rstick", "Stick derecho (pulsar)")]),
]


class PadDiagram(QWidget):
    """A Wii U Pro Controller drawn in the palette; the selected or hovered button glows gold."""

    picked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(380)
        self.setFixedHeight(300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.active = None  # the button picked in the list
        self._hover = None

    def set_active(self, name):
        self.active = name
        self.update()

    def _box(self):
        # keep the controller's proportions inside the widget
        w, h = self.width(), self.height()
        ratio = 1.55
        bw = min(w, h * ratio)
        bh = bw / ratio
        return QRectF((w - bw) / 2, (h - bh) / 2, bw, bh)

    def _pos(self, name):
        b = self._box()
        x, y, _ = BUTTONS[name]
        return QPointF(b.x() + x * b.width(), b.y() + y * b.height())

    def _hit(self, point):
        b = self._box()
        for name, (_x, _y, kind) in BUTTONS.items():
            radius = b.width() * (0.045 if kind in ("face", "dpad", "small", "home") else 0.07)
            c = self._pos(name)
            if (c.x() - point.x()) ** 2 + (c.y() - point.y()) ** 2 <= radius * radius:
                return name
        return None

    def mouseMoveEvent(self, event):
        hit = self._hit(event.position())
        if hit != self._hover:
            self._hover = hit
            self.setCursor(Qt.CursorShape.PointingHandCursor if hit else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, _event):
        self._hover = None
        self.update()

    def mousePressEvent(self, event):
        hit = self._hit(event.position())
        if hit:
            self.picked.emit(hit)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        b = self._box()

        # body: a wide rounded shape with two grips
        body = QPainterPath()
        body.addRoundedRect(QRectF(b.x() + b.width() * 0.04, b.y() + b.height() * 0.22, b.width() * 0.92, b.height() * 0.46), b.height() * 0.2, b.height() * 0.2)
        for gx in (0.14, 0.86):
            grip = QPainterPath()
            grip.addEllipse(QPointF(b.x() + b.width() * gx, b.y() + b.height() * 0.62), b.width() * 0.115, b.height() * 0.30)
            body = body.united(grip)
        g = QRadialGradient(b.center().x(), b.y(), b.width() * 0.7)
        g.setColorAt(0, QColor(36, 78, 92, 230))
        g.setColorAt(1, QColor(10, 26, 34, 235))
        p.setBrush(g)
        p.setPen(QPen(QColor(220, 240, 245, 110), 1.2))
        p.drawPath(body)

        r = b.width()
        for name, (_x, _y, kind) in BUTTONS.items():
            c = self._pos(name)
            hot = name == self.active
            over = name == self._hover
            glow = hot or over
            if kind in ("face",):
                rad = r * 0.034
                fill = QColor(GOLD) if glow else QColor(20, 44, 56)
            elif kind == "stick":
                rad = r * 0.058
                fill = QColor(GOLD) if glow else QColor(8, 20, 28)
            elif kind == "dpad":
                rad = r * 0.027
                fill = QColor(GOLD) if glow else QColor(20, 44, 56)
            elif kind in ("small", "home"):
                rad = r * 0.02
                fill = QColor(GOLD) if glow else QColor(30, 60, 74)
            else:
                rad = r * 0.0
                fill = QColor(GOLD) if glow else QColor(30, 60, 74)
            if kind in ("shoulder", "trigger"):
                w, h = r * 0.15, r * 0.045
                rect = QRectF(c.x() - w / 2, c.y() - h / 2, w, h)
                p.setPen(QPen(QColor(235, 250, 252, 160 if glow else 90), 1))
                p.setBrush(fill)
                p.drawRoundedRect(rect, 6, 6)
            else:
                if glow:
                    halo = QRadialGradient(c, rad * 2.4)
                    halo.setColorAt(0, QColor(212, 146, 42, 150))
                    halo.setColorAt(1, QColor(212, 146, 42, 0))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(halo)
                    p.drawEllipse(c, rad * 2.4, rad * 2.4)
                p.setPen(QPen(QColor(235, 250, 252, 170 if glow else 90), 1.2))
                p.setBrush(fill)
                p.drawEllipse(c, rad, rad)
            label = {"minus": "−", "plus": "+", "home": "⌂", "lstick": "LS", "rstick": "RS", "up": "", "down": "", "left": "", "right": ""}.get(name, name)
            if label and kind not in ("shoulder", "trigger"):
                p.setPen(QColor("#0d1820" if glow and kind != "stick" else PARCHMENT))
                p.setFont(font(max(7, r * 0.022), bold=True))
                p.drawText(QRectF(c.x() - rad, c.y() - rad, rad * 2, rad * 2), Qt.AlignmentFlag.AlignCenter, label)
            elif kind in ("shoulder", "trigger"):
                p.setPen(QColor("#0d1820" if glow else PARCHMENT))
                p.setFont(font(max(7, r * 0.022), bold=True))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, name)
        # d-pad cross
        p.setPen(QPen(QColor(235, 250, 252, 50), 1))
        c = self._pos("up")
        d = self._pos("down")
        p.drawLine(c, d)
        p.drawLine(self._pos("left"), self._pos("right"))
        # teal rim light so it reads as part of the glass UI
        p.setPen(QPen(QColor(TEAL), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
