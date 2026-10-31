"""A title bar drawn inside the window (the window has no native frame), with the resize grips a framed window has."""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QWidget

from qtshim import GOLD, GOLD_HOVER, PARCHMENT, font

GRIP = 6  # width of the edges that resize the window


class _CaptionButton(QAbstractButton):
    """Minimize / maximize / close; turns palette gold under the mouse."""

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.maximized = False
        self.setFixedSize(46, 32)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        hot = self.underMouse()
        if hot:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(GOLD_HOVER if self.isDown() else GOLD))
            p.drawRoundedRect(QRectF(4, 3, self.width() - 8, self.height() - 6), 8, 8)
        pen = QPen(QColor("#fff6e0" if hot else PARCHMENT), 1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        if self.kind == "min":
            p.drawLine(QPointF(cx - 5, cy + 1), QPointF(cx + 5, cy + 1))
        elif self.kind == "max":
            if self.maximized:
                p.drawRect(QRectF(cx - 5, cy - 3, 7, 7))
                p.drawLine(QPointF(cx - 2, cy - 5), QPointF(cx + 5, cy - 5))
                p.drawLine(QPointF(cx + 5, cy - 5), QPointF(cx + 5, cy + 2))
            else:
                p.drawRect(QRectF(cx - 5, cy - 5, 10, 10))
        else:
            p.drawLine(QPointF(cx - 5, cy - 5), QPointF(cx + 5, cy + 5))
            p.drawLine(QPointF(cx - 5, cy + 5), QPointF(cx + 5, cy - 5))

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class TitleBar(QWidget):
    def __init__(self, window, title, icon_path=None):
        super().__init__(window)
        self._window = window
        self.setFixedHeight(38)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 8, 0)
        lay.setSpacing(8)
        if icon_path:
            icon = QLabel()
            icon.setPixmap(QIcon(icon_path).pixmap(QSize(18, 18)))
            icon.setStyleSheet("background: transparent;")
            lay.addWidget(icon)
        label = QLabel(title)
        label.setFont(font(10))
        label.setStyleSheet(f"color: {PARCHMENT}; background: transparent;")
        lay.addWidget(label)
        lay.addStretch(1)
        self.btn_min = _CaptionButton("min")
        self.btn_max = _CaptionButton("max")
        self.btn_close = _CaptionButton("close")
        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(self.toggle_maximized)
        self.btn_close.clicked.connect(window.close)
        for b in (self.btn_min, self.btn_max, self.btn_close):
            lay.addWidget(b)

    def toggle_maximized(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self.sync()

    def sync(self):
        self.btn_max.maximized = self._window.isMaximized()
        self.btn_max.update()

    def paintEvent(self, _event):
        # a little shade at the very top keeps the title readable over the artwork
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, QColor(4, 10, 14, 120))
        g.setColorAt(1.0, QColor(4, 10, 14, 0))
        p.fillRect(self.rect(), g)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._window.isMaximized():
            handle = self._window.windowHandle()
            if handle:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()


class _Grip(QWidget):
    def __init__(self, window, edges, cursor):
        super().__init__(window)
        self._window = window
        self._edges = edges
        self.setCursor(cursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._window.isMaximized():
            handle = self._window.windowHandle()
            if handle:
                handle.startSystemResize(self._edges)


def install_grips(window):
    """Invisible strips along the edges and corners that start a native resize; call `place_grips` on resize."""
    edge = Qt.Edge
    cur = Qt.CursorShape
    specs = [
        ("l", edge.LeftEdge, cur.SizeHorCursor),
        ("r", edge.RightEdge, cur.SizeHorCursor),
        ("t", edge.TopEdge, cur.SizeVerCursor),
        ("b", edge.BottomEdge, cur.SizeVerCursor),
        ("tl", edge.TopEdge | edge.LeftEdge, cur.SizeFDiagCursor),
        ("br", edge.BottomEdge | edge.RightEdge, cur.SizeFDiagCursor),
        ("tr", edge.TopEdge | edge.RightEdge, cur.SizeBDiagCursor),
        ("bl", edge.BottomEdge | edge.LeftEdge, cur.SizeBDiagCursor),
    ]
    window._grips = {name: _Grip(window, edges, cursor) for name, edges, cursor in specs}


def place_grips(window):
    w, h, g = window.width(), window.height(), GRIP
    on = not window.isMaximized()
    c = 14  # corner size
    geo = {
        "l": (0, c, g, h - 2 * c),
        "r": (w - g, c, g, h - 2 * c),
        "t": (c, 0, w - 2 * c, g),
        "b": (c, h - g, w - 2 * c, g),
        "tl": (0, 0, c, c),
        "tr": (w - c, 0, c, c),
        "bl": (0, h - c, c, c),
        "br": (w - c, h - c, c, c),
    }
    for name, grip in window._grips.items():
        grip.setGeometry(*geo[name])
        grip.setVisible(on)
        grip.raise_()
