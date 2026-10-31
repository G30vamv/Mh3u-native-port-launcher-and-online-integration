"""
Glass look for the launcher window (PySide6).

The window is painted over a backdrop made from the launcher's own artwork (the Moga Village scene), darkened and tinted
in the palette. Each `GlassPanel` shows, behind its content, the part of a blurred copy of that backdrop that lies under it,
with a tint, a light sheen and a thin light border: the same frosted-glass look as the reference, drawn here with real
alpha, so the labels and buttons placed on a panel are transparent and need no matching colours.
"""

import os

from PIL import Image, ImageChops, ImageFilter
from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QWidget

NAVY = (10, 19, 26)

# the soft palette glows the backdrop is lit with
_BASE_TOP = (13, 30, 40)
_BASE_BOTTOM = (7, 15, 22)
# (colour, centre x, centre y, radius as a share of the width, strength)
_GLOWS = [
    ((47, 148, 136), 0.10, 0.05, 0.55, 0.62),  # teal
    ((184, 121, 30), 0.96, 0.92, 0.50, 0.55),  # gold
    ((79, 195, 214), 0.80, 0.12, 0.34, 0.30),  # cyan
    ((43, 74, 88), 0.28, 0.80, 0.48, 0.55),  # slate blue
]


def _falloff(v):
    """The radial gradient reaches 181 at the middle of its edges (255 only at the corners): scale it so the glow is
    exactly zero at its edge (no visible square), and ease it out."""
    t = max(0.0, 1.0 - v / 181.0)
    return int(255 * t * t * (3 - 2 * t))


def build_backdrop(width, height, boost=1.0):
    """The window's backdrop: a dark gradient with soft coloured glows, with a little noise against banding."""
    width, height = max(width, 64), max(height, 64)
    sw, sh = max(width // 6, 32), max(height // 6, 32)
    column = Image.linear_gradient("L").resize((1, sh), Image.BILINEAR)
    column = column.resize((sw, sh), Image.NEAREST)
    base = Image.merge(
        "RGB",
        [ImageChops.add(Image.new("L", (sw, sh), _BASE_BOTTOM[i]), column.point(lambda v, i=i: int((_BASE_TOP[i] - _BASE_BOTTOM[i]) * (255 - v) / 255)))
         for i in range(3)],
    )
    glow = Image.radial_gradient("L").point(_falloff).resize((256, 256), Image.BILINEAR)
    for colour, cx, cy, radius, strength in _GLOWS:
        size = max(int(radius * 2 * sw), 8)
        blob = glow.resize((size, size), Image.BILINEAR).point(lambda v, s=min(strength * boost, 1.0): int(v * s))
        layer = Image.new("RGB", (sw, sh), (0, 0, 0))
        layer.paste(Image.new("RGB", (size, size), colour), (int(cx * sw - size / 2), int(cy * sh - size / 2)), blob)
        mask = Image.new("L", (sw, sh), 0)
        mask.paste(blob, (int(cx * sw - size / 2), int(cy * sh - size / 2)))
        base = Image.composite(layer, base, mask)
    big = base.resize((width, height), Image.BICUBIC)
    noise = Image.effect_noise((width, height), 5).convert("RGB")
    return ImageChops.add(big, noise, 1.0, -128)

# level -> (tint rgba, border strength, sheen strength)
LEVELS = {
    "panel": ((9, 24, 32, 70), 0.55, 0.07),
    "card": ((16, 42, 54, 50), 0.60, 0.10),
    "inset": ((5, 14, 20, 105), 0.35, 0.04),
    "accent": ((22, 66, 74, 58), 0.65, 0.11),
    "bar": ((7, 18, 25, 80), 0.50, 0.06),
}


def _to_pixmap(image, dpr):
    data = image.tobytes("raw", "RGB")
    q = QImage(data, image.width, image.height, image.width * 3, QImage.Format.Format_RGB888).copy()
    pix = QPixmap.fromImage(q)
    pix.setDevicePixelRatio(dpr)
    return pix


def build_images(art_path, width, height):
    """(sharp, blurred) PIL images of the backdrop at width x height."""
    width, height = max(width, 64), max(height, 64)
    glow = build_backdrop(width, height, boost=1.0 if art_path else 1.7)
    if art_path and os.path.exists(art_path):
        art = Image.open(art_path).convert("RGB")
        scale = max(width / art.width, height / art.height)
        art = art.resize((max(int(art.width * scale), width), max(int(art.height * scale), height)), Image.BICUBIC)
        left, top = (art.width - width) // 2, (art.height - height) // 4
        art = art.crop((left, top, left + width, top + height)).filter(ImageFilter.GaussianBlur(1.2))
        art = Image.blend(art, Image.new("RGB", art.size, NAVY), 0.34)
        sharp = ImageChops.screen(art, glow)
    else:
        sharp = glow
    # darker towards the bottom, where the footer sits
    fade = Image.linear_gradient("L").resize((1, height)).resize((width, height))
    sharp = Image.composite(sharp, Image.new("RGB", sharp.size, NAVY), fade.point(lambda v: 255 - v // 3))
    small = sharp.resize((max(width // 4, 1), max(height // 4, 1)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(9))
    blur = small.resize((width, height), Image.BICUBIC)
    blur = Image.blend(blur, Image.new("RGB", blur.size, (170, 215, 225)), 0.05)
    return sharp, blur


class Backdrop(QObject):
    """The picture behind the window: `sharp` for the window itself, `blur` for what shows through the glass."""

    changed = Signal()

    def __init__(self, art_path):
        super().__init__()
        self.art_path = art_path
        self.sharp = None
        self.blur = None
        self._size = (0, 0, 1.0)

    def build(self, width, height, dpr):
        key = (width, height, dpr)
        if key == self._size:
            return
        self._size = key
        sharp, blur = build_images(self.art_path, int(width * dpr), int(height * dpr))
        self.sharp = _to_pixmap(sharp, dpr)
        self.blur = _to_pixmap(blur, dpr)
        self.changed.emit()


BACKDROP = None  # the BackdropWidget of the window
SEE_THROUGH = False  # Acrylic on: panels let part of the desktop material through


class BackdropWidget(QWidget):
    """Fills the window with the backdrop; every other widget lives inside it."""

    def __init__(self, art_path, parent=None, opacity=1.0):
        super().__init__(parent)
        self.opacity = opacity  # below 1 lets the Acrylic material behind the window show through
        global BACKDROP
        BACKDROP = self
        self.backdrop = Backdrop(art_path)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._rebuild)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, opacity >= 1.0)
        self.backdrop.changed.connect(self.update)

    def _rebuild(self):
        self.backdrop.build(self.width(), self.height(), self.devicePixelRatioF())

    def showEvent(self, event):
        super().showEvent(event)
        if self.backdrop.sharp is None:
            self._rebuild()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # until the new backdrop is ready the old one is stretched
        self._timer.start(90)

    def paintEvent(self, _event):
        p = QPainter(self)
        if self.opacity < 1.0:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.fillRect(self.rect(), Qt.GlobalColor.transparent)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setOpacity(self.opacity)
        if self.backdrop.sharp is not None:
            p.drawPixmap(self.rect(), self.backdrop.sharp)
        else:
            p.fillRect(self.rect(), QColor(*NAVY))


class GlassPanel(QFrame):
    """A pane of frosted glass. Put the content in a layout on it."""

    def __init__(self, level="card", radius=16, parent=None):
        super().__init__(parent)
        self.level = level
        self.radius = radius
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def paint_extra(self, p):
        """Subclasses paint here: over the tint, under the sheen and the border (already clipped to the pane)."""

    # frame-like helpers the launcher logic uses on the online panels
    def grid(self, **_kw):
        self.show()

    def grid_remove(self):
        self.hide()

    def paintEvent(self, _event):
        tint, border, sheen = LEVELS[self.level]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(r, self.radius, self.radius)
        p.setClipPath(path)

        # what is behind the pane, blurred
        back = BACKDROP.backdrop.blur if BACKDROP is not None else None
        if back is not None:
            origin = self.mapTo(BACKDROP, QPoint(0, 0))
            k = back.devicePixelRatio()  # the source is in the pixmap's own pixels
            if SEE_THROUGH:
                p.setOpacity(0.62)
            p.drawPixmap(
                QRectF(0, 0, self.width(), self.height()),
                back,
                QRectF(origin.x() * k, origin.y() * k, self.width() * k, self.height() * k),
            )
        p.setOpacity(1.0)
        p.fillRect(self.rect(), QColor(tint[0], tint[1], tint[2], min(255, int(tint[3] * (1.2 if SEE_THROUGH else 1.0)))))

        self.paint_extra(p)

        # light from the top, fading out well before the middle so the text area stays calm
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, QColor(255, 255, 255, int(255 * sheen * 1.6)))
        g.setColorAt(0.35, QColor(255, 255, 255, int(255 * sheen * 0.35)))
        g.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(self.rect(), g)
        p.setClipping(False)

        # border: bright on the top left, dim on the bottom right
        bg = QLinearGradient(0, 0, self.width(), self.height())
        bg.setColorAt(0.0, QColor(235, 250, 252, int(255 * border * 0.85)))
        bg.setColorAt(0.5, QColor(200, 230, 236, int(255 * border * 0.28)))
        bg.setColorAt(1.0, QColor(200, 230, 236, int(255 * border * 0.45)))
        p.setPen(QPen(bg, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # a faint line of light just inside the top edge
        hl = QLinearGradient(self.radius, 0, self.width() - self.radius, 0)
        hl.setColorAt(0.0, QColor(255, 255, 255, 0))
        hl.setColorAt(0.5, QColor(255, 255, 255, int(255 * border * 0.35)))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(QPen(hl, 1))
        p.drawLine(QPointF(self.radius, 1.5), QPointF(self.width() - self.radius, 1.5))


class BannerPanel(GlassPanel):
    """A pane with the game's banner as its background on the left, fading out into the glass."""

    def __init__(self, banner_path, level="card", radius=16, reach=0.46, parent=None):
        super().__init__(level, radius, parent)
        self._source = QPixmap(banner_path) if banner_path and os.path.exists(banner_path) else None
        self._reach = reach  # how much of the width the picture covers before it has faded away
        self._cache = None
        self._cache_key = None

    def _faded(self):
        dpr = self.devicePixelRatioF()
        w, h = int(min(self.width() * self._reach, 560) * dpr), int(self.height() * dpr)
        key = (w, h)
        if key == self._cache_key:
            return self._cache
        pic = self._source.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        pic = pic.copy((pic.width() - w) // 2, (pic.height() - h) // 2, w, h)
        out = QPixmap(w, h)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.drawPixmap(0, 0, pic)
        # fully visible on the left, gone at the right edge of the picture
        fade = QLinearGradient(0, 0, w, 0)
        fade.setColorAt(0.0, QColor(0, 0, 0, 255))
        fade.setColorAt(0.35, QColor(0, 0, 0, 215))
        fade.setColorAt(0.7, QColor(0, 0, 0, 80))
        fade.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        p.fillRect(out.rect(), fade)
        p.end()
        out.setDevicePixelRatio(dpr)
        self._cache, self._cache_key = out, key
        return out

    def paint_extra(self, p):
        if self._source is None or self._source.isNull():
            return
        pic = self._faded()
        p.drawPixmap(0, 0, pic)
        # a little shade under the picture keeps the glass look at its edge
        shade = QLinearGradient(0, 0, 0, self.height())
        shade.setColorAt(0.0, QColor(5, 12, 18, 0))
        shade.setColorAt(1.0, QColor(5, 12, 18, 70))
        p.fillRect(QRectF(0, 0, pic.width() / pic.devicePixelRatio(), self.height()), shade)
