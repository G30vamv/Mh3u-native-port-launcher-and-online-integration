"""Windows 11 window effects through DWM: dark title bar in the palette, rounded corners and, optionally, the Acrylic backdrop."""

import ctypes
import os
import sys

# DwmSetWindowAttribute ids
_DARK_MODE = 20
_CORNERS = 33
_BORDER_COLOR = 34
_CAPTION_COLOR = 35
_TEXT_COLOR = 36
_SYSTEM_BACKDROP = 38
_ACRYLIC = 3  # DWMSBT_TRANSIENTWINDOW


class _Margins(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int), ("right", ctypes.c_int), ("top", ctypes.c_int), ("bottom", ctypes.c_int)]


class _Accent(ctypes.Structure):
    _fields_ = [("state", ctypes.c_int), ("flags", ctypes.c_int), ("color", ctypes.c_uint), ("anim", ctypes.c_int)]


class _CompositionData(ctypes.Structure):
    _fields_ = [("attr", ctypes.c_int), ("data", ctypes.c_void_p), ("size", ctypes.c_size_t)]


def blur_behind(hwnd, tint_abgr=0x66100A06):
    """Acrylic blur of whatever is behind the window (works on Windows 10 1803+ and 11); the tint is AABBGGRR."""
    accent = _Accent(4, 2, tint_abgr, 0)  # ACCENT_ENABLE_ACRYLICBLURBEHIND
    data = _CompositionData(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))  # WCA_ACCENT_POLICY
    ctypes.windll.user32.SetWindowCompositionAttribute(int(hwnd), ctypes.byref(data))


def acrylic_available():
    return sys.platform == "win32" and getattr(sys, "getwindowsversion", None) is not None and sys.getwindowsversion().build >= 22621


def _bgr(r, g, b):
    return (b << 16) | (g << 8) | r


def style_window(hwnd, acrylic=False):
    """Returns True when the Acrylic backdrop was turned on."""
    if sys.platform != "win32":
        return False
    try:
        dwm = ctypes.windll.dwmapi

        def attr(which, value):
            v = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(int(hwnd), which, ctypes.byref(v), ctypes.sizeof(v))

        attr(_DARK_MODE, 1)
        attr(_CORNERS, 2)
        attr(_CAPTION_COLOR, _bgr(0x0A, 0x13, 0x1A))
        attr(_BORDER_COLOR, _bgr(0x2B, 0x4A, 0x58))
        attr(_TEXT_COLOR, _bgr(0xE3, 0xD8, 0xBD))
        if acrylic and acrylic_available():
            if os.environ.get("MH3U_ACRYLIC_API") == "dwm":
                attr(_SYSTEM_BACKDROP, _ACRYLIC)
                dwm.DwmExtendFrameIntoClientArea(int(hwnd), ctypes.byref(_Margins(-1, -1, -1, -1)))
            else:
                blur_behind(hwnd)
            return True
        # a window without a native frame gets its shadow from a 1 px frame extension
        dwm.DwmExtendFrameIntoClientArea(int(hwnd), ctypes.byref(_Margins(1, 1, 1, 1)))
    except Exception:
        pass
    return False
