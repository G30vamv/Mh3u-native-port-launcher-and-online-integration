"""
Widgets and dialogs for the launcher window (PySide6), with the small CTk-like API the launcher logic in core.py uses:
`configure(text=..., text_color=..., state=..., fg_color=..., hover_color=...)`, `get`/`set`/`select`, `insert`/`delete` on entries
and so on, plus message boxes and folder dialogs that can be called from any thread.
"""

import threading

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QWidget,
)

END = "end"

# Moga Village / Tanzia palette
GOLD = "#b8791e"
GOLD_HOVER = "#d4922a"
TEAL = "#2f9488"
TEAL_HOVER = "#257a70"
SLATE = "#2b4a58"
SLATE_HOVER = "#3b6073"
PARCHMENT = "#e3d8bd"
RED = "#e0675c"
RED_HOVER = "#a9493f"

# kind -> (background, hover, text)
BUTTON_KINDS = {
    "default": (SLATE, SLATE_HOVER, "#fff6e0"),
    "gold": (GOLD, GOLD_HOVER, "#fff6e0"),
    "teal": (TEAL, TEAL_HOVER, "#fff6e0"),
    "ember": ("#e08e4a", "#eab84c", "#0d1820"),
    "danger": (RED, RED_HOVER, "#fff6e0"),
    "good": ("#7fcfa6", "#9bdcbb", "#0d1820"),
    "link": ("#22414f", SLATE_HOVER, "#fff6e0"),
}


def tx(text):
    """Button text with & kept as an ampersand (Qt reads a single & as a shortcut mark)."""
    return str(text).replace("&", "&&")


class _MainThread(QObject):
    """Runs a function on the GUI thread and gives its result back to the thread that asked."""

    run = Signal(object)

    def __init__(self):
        super().__init__()
        self.run.connect(self._call, Qt.ConnectionType.BlockingQueuedConnection)

    def _call(self, box):
        try:
            box["result"] = box["fn"]()
        except Exception as e:  # shown by the caller
            box["error"] = e


_main = None
_main_ident = threading.main_thread().ident


def on_main(fn):
    global _main
    if threading.get_ident() == _main_ident:
        return fn()
    if _main is None:
        raise RuntimeError("the GUI is not running")
    box = {"fn": fn}
    _main.run.emit(box)
    if "error" in box:
        raise box["error"]
    return box.get("result")


def init_threading():
    """Call once from the GUI thread after the QApplication exists."""
    global _main
    _main = _MainThread()


def _box(kind, title, text, buttons=QMessageBox.StandardButton.Ok):
    def show():
        box = QMessageBox(kind, str(title), str(text), buttons)
        return box.exec()

    return on_main(show)


class messagebox:  # noqa: N801 - mirrors the tkinter module the logic was written for
    @staticmethod
    def showinfo(title, text):
        _box(QMessageBox.Icon.Information, title, text)

    @staticmethod
    def showwarning(title, text):
        _box(QMessageBox.Icon.Warning, title, text)

    @staticmethod
    def showerror(title, text):
        _box(QMessageBox.Icon.Critical, title, text)

    @staticmethod
    def askyesno(title, text):
        yes_no = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        return _box(QMessageBox.Icon.Question, title, text, yes_no) == QMessageBox.StandardButton.Yes


class filedialog:  # noqa: N801
    @staticmethod
    def askdirectory(title="", initialdir=""):
        return on_main(lambda: QFileDialog.getExistingDirectory(None, title, initialdir)) or ""


def font(size=None, bold=False, family=None, pixel=False):
    f = QFont(family or "Segoe UI")
    if size:
        f.setPointSizeF(size * 0.75 if pixel else size)
    f.setBold(bold)
    return f


class Label(QLabel):
    def __init__(self, text="", color=None, size=10.5, bold=False, family=None, wrap=0, parent=None):
        super().__init__(text, parent)
        self.setFont(font(size, bold, family))
        self._color = color or PARCHMENT
        self._paint_color()
        if wrap:
            self.setWordWrap(True)
            self.setMaximumWidth(wrap)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def _paint_color(self):
        self.setStyleSheet(f"color: {self._color}; background: transparent;")

    def configure(self, **kw):
        if "text" in kw:
            self.setText(str(kw["text"]))
        if "text_color" in kw:
            self._color = kw["text_color"]
            self._paint_color()


class Button(QPushButton):
    def __init__(self, text="", kind="default", command=None, width=None, height=34, size=10.5, bold=True, parent=None):
        super().__init__(tx(text), parent)
        self._fg, self._hover, self._tc = BUTTON_KINDS[kind]
        self._command = None
        self.setFont(font(size, bold))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(height)
        if width:
            self.setMinimumWidth(width)
        self.configure(command=command)
        self._restyle()

    def _restyle(self):
        self.setStyleSheet(
            f"""
            QPushButton {{ background: {self._fg}; color: {self._tc}; border: 1px solid rgba(255,255,255,40);
                          border-radius: 10px; padding: 4px 16px; }}
            QPushButton:hover {{ background: {self._hover}; border: 1px solid rgba(255,255,255,90); }}
            QPushButton:pressed {{ padding-top: 6px; }}
            QPushButton:disabled {{ background: rgba(60,80,90,150); color: rgba(227,216,189,110); border: 1px solid rgba(255,255,255,20); }}
            """
        )

    def configure(self, **kw):
        if "text" in kw:
            self.setText(tx(kw["text"]))
        if "state" in kw:
            self.setEnabled(kw["state"] != "disabled")
        if "fg_color" in kw:
            self._fg = kw["fg_color"]
        if "hover_color" in kw:
            self._hover = kw["hover_color"]
        if "text_color" in kw:
            self._tc = kw["text_color"]
        if "command" in kw:
            if self._command is not None:
                try:
                    self.clicked.disconnect(self._command)
                except (RuntimeError, TypeError):
                    pass
            command = kw["command"]
            self._command = (lambda checked=False, c=command: c()) if command else None
            if self._command:
                self.clicked.connect(self._command)
        if any(k in kw for k in ("fg_color", "hover_color", "text_color")):
            self._restyle()


class Entry(QLineEdit):
    def __init__(self, placeholder="", width=None, height=34, parent=None):
        super().__init__(parent)
        self.setFont(font(10.5))
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(height)
        if width:
            self.setFixedWidth(width)

    def get(self):
        return self.text()

    def delete(self, first=0, last=None):
        self.clear()

    def insert(self, index, text):
        self.setText(str(text))

    def on_change(self, fn):
        self.textEdited.connect(lambda _t: fn())


class _Toggle(QAbstractButton):
    """A check box or a switch; painted here so the palette and the glass look match."""

    def __init__(self, text="", command=None, switch=False, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setFont(font(10.5, bold=switch))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._switch = switch
        if command:
            self.clicked.connect(lambda checked=False: command())

    def get(self):
        return 1 if self.isChecked() else 0

    def select(self):
        self.setChecked(True)

    def deselect(self):
        self.setChecked(False)

    def sizeHint(self):
        box = 44 if self._switch else 22
        return QSize(box + 10 + self.fontMetrics().horizontalAdvance(self.text()) + 4, 28)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        hover = self.underMouse()
        y = (self.height() - 22) / 2
        if self._switch:
            track = QRectF(1, y + 2, 40, 18)
            p.setPen(QPen(QColor(255, 255, 255, 60), 1))
            p.setBrush(QColor(TEAL if on else "#1b3441"))
            p.drawRoundedRect(track, 9, 9)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#f2c968" if hover else "#eab84c"))
            x = 23 if on else 3
            p.drawEllipse(QRectF(x, y + 4, 14, 14))
            left = 52
        else:
            box = QRectF(1, y + 1, 20, 20)
            p.setPen(QPen(QColor(255, 255, 255, 110 if hover else 70), 1))
            p.setBrush(QColor(TEAL if on else "#0d1820"))
            p.drawRoundedRect(box, 6, 6)
            if on:
                pen = QPen(QColor("#fff6e0"), 2.2)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                path = QPainterPath()
                path.moveTo(QPointF(6, y + 11.5))
                path.lineTo(QPointF(9.5, y + 15))
                path.lineTo(QPointF(16, y + 7.5))
                p.drawPath(path)
            left = 32
        p.setPen(QColor(PARCHMENT))
        p.setFont(self.font())
        p.drawText(QRectF(left, 0, self.width() - left, self.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


def CheckBox(text="", command=None, parent=None):  # noqa: N802
    return _Toggle(text, command, switch=False, parent=parent)


def Switch(text="", command=None, parent=None):  # noqa: N802
    return _Toggle(text, command, switch=True, parent=parent)


class Segmented(QFrame):
    def __init__(self, values, command=None, parent=None, size=10.5, bold=False):
        super().__init__(parent)
        self.setObjectName("seg")
        self._command = command
        self._buttons = {}
        self._value = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        for v in values:
            b = QPushButton(tx(v))
            b.setCheckable(True)
            b.setFont(font(size, bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(30)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.clicked.connect(lambda checked=False, v=v: self._clicked(v))
            lay.addWidget(b)
            self._buttons[v] = b
        self.setStyleSheet(
            f"""
            #seg {{ background: rgba(8,20,28,170); border: 1px solid rgba(255,255,255,40); border-radius: 12px; }}
            #seg QPushButton {{ background: transparent; color: {PARCHMENT}; border: none; border-radius: 9px; padding: 4px 10px; }}
            #seg QPushButton:hover {{ background: rgba(255,255,255,26); }}
            #seg QPushButton:checked {{ background: {GOLD}; color: #fff6e0; }}
            #seg QPushButton:checked:hover {{ background: {GOLD_HOVER}; }}
            """
        )

    def set(self, value):
        self._value = value
        for v, b in self._buttons.items():
            b.setChecked(v == value)

    def get(self):
        return self._value

    def _clicked(self, value):
        self.set(value)
        if self._command:
            self._command(value)


class OptionMenu(QComboBox):
    def __init__(self, values, width=None, parent=None):
        super().__init__(parent)
        self.addItems(values)
        self.setFont(font(10.5))
        self.setMinimumHeight(34)
        if width:
            self.setFixedWidth(width)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def get(self):
        return self.currentText()

    def set(self, text):
        i = self.findText(text)
        if i >= 0:
            self.setCurrentIndex(i)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(PARCHMENT), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        cx, cy = self.width() - 18, self.height() / 2
        p.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2))
        p.drawLine(QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2))


class Slider(QSlider):
    def __init__(self, from_, to, command=None, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setRange(int(from_), int(to))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._command = command
        self.valueChanged.connect(self._changed)
        self._quiet = False

    def _changed(self, value):
        if self._command and not self._quiet:
            self._command(value)

    def set(self, value):
        self._quiet = True
        self.setValue(int(round(value)))
        self._quiet = False


class ProgressBar(QWidget):
    def __init__(self, height=10, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._value = 0.0

    def set(self, value):
        self._value = max(0.0, min(1.0, float(value)))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        radius = self.height() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(8, 20, 28, 190))
        p.drawRoundedRect(r, radius, radius)
        w = max(self.height(), self._value * self.width()) if self._value > 0 else self.height()
        p.setBrush(QColor("#eab84c"))
        p.drawRoundedRect(QRectF(0, 0, w, self.height()), radius, radius)


class LogBox(QPlainTextEdit):
    def __init__(self, height=150, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(font(9.5, family="Consolas"))
        self.setMinimumHeight(height)
        self.setObjectName("log")

    def insert(self, where, text):
        self.moveCursor(self.textCursor().MoveOperation.End)
        self.insertPlainText(text)

    def see(self, where):
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def delete(self, first, last=None):
        self.clear()


class TabView(QWidget):
    """A row of tab buttons over a stack of pages."""

    changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QVBoxLayout

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.bar = QFrame()
        self.bar.setObjectName("tabbar")
        self._bar_lay = QHBoxLayout(self.bar)
        self._bar_lay.setContentsMargins(5, 5, 5, 5)
        self._bar_lay.setSpacing(4)
        self.stack = QStackedWidget()
        lay.addWidget(self.bar, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.stack, 1)
        self._pages = {}
        self._buttons = {}
        self.bar.setStyleSheet(
            f"""
            #tabbar {{ background: rgba(8,20,28,170); border: 1px solid rgba(255,255,255,40); border-radius: 18px; }}
            #tabbar QPushButton {{ background: transparent; color: {PARCHMENT}; border: none; border-radius: 14px; padding: 6px 16px; }}
            #tabbar QPushButton:hover {{ background: rgba(255,255,255,26); }}
            #tabbar QPushButton:checked {{ background: {GOLD}; color: #fff6e0; }}
            """
        )

    def add(self, name, page):
        b = QPushButton(tx(name))
        b.setCheckable(True)
        b.setFont(font(10.5, bold=True))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda checked=False, n=name: self.set(n))
        self._bar_lay.addWidget(b)
        self.stack.addWidget(page)
        self._pages[name.strip()] = page
        self._buttons[name.strip()] = b
        if len(self._pages) == 1:
            self.set(name)

    def set(self, name):
        key = name.strip()
        if key not in self._pages:
            return
        self.stack.setCurrentWidget(self._pages[key])
        for k, b in self._buttons.items():
            b.setChecked(k == key)
        self.changed.emit(key)
