"""
Monster Hunter 3 Ultimate - PC Native Port Launcher
Author: g30wolff99
The launcher window (PySide6, glass look). What the launcher does lives in core.py.
"""

import os
import queue
import sys
import threading
import webbrowser

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import qtshim
import qtmapping
import qttitle
import winfx
from core import (
    APP_VERSION,
    DEFAULT_OUT_DIR,
    LauncherLogic,
    get_assets_dir,
    get_hunter_name_from_save,
    get_local_ip_addresses,
    updater,
)
import qtglass
from qtglass import BackdropWidget, BannerPanel, GlassPanel
from qtshim import (
    CheckBox,
    Button,
    Entry,
    Label,
    LogBox,
    OptionMenu,
    ProgressBar,
    Segmented,
    Slider,
    Switch,
    TabView,
    font,
)

TAB_MAIN = "🎮 Principal"
TAB_INSTALL = "⚙️ Instalación & Dump"
TAB_SETTINGS = "🛠️ Configuración Gráfica"
TAB_CONTROLS = "🕹️ Controles y Mandos"
TAB_ONLINE = "🌐 Modo Online (Beta)"
TAB_TOOLS = "💾 Partidas & Logs"

STYLE = """
* { font-family: "Segoe UI"; }
QToolTip { background: #0d1820; color: #e3d8bd; border: 1px solid #2b4a58; padding: 4px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(120,170,185,110); border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(212,146,42,200); }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QLineEdit { background: rgba(6,15,21,185); color: #fff6e0; border: 1px solid rgba(255,255,255,45);
            border-radius: 9px; padding: 4px 10px; selection-background-color: #2f9488; }
QLineEdit:focus { border: 1px solid #d4922a; }
QComboBox { background: rgba(6,15,21,185); color: #fff6e0; border: 1px solid rgba(255,255,255,45);
            border-radius: 9px; padding: 4px 34px 4px 10px; }
QComboBox:hover { border: 1px solid #d4922a; }
QComboBox::drop-down { border: none; width: 0; }
QComboBox QAbstractItemView { background: #0d1820; color: #e3d8bd; border: 1px solid #2b4a58;
            selection-background-color: #b8791e; selection-color: #fff6e0; outline: none; }
QSlider::groove:horizontal { height: 6px; background: rgba(6,15,21,200); border-radius: 3px; }
QSlider::sub-page:horizontal { background: #2f9488; border-radius: 3px; }
QSlider::handle:horizontal { background: #eab84c; width: 16px; margin: -6px 0; border-radius: 8px; }
QSlider::handle:horizontal:hover { background: #f2c968; }
QPlainTextEdit#log { background: rgba(5,12,17,205); color: #cfe3e6; border: 1px solid rgba(255,255,255,40);
            border-radius: 10px; padding: 6px; selection-background-color: #2f9488; }
QMessageBox, QDialog { background: #10202a; }
QMessageBox QLabel { color: #e3d8bd; }
QMessageBox QPushButton { background: #2b4a58; color: #fff6e0; border: 1px solid rgba(255,255,255,40);
            border-radius: 8px; padding: 6px 18px; min-width: 70px; }
QMessageBox QPushButton:hover { background: #b8791e; }
"""


def _transparent_scroll(inner):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.viewport().setAutoFillBackground(False)
    inner.setAutoFillBackground(False)
    area.setWidget(inner)
    return area


def _card(level="card", radius=16):
    panel = GlassPanel(level, radius)
    lay = QVBoxLayout(panel)
    lay.setContentsMargins(18, 14, 18, 14)
    lay.setSpacing(8)
    return panel, lay


def _grid_card(level="card", radius=16):
    panel = GlassPanel(level, radius)
    grid = QGridLayout(panel)
    grid.setContentsMargins(18, 14, 18, 14)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(8)
    return panel, grid


def _hint(text, color="#9db3ba", size=9.5):
    return Label(text, color, size, wrap=0)


class Window(QWidget):
    def __init__(self, app):
        super().__init__()
        self._app = app
        # no native frame: the title bar is drawn inside the window (qttitle)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowSystemMenuHint
        )
        qttitle.install_grips(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        qttitle.place_grips(self)

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self._app, "titlebar"):
            self._app.titlebar.sync()
            qttitle.place_grips(self)

    def closeEvent(self, event):
        self._app.on_app_close()
        event.accept()


class MH3ULauncherApp(LauncherLogic):
    def __init__(self, qapp):
        self.qapp = qapp
        self.assets_dir = get_assets_dir()
        self.config = self.load_config()
        self.is_compiling = False
        self.is_running = False
        self.is_downloading_toolchain = False
        self.game_process = None
        self.ui_queue = queue.Queue()
        self.server_process = None

        self.window = Window(self)
        self.window.setWindowTitle(f"Monster Hunter 3 Ultimate - PC Port Launcher {APP_VERSION}")
        icon_path = os.path.join(self.assets_dir, "app_icon.ico")
        if os.path.exists(icon_path):
            self.window.setWindowIcon(QIcon(icon_path))
        self.window.resize(1180, 840)
        self.window.setMinimumSize(980, 680)

        self.acrylic = bool(self.config.get("acrylic", False)) and winfx.acrylic_available()
        if self.acrylic:
            self.window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.backdrop = BackdropWidget(None, self.window, opacity=0.50 if self.acrylic else 1.0)
        qtglass.SEE_THROUGH = self.acrylic
        outer = QVBoxLayout(self.window)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.backdrop)
        self.build_ui()

        self.poll = QTimer()
        self.poll.timeout.connect(self._process_ui_queue)
        self.poll.start(50)
        self.refresh_status()
        if updater and self.config.get("auto_check_updates", True):
            QTimer.singleShot(4000, lambda: self.check_for_updates(silent=True))

    # ---- what the logic expects from a window -------------------------------------------------
    def after(self, ms, fn):
        if threading.current_thread() is threading.main_thread():
            QTimer.singleShot(ms, fn)
        else:
            self.ui_queue.put(("call", (ms, fn)))

    def destroy(self):
        self.poll.stop()
        self.window.hide()
        self.qapp.quit()

    def clipboard_clear(self):
        self.qapp.clipboard().clear()

    def clipboard_append(self, text):
        self.qapp.clipboard().setText(text)

    def show(self):
        self.window.show()
        # the window handle exists once it is shown
        winfx.style_window(self.window.winId(), self.acrylic)

    def on_acrylic_toggled(self):
        self.config["acrylic"] = bool(self.chk_acrylic.get())
        self.save_config()
        qtshim.messagebox.showinfo("Efecto Acrylic", "El cambio se aplicará la próxima vez que abras el launcher.")

    # ---- messages from other threads -----------------------------------------------------------
    def _process_ui_queue(self):
        try:
            while not self.ui_queue.empty():
                kind, data = self.ui_queue.get_nowait()
                if kind == "log":
                    self.txt_log.insert("end", data + "\n")
                    self.txt_log.see("end")
                elif kind == "server_log":
                    self.txt_server_log.insert("end", data + "\n")
                    self.txt_server_log.see("end")
                elif kind == "server_status":
                    self.lbl_server_status.configure(**data)
                elif kind == "ping_result":
                    success, elapsed_ms, detail = data
                    self._on_ping_result(success, elapsed_ms, detail)
                elif kind == "progress":
                    self.progress_bar.set(data)
                elif kind == "btn_compile":
                    self.btn_compile_action.configure(**data)
                elif kind == "btn_download":
                    self.btn_download_toolchain.configure(**data)
                elif kind == "tab":
                    self.tabview.set(data)
                elif kind == "refresh":
                    self.refresh_status()
                elif kind == "info":
                    qtshim.messagebox.showinfo(data[0], data[1])
                elif kind == "error":
                    qtshim.messagebox.showerror(data[0], data[1])
                elif kind == "warning":
                    qtshim.messagebox.showwarning(data[0], data[1])
                elif kind == "update_state":
                    self.lbl_update_status.configure(**data)
                elif kind == "update_btn":
                    self.btn_update.configure(**data)
                elif kind == "update_prompt":
                    self._prompt_update(*data)
                elif kind == "call":
                    ms, fn = data
                    QTimer.singleShot(ms, fn)
        except Exception as e:
            print(f"UI Queue error: {e}")

    # ---- window --------------------------------------------------------------------------------
    def build_ui(self):
        root = QVBoxLayout(self.backdrop)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        icon_path = os.path.join(self.assets_dir, "app_icon.ico")
        self.titlebar = qttitle.TitleBar(
            self.window,
            f"Monster Hunter 3 Ultimate - PC Port Launcher {APP_VERSION}",
            icon_path if os.path.exists(icon_path) else None,
        )
        root.addWidget(self.titlebar)

        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(20, 2, 20, 12)
        content_lay.setSpacing(12)
        root.addWidget(content, 1)
        content_lay.addWidget(self.create_header())

        self.tabview = TabView()
        content_lay.addWidget(self.tabview, 1)

        self.tabview.add(TAB_MAIN, self.setup_tab_main())
        self.tabview.add(TAB_INSTALL, self.setup_tab_install())
        self.tabview.add(TAB_SETTINGS, self.setup_tab_settings())
        self.tabview.add(TAB_CONTROLS, self.setup_tab_controls())
        self.tabview.add(TAB_ONLINE, self.setup_tab_online())
        self.tabview.add(TAB_TOOLS, self.setup_tab_tools())

        content_lay.addWidget(self.create_footer())

    def create_header(self):
        header = BannerPanel(os.path.join(self.assets_dir, "banner.png"), "card", 20)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(330, 14, 18, 14)
        lay.setSpacing(16)

        text = QVBoxLayout()
        text.setSpacing(2)
        title = Label("MONSTER HUNTER 3 ULTIMATE", "#f2b94b", 24, bold=True, family="Georgia")
        sub = Label(
            f"PC Native Port Launcher {APP_VERSION} • Vulkan / DX12 / LTO • Puerto Tanzia", "#b9ccd2", 11
        )
        text.addWidget(title)
        text.addWidget(sub)
        lay.addLayout(text, 1)

        badge = GlassPanel("inset", 14)
        blay = QVBoxLayout(badge)
        blay.setContentsMargins(14, 8, 14, 8)
        blay.setSpacing(4)
        blay.addWidget(Label(f"🛠️ Versión {APP_VERSION}", "#eab84c", 10, bold=True), 0, Qt.AlignmentFlag.AlignHCenter)
        if updater:
            self.btn_update = Button("⟳  Buscar actualizaciones", "teal", self.on_update_button, width=200, height=30, size=10)
            self.lbl_update_status = Label("", "#9db3ba", 9.5)
            self.lbl_update_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_update_status.setWordWrap(True)
            self.lbl_update_status.setFixedWidth(200)
            blay.addWidget(self.btn_update)
            blay.addWidget(self.lbl_update_status)
        lay.addWidget(badge)
        return header

    def create_footer(self):
        """Credits line straight on the background, with no pane behind it."""
        footer = QWidget()
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.addWidget(Label(f"Monster Hunter 3 Ultimate (Wii U) • Recompilación Nativa para PC | {APP_VERSION}", "#a9bec6", 9.5))
        lay.addStretch(1)
        lay.addWidget(Label("Launcher desarrollado por g30wolff99", "#e3d8bd", 9.5, bold=True))
        return footer

    # ---- tab 1 ---------------------------------------------------------------------------------
    def setup_tab_main(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(12)

        status, sg = _grid_card("card")
        sg.addWidget(Label("ESTADO DEL JUEGO:", None, 11, bold=True), 0, 0)
        self.lbl_main_status = Label("Verificando instalación...", "#eab84c", 11, bold=True)
        sg.addWidget(self.lbl_main_status, 0, 1)
        sg.addWidget(Label("MODO ONLINE:", None, 10.5, bold=True), 1, 0)
        self.lbl_main_online_status = Label("Comprobando...", "#e3d8bd", 10.5, bold=True)
        sg.addWidget(self.lbl_main_online_status, 1, 1)
        sg.setColumnStretch(1, 1)
        lay.addWidget(status)

        self.btn_play = Button("⚔️  JUGAR MONSTER HUNTER 3 ULTIMATE", "teal", self.launch_game, height=64, size=16)
        lay.addWidget(self.btn_play)

        row = QHBoxLayout()
        row.setSpacing(12)
        quick, ql = _card("card")
        ql.addWidget(Label("Ajustes Rápidos Activos", "#4fc3d6", 11.5, bold=True))
        # the logic updates these labels when a setting changes; the panel below shows the same, and more
        self.lbl_quick_scale = Label("")
        self.lbl_quick_pad = Label("")
        self.lbl_quick_mods = Label("")
        self.lbl_quick_backend = Label("")
        self.lbl_quick_online = Label("Online: Comprobando...")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(9)
        self._quick_items = [
            ("scale", "Resolución interna"), ("upscaler", "Reescalado"), ("present", "VSync"), ("backend", "API gráfica"),
            ("window", "Pantalla"), ("fps", "Contador de FPS"), ("input", "Entrada"), ("layout", "Disposición del mando"),
            ("sens", "Sensibilidad de cámara"), ("mods", "Mods nativos"), ("audio", "Audio"), ("lto", "Compilación LTO"),
            ("online", "Online"), ("discord", "Discord Rich Presence"),
        ]
        self._quick_labels = {}
        self._quick_last = {}
        for i, (key, name) in enumerate(self._quick_items):
            r, c = divmod(i, 2)
            grid.addWidget(Label(name, "#9db3ba", 10), r, c * 2)
            value = Label("", "#e3d8bd", 10, bold=True)
            value.setWordWrap(True)
            grid.addWidget(value, r, c * 2 + 1)
            self._quick_labels[key] = value
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        ql.addLayout(grid)
        ql.addStretch(1)
        row.addWidget(quick, 3)
        self.quick_timer = QTimer()
        self.quick_timer.timeout.connect(self.refresh_quick)
        self.quick_timer.start(400)
        QTimer.singleShot(0, self.refresh_quick)

        actions, al = _card("card")
        al.addWidget(Label("Acciones Frecuentes", "#4fc3d6", 11.5, bold=True))
        al.addWidget(Button("📦 Seleccionar / Cambiar Carpeta del Dump", "default", lambda: self.tabview.set(TAB_INSTALL)))
        al.addWidget(Button("🔨 Recompilar Librería del Juego", "default", self.start_build_process))
        al.addWidget(Button("📂 Abrir Carpeta de Guardado", "default", self.open_save_folder))
        al.addWidget(Label("¿Juegas con mando o teclado?"))
        self.opt_keyboard = Segmented(["Mando", "Teclado"], self.on_keyboard_changed)
        self.opt_keyboard.set("Teclado" if self.config.get("keyboard_controls", True) else "Mando")
        al.addWidget(self.opt_keyboard)
        row.addWidget(actions, 2)
        lay.addLayout(row, 1)

        tip, tl = _grid_card("inset", 14)
        tl.addWidget(Label("💡", None, 16), 0, 0)
        text = Label(
            "Consejo para Puerto Tanzia (Offline): Para jugar las misiones de la taberna (Rango Bajo, Alto y G) en solitario, "
            "habla con el marinero del barco y elige 'Puerto Tanzia -> Individual -> Marina o Taberna'. "
            "No selecciones 'Multijugador' si estás jugando sin conexión.",
            "#e3d8bd",
            10,
        )
        text.setWordWrap(True)
        tl.addWidget(text, 0, 1)
        tl.setColumnStretch(1, 1)
        lay.addWidget(tip)
        return page

    def refresh_quick(self):
        """Read-only summary of the launcher's main settings; follows the configuration as it changes."""
        c = self.config
        green, grey, gold, plain = "#7fcfa6", "#9db3ba", "#eab84c", "#e3d8bd"

        def yes(on, text_on="Sí", text_off="No"):
            return (text_on, green) if on else (text_off, grey)

        scale = {"1": "1x (720p)", "2": "2x (1440p)", "3": "3x (4K UHD)", "4": "4x (5K)"}.get(str(c.get("scale", "2")), "2x (1440p)")
        sharp = int(c.get("fsr_sharpness", 75))
        upscaler = {"fsr": f"FSR 1.0 · nitidez {sharp} %", "cas": f"AMD CAS · nitidez {sharp} %"}.get(c.get("upscaler", "fsr"), "Desactivado")
        present = {"mailbox": "Mailbox (Fast-Sync)", "fifo": "VSync clásico (Fifo)", "immediate": "Desactivado"}.get(c.get("present_mode", "mailbox"), "Mailbox")
        mods = [n for k, n in (("overlay", "Overlay F1"), ("native_menu", "Menú en pausa"), ("native_text", "Estado de forja")) if c.get(k, True)]
        audio = [n for k, n in (("audio", "Sonido"), ("audio_fx", "Efectos")) if c.get(k, True)]
        online = self.lbl_quick_online.text().replace("Online:", "").strip() or "Comprobando..."
        online_color = green if "Activ" in online and "Desactiv" not in online else grey
        values = {
            "scale": (scale, gold),
            "upscaler": (upscaler, gold if c.get("upscaler", "fsr") != "off" else grey),
            "present": (present, plain),
            "backend": ("DirectX 12" if c.get("gfx_backend") == "dx12" else "Vulkan", plain),
            "window": ("Completa sin bordes", plain) if c.get("fullscreen", True) else ("En ventana", plain),
            "fps": yes(c.get("fps", False)),
            "input": ("Teclado y ratón", plain) if c.get("keyboard_controls", True) else ("Mando", plain),
            "layout": ("Xbox (A abajo)" if c.get("pad_layout") == "xbox" else "Nintendo (B abajo)", plain),
            "sens": (str(int(round(float(c.get("mouse_sensitivity", 0.0008)) * 10000))), plain),
            "mods": (", ".join(mods), green) if mods else ("Desactivados", grey),
            "audio": (" · ".join(audio), green) if audio else ("Silenciado", grey),
            "lto": yes(c.get("build_lto", False)),
            "online": (online, online_color),
            "discord": yes(c.get("discord_rpc", True), "Activado", "Desactivado"),
        }
        for key, (text, color) in values.items():
            if self._quick_last.get(key) != (text, color):
                self._quick_last[key] = (text, color)
                self._quick_labels[key].configure(text=text, text_color=color)

    # ---- tab 2 ---------------------------------------------------------------------------------
    def setup_tab_install(self):
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 8, 4)
        lay.setSpacing(12)

        folder, fl = _card("card")
        fl.addWidget(Label("Carpeta de Dumps de Monster Hunter 3 Ultimate (USA):", None, 10.5, bold=True))
        path_row = QHBoxLayout()
        self.entry_games_path = Entry("Ej: D:\\Juegos\\WiiU\\Monster Hunter 3 Ultimate Dumps")
        if self.config.get("games_dir"):
            self.entry_games_path.insert(0, self.config["games_dir"])
        path_row.addWidget(self.entry_games_path, 1)
        path_row.addWidget(Button("Examinar...", "gold", self.browse_games_folder, width=110))
        fl.addLayout(path_row)
        lay.addWidget(folder)

        badges, bl = _grid_card("card")
        self.lbl_badge_base = Label("⚪ Juego Base USA (0005000010118300): No detectado", "#e3d8bd", 10, bold=True)
        self.lbl_badge_update = Label("⚪ Actualización v32 USA (0005000e10118300): No detectada", "#e3d8bd", 10, bold=True)
        self.lbl_badge_compiler = Label("⚪ Compilador Clang: Comprobando...", "#e3d8bd", 10, bold=True)
        bl.addWidget(self.lbl_badge_base, 0, 0)
        bl.addWidget(self.lbl_badge_update, 0, 1)
        bl.addWidget(self.lbl_badge_compiler, 1, 0, 1, 2)
        lay.addWidget(badges)

        build, bx = _card("card")
        btn_row = QHBoxLayout()
        self.btn_compile_action = Button("⚡ Traducir y Compilar Port (Crear game.dll)", "ember", self.start_build_process, height=44, size=12)
        btn_row.addWidget(self.btn_compile_action, 1)
        self.btn_download_toolchain = Button("⬇️ Descargar Clang Portátil", "default", self.start_download_toolchain, width=200, height=44)
        btn_row.addWidget(self.btn_download_toolchain)
        bx.addLayout(btn_row)
        self.chk_lto = CheckBox("🚀 Optimización Inter-archivos LTO (-flto=thin + -O3) para mayor rendimiento en CPU", self.save_settings_from_ui)
        if self.config.get("build_lto", False):
            self.chk_lto.select()
        bx.addWidget(self.chk_lto)
        self.progress_bar = ProgressBar(10)
        bx.addWidget(self.progress_bar)
        bx.addWidget(Label("Registro del compilador en tiempo real:", None, 10))
        self.txt_log = LogBox(240)
        bx.addWidget(self.txt_log)
        lay.addWidget(build)
        lay.addStretch(1)
        return _transparent_scroll(inner)

    # ---- tab 3 ---------------------------------------------------------------------------------
    def setup_tab_settings(self):
        inner = QWidget()
        cols = QHBoxLayout(inner)
        cols.setContentsMargins(4, 4, 8, 4)
        cols.setSpacing(12)

        gfx, g = _card("card")
        g.addWidget(Label("Opciones Gráficas", "#4fc3d6", 12.5, bold=True))
        g.addWidget(Label("Escala de Resolución Interna:", None, 10.5, bold=True))
        self.opt_scale = Segmented(["1x (720p)", "2x (1440p 2K)", "3x (4K UHD)", "4x (5K Ultra)"], self.on_scale_changed)
        scale_map = {
            "1": "1x (720p)", "2": "2x (1440p 2K)", "3": "3x (4K UHD)", "4": "4x (5K Ultra)",
            "1x (Nativo)": "1x (720p)", "2x (1440p/4K)": "2x (1440p 2K)", "3x (Super)": "3x (4K UHD)", "4x (Ultra)": "4x (5K Ultra)",
        }
        self.opt_scale.set(scale_map.get(str(self.config.get("scale", "2")), "2x (1440p 2K)"))
        g.addWidget(self.opt_scale)
        info = _hint(
            "Resolución a la que se dibuja el juego (base Wii U 1280x720 × factor entero); es independiente del reescalado FSR.\n"
            "1x (720p): nativo, 60 FPS seguros  |  2x (1440p): 4x píxeles, nítido en monitores 1080p/1440p\n"
            "3x (4K UHD): 9x píxeles  |  4x (5K): 16x píxeles (GPUs potentes)"
        )
        info.setWordWrap(True)
        g.addWidget(info)

        self.chk_fullscreen = CheckBox("Pantalla Completa sin bordes (Borderless)", self.save_settings_from_ui)
        if self.config.get("fullscreen", True):
            self.chk_fullscreen.select()
        g.addWidget(self.chk_fullscreen)
        self.chk_fps = CheckBox("Mostrar Contador de FPS en pantalla", self.save_settings_from_ui)
        if self.config.get("fps", False):
            self.chk_fps.select()
        g.addWidget(self.chk_fps)

        g.addWidget(Label("Motor Gráfico (Backend):", None, 10.5, bold=True))
        self.opt_backend = Segmented(["Vulkan (Recomendado)", "DirectX 12 (DX12)"], self.on_backend_changed)
        self.opt_backend.set("DirectX 12 (DX12)" if self.config.get("gfx_backend", "vulkan") == "dx12" else "Vulkan (Recomendado)")
        g.addWidget(self.opt_backend)
        g.addWidget(_hint("💡 Usa DirectX 12 si tienes gráfica integrada Intel o notas tirones con Vulkan."))

        g.addWidget(Label("Sincronización Vertical (VSync):", None, 10.5, bold=True))
        self.opt_present = Segmented(["Mailbox (Fast-Sync)", "VSync Clásico (Fifo)", "Desactivado (OFF)"], self.on_present_changed)
        present_map = {"mailbox": "Mailbox (Fast-Sync)", "fifo": "VSync Clásico (Fifo)", "immediate": "Desactivado (OFF)"}
        self.opt_present.set(present_map.get(self.config.get("present_mode", "mailbox"), "Mailbox (Fast-Sync)"))
        g.addWidget(self.opt_present)
        g.addWidget(_hint("💡 Mailbox evita tirones y reduce la latencia al mínimo sin cortes de pantalla."))

        g.addWidget(Label("Tecnología de Reescalado & Nitidez:", None, 10.5, bold=True))
        self.opt_upscaler = Segmented(["FSR 1.0 (EASU + RCAS)", "AMD CAS (Solo Nitidez)", "Desactivado (Nativo)"], self.on_upscaler_changed)
        upscaler = self.config.get("upscaler", "fsr")
        self.opt_upscaler.set({"cas": "AMD CAS (Solo Nitidez)", "off": "Desactivado (Nativo)"}.get(upscaler, "FSR 1.0 (EASU + RCAS)"))
        g.addWidget(self.opt_upscaler)
        hint = _hint(
            "💡 FSR escala la imagen solo si la resolución interna es menor que la de tu ventana (p. ej. 1x = 720p en un monitor 1080p o 1440p). "
            "Con 2x o más en un monitor 1080p ya hay de sobra y solo se aplica el afilado."
        )
        hint.setWordWrap(True)
        g.addWidget(hint)

        sharp, sl = _card("inset", 12)
        head = QHBoxLayout()
        head.addWidget(Label("Nitidez de Reescalado (FSR / CAS):", None, 10, bold=True))
        head.addStretch(1)
        raw_sharp = self.config.get("fsr_sharpness", 75)
        self.lbl_sharpness_val = Label(f"{raw_sharp}%", "#4fc3d6", 10, bold=True)
        head.addWidget(self.lbl_sharpness_val)
        sl.addLayout(head)
        self.slider_sharpness = Slider(20, 100, self.on_fsr_sharpness_changed)
        self.slider_sharpness.set(raw_sharp)
        sl.addWidget(self.slider_sharpness)
        g.addWidget(sharp)

        g.addWidget(Label("Ventana", None, 10.5, bold=True))
        self.chk_acrylic = CheckBox("Efecto Acrylic (el escritorio se transparenta; reinicia el launcher)", self.on_acrylic_toggled)
        if self.config.get("acrylic", False):
            self.chk_acrylic.select()
        g.addWidget(self.chk_acrylic)
        g.addWidget(_hint("💡 Si usas Windows 10, déjalo desactivado: solo funciona en Windows 11."))

        g.addWidget(Label("Audio & Efectos", None, 10.5, bold=True))
        self.chk_audio = CheckBox("Sonido Activado (CPAL WASAPI)", self.save_settings_from_ui)
        if self.config.get("audio", True):
            self.chk_audio.select()
        g.addWidget(self.chk_audio)
        self.chk_audio_fx = CheckBox("Efectos de Reverberación y Filtros", self.save_settings_from_ui)
        if self.config.get("audio_fx", True):
            self.chk_audio_fx.select()
        g.addWidget(self.chk_audio_fx)
        g.addStretch(1)
        cols.addWidget(gfx, 1, Qt.AlignmentFlag.AlignTop)

        right, r = _card("card")
        r.addWidget(Label("Mejoras & Mods Nativos", "#eab84c", 12.5, bold=True))
        self.chk_overlay = CheckBox("Overlay de Lista de Deseos de Forja (Tecla F1)", self.save_settings_from_ui)
        self.chk_native_menu = CheckBox("Menú de Mods en Pausa (Mantener R-Shift/ZL en Menú Pausa -> Cazador)", self.save_settings_from_ui)
        self.chk_native_text = CheckBox("Estado de Forja en el menú de objetos del juego", self.save_settings_from_ui)
        for chk, key in ((self.chk_overlay, "overlay"), (self.chk_native_menu, "native_menu"), (self.chk_native_text, "native_text")):
            if self.config.get(key, True):
                chk.select()
            r.addWidget(chk)

        r.addWidget(Label("Nombre del Cazador (Nombre en Creación / Partida):", "#4fc3d6", 10.5, bold=True))
        self.entry_hunter_name_cfg = Entry(width=300)
        current_hunter = self.config.get("hunter_name", "Hunter")
        if current_hunter == "Hunter":
            detected = get_hunter_name_from_save(self.config.get("out_dir", DEFAULT_OUT_DIR))
            if detected:
                current_hunter = detected
                self.config["hunter_name"] = detected
        self.entry_hunter_name_cfg.insert(0, current_hunter)
        self.entry_hunter_name_cfg.on_change(self.save_settings_from_ui)
        r.addWidget(self.entry_hunter_name_cfg)

        r.addWidget(Label("Discord Rich Presence (Estado en Discord):", "#8f9bff", 10.5, bold=True))
        self.chk_discord_rpc = CheckBox("Mostrar estado en Discord (Rich Presence)", self.save_settings_from_ui)
        if self.config.get("discord_rpc", True):
            self.chk_discord_rpc.select()
        r.addWidget(self.chk_discord_rpc)
        r.addStretch(1)
        cols.addWidget(right, 1, Qt.AlignmentFlag.AlignTop)
        return _transparent_scroll(inner)

    # ---- tab: controls -------------------------------------------------------------------------
    def setup_tab_controls(self):
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 8, 4)
        lay.setSpacing(12)

        info, il = _grid_card("accent")
        il.addWidget(Label("🕹️", None, 26), 0, 0, 2, 1)
        il.addWidget(Label("Mapeado universal de botones", "#4fc3d6", 12.5, bold=True), 0, 1)
        badge = Label("PRÓXIMAMENTE", "#fff6e0", 9, bold=True)
        badge.setStyleSheet("color: #fff6e0; background: #b8791e; border-radius: 9px; padding: 2px 10px;")
        il.addWidget(badge, 0, 2, Qt.AlignmentFlag.AlignRight)
        text = Label(
            "Asigna cualquier botón de cualquier mando (Xbox, PlayStation, Nintendo o genérico) a cada acción del Wii U Pro Controller, "
            "con perfiles por mando e importar / exportar. La interfaz ya está lista; la captura de botones se activa en una próxima versión.",
            "#e3d8bd",
            10,
        )
        text.setWordWrap(True)
        il.addWidget(text, 1, 1, 1, 2)
        il.setColumnStretch(1, 1)
        lay.addWidget(info)

        row = QHBoxLayout()
        row.setSpacing(12)

        # left: device, profile and the controller picture
        left, ll = _card("card")
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(Label("Mando:", None, 10, bold=True))
        self.opt_map_device = OptionMenu(["Detectando mandos…"], width=210)
        self.opt_map_device.setEnabled(False)
        head.addWidget(self.opt_map_device)
        head.addWidget(Label("Perfil:", None, 10, bold=True))
        self.opt_map_profile = OptionMenu(["Predeterminado (Xbox)", "Predeterminado (Nintendo)"], width=210)
        self.opt_map_profile.setEnabled(False)
        head.addWidget(self.opt_map_profile)
        head.addStretch(1)
        ll.addLayout(head)
        self.pad_diagram = qtmapping.PadDiagram()
        self.pad_diagram.picked.connect(self._on_map_pick)
        ll.addWidget(self.pad_diagram, 1)
        tools = QHBoxLayout()
        tools.setSpacing(8)
        for text in ("📥 Importar", "📤 Exportar", "↺ Restablecer"):
            b = Button(text, "default", None, height=32, bold=False)
            b.configure(state="disabled")
            tools.addWidget(b)
        tools.addStretch(1)
        ll.addLayout(tools)
        row.addWidget(left, 5, Qt.AlignmentFlag.AlignTop)

        # right: one row per action
        right, rl = _card("card")
        rl.addWidget(Label("Asignación de botones", "#7fcfa6", 12, bold=True))
        self.map_note = Label("Elige una acción para ver su botón en el mando.", "#9db3ba", 9.5)
        self.map_note.setWordWrap(True)
        rl.addWidget(self.map_note)
        self.map_chips = {}
        for group, items in qtmapping.GROUPS:
            rl.addWidget(Label(group, "#eab84c", 10, bold=True))
            for key, name in items:
                line = QHBoxLayout()
                line.setSpacing(8)
                line.addWidget(Label(name, None, 10), 1)
                chip = Button("Sin asignar", "default", lambda k=key: self._on_map_pick(k), width=150, height=28, bold=False, size=9.5)
                clear = Button("✕", "default", None, width=34, height=28, bold=False, size=9.5)
                clear.configure(state="disabled")
                line.addWidget(chip)
                line.addWidget(clear)
                rl.addLayout(line)
                self.map_chips[key] = chip
        rl.addStretch(1)
        row.addWidget(right, 4)
        lay.addLayout(row)

        # what was in the graphics tab: layout and camera
        base, bl = _card("card")
        bl.addWidget(Label("Disposición y cámara", "#7fcfa6", 12, bold=True))
        bl.addWidget(Label("Disposición de Botones del Mando:"))
        self.opt_pad = Segmented(["Xbox (A abajo, B der)", "Nintendo (B abajo, A der)"], self.on_pad_changed)
        self.opt_pad.set("Xbox (A abajo, B der)" if self.config.get("pad_layout") == "xbox" else "Nintendo (B abajo, A der)")
        bl.addWidget(self.opt_pad)

        sens, sn = _card("inset", 12)
        head = QHBoxLayout()
        head.addWidget(Label("Sensibilidad de Cámara (Ratón):", None, 10, bold=True))
        head.addStretch(1)
        raw_sens = self.config.get("mouse_sensitivity", 0.0008)
        self.lbl_sens_val = Label(f"{int(round(raw_sens * 10000))}", "#4fc3d6", 10, bold=True)
        head.addWidget(self.lbl_sens_val)
        sn.addLayout(head)
        self.slider_sens = Slider(2, 30, self.on_mouse_sens_changed)
        self.slider_sens.set(int(round(raw_sens * 10000)))
        sn.addWidget(self.slider_sens)
        bl.addWidget(sens)
        lay.addWidget(base)
        lay.addStretch(1)
        return _transparent_scroll(inner)

    def _on_map_pick(self, key):
        """Selecting an action shows its button on the controller; capturing the real button comes later."""
        self.pad_diagram.set_active(key)
        for k, chip in self.map_chips.items():
            chip.configure(text="Pulsa un botón…" if k == key else "Sin asignar", fg_color="#b8791e" if k == key else "#2b4a58", hover_color="#d4922a" if k == key else "#3b6073")
        self.map_note.configure(text="La captura de botones se activará en una próxima versión; por ahora la disposición se elige abajo.")
        QTimer.singleShot(2200, lambda: self._reset_map_chips(key))

    def _reset_map_chips(self, key):
        if self.pad_diagram.active == key:
            for chip in self.map_chips.values():
                chip.configure(text="Sin asignar", fg_color="#2b4a58", hover_color="#3b6073")

    # ---- tab 4 ---------------------------------------------------------------------------------
    def setup_tab_online(self):
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 8, 4)
        lay.setSpacing(12)

        info, il = _grid_card("accent")
        il.addWidget(Label("🌐", None, 28), 0, 0, 2, 1)
        il.addWidget(Label("Multijugador Online de Tanzia (Protocolo Matt-Wood-23 / mh3u-revival)", "#4fc3d6", 12, bold=True), 0, 1)
        text = Label(
            "Módulo de red con soporte P2P y servidor relay de baja latencia. Permite crear o unirte a partidas de hasta 4 cazadores. "
            "Para jugar por Internet sin abrir puertos en el router, se recomienda que tú y tus amigos usen una red virtual como "
            "Radmin VPN, ZeroTier o Tailscale.",
            "#e3d8bd",
            10,
        )
        text.setWordWrap(True)
        il.addWidget(text, 1, 1)
        il.setColumnStretch(1, 1)
        lay.addWidget(info)

        top, tl = _card("card")
        self.switch_online = Switch("Habilitar Modo Multijugador Online al iniciar el juego", self.on_online_switch_toggled)
        if self.config.get("online_enabled", False):
            self.switch_online.select()
        tl.addWidget(self.switch_online)
        tl.addWidget(Label("Selecciona tu función en la partida:", "#9db3ba", 10, bold=True))
        current_mode = self.config.get("online_mode", "client")
        init_mode = "👑 Crear Servidor de Sala (Host)" if current_mode == "host" else "🎮 Unirse a una Sala (Cliente)"
        self.seg_online_mode = Segmented(["🎮 Unirse a una Sala (Cliente)", "👑 Crear Servidor de Sala (Host)"], self.on_online_mode_changed, bold=True)
        self.seg_online_mode.set(init_mode)
        tl.addWidget(self.seg_online_mode)
        lay.addWidget(top)

        # client
        self.frame_client_mode, c = _grid_card("card")
        c.addWidget(Label("🎮 Conexión a la Partida de tu Amigo (Cliente)", "#7fcfa6", 11.5, bold=True), 0, 0, 1, 2)
        c.addWidget(Label("IP del Anfitrión / Amigo:"), 1, 0)
        host_row = QHBoxLayout()
        self.entry_server_host = Entry(width=230)
        self.entry_server_host.insert(0, self.config.get("online_server", "127.0.0.1"))
        host_row.addWidget(self.entry_server_host)
        self.btn_ping_host = Button("🔍 Probar Ping", "default", self.test_host_ping, width=120)
        host_row.addWidget(self.btn_ping_host)
        host_row.addStretch(1)
        c.addLayout(host_row, 1, 1)
        self.lbl_ping_result = Label("Estado: Listo para probar conexión", "#9db3ba", 10)
        c.addWidget(self.lbl_ping_result, 2, 1)
        c.addWidget(Label("ID de Sala / Taberna:"), 3, 0)
        self.entry_room_id = Entry(width=130)
        self.entry_room_id.insert(0, self.config.get("online_room_id", "1001"))
        c.addWidget(self.entry_room_id, 3, 1)
        c.addWidget(Label("Tu Nombre de Cazador:"), 4, 0)
        self.entry_hunter_name = Entry(width=230)
        detected = get_hunter_name_from_save(self.config.get("out_dir", DEFAULT_OUT_DIR))
        self.entry_hunter_name.insert(0, self.config.get("online_hunter_name") or detected or "Hunter")
        c.addWidget(self.entry_hunter_name, 4, 1)
        c.setColumnStretch(1, 1)
        lay.addWidget(self.frame_client_mode)

        # host
        self.frame_host_mode, h = _grid_card("card")
        h.addWidget(Label("👑 Servidor de Salas Integrado (Crear Partida)", "#eab84c", 11.5, bold=True), 0, 0, 1, 2)
        h.addWidget(_hint("Inicia el servidor de retransmisión local para que tus amigos se conecten contigo a Puerto Tanzia."), 1, 0, 1, 2)
        h.addWidget(Label("Tu IP para amigos:"), 2, 0)
        ip_row = QHBoxLayout()
        ips = get_local_ip_addresses()
        self.opt_local_ips = OptionMenu(ips, width=290)
        if ips:
            self.opt_local_ips.set(ips[0])
        ip_row.addWidget(self.opt_local_ips)
        ip_row.addWidget(Button("📋 Copiar IP", "default", self.copy_selected_ip, width=110))
        self.lbl_copy_feedback = Label("", "#7fcfa6", 9.5)
        ip_row.addWidget(self.lbl_copy_feedback)
        ip_row.addStretch(1)
        h.addLayout(ip_row, 2, 1)
        h.addWidget(Label("ID de Sala por Defecto:"), 3, 0)
        self.entry_host_room = Entry(width=130)
        self.entry_host_room.insert(0, self.config.get("online_room_id", "1001"))
        h.addWidget(self.entry_host_room, 3, 1)
        act = QHBoxLayout()
        self.btn_toggle_server = Button("▶  Iniciar Servidor de Sala (Host)", "teal", self.toggle_host_server, height=38)
        act.addWidget(self.btn_toggle_server)
        self.lbl_server_status = Label("⚪ Servidor Inactivo", "#9db3ba", 10.5, bold=True)
        act.addWidget(self.lbl_server_status)
        act.addStretch(1)
        h.addLayout(act, 4, 0, 1, 2)
        h.addWidget(Label("Registro del Servidor en Tiempo Real:", "#4fc3d6", 10, bold=True), 5, 0, 1, 2)
        self.txt_server_log = LogBox(140)
        h.addWidget(self.txt_server_log, 6, 0, 1, 2)
        h.setColumnStretch(1, 1)
        lay.addWidget(self.frame_host_mode)

        save = Button("💾 Guardar Parámetros de Red", "default", self.save_online_settings, height=38)
        lay.addWidget(save, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addStretch(1)

        self.on_online_mode_changed(init_mode)
        return _transparent_scroll(inner)

    # ---- tab 5 ---------------------------------------------------------------------------------
    def setup_tab_tools(self):
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 8, 4)
        lay.setSpacing(12)

        card, g = _grid_card("card")
        g.addWidget(Label("Gestión de Datos y Partidas", "#4fc3d6", 12.5, bold=True), 0, 0, 1, 2)
        rows = [
            ("📂 Abrir Carpeta de Saves", "gold", self.open_save_folder, "Ubicación donde el port guarda tu progreso y personaje."),
            ("🛡️ Respaldar Partidas Ahora", "good", self.backup_save_folder, "Crea un archivo comprimido .zip con la fecha actual."),
            ("📄 Abrir Registro (Log Reciente)", "default", self.open_latest_log, "Abre 'mh3u_latest.log' para revisar errores de Vulkan o del juego."),
            ("🧹 Limpiar Caché de Shaders", "danger", self.clean_cache, "Elimina la caché de pipelines si notas artefactos gráficos."),
        ]
        for i, (text, kind, fn, desc) in enumerate(rows, start=1):
            g.addWidget(Button(text, kind, fn, width=250), i, 0)
            g.addWidget(Label(desc), i, 1)
        g.setColumnStretch(1, 1)
        lay.addWidget(card)

        credits, c = _grid_card("card")
        c.addWidget(Label("Créditos y Agradecimientos", "#4fc3d6", 12.5, bold=True), 0, 0, 1, 2)
        c.addWidget(Label("Desarrollo del Launcher:", "#eab84c", 10.5, bold=True), 1, 0)
        c.addWidget(Button("G30vamv / Mh3u-native-port-launcher-and-online-integration ↗", "link", lambda: webbrowser.open_new_tab("https://github.com/G30vamv/Mh3u-native-port-launcher-and-online-integration"), height=28, bold=False), 1, 1, Qt.AlignmentFlag.AlignLeft)
        links = [
            ("Port Nativo & Recompilación PC:", "glinesbdev / mh3u-port ↗", "https://github.com/glinesbdev/mh3u-port"),
            ("Lógica de Red & Servidor Online:", "Matt-Wood-23 / mh3u-revival ↗", "https://github.com/Matt-Wood-23/mh3u-revival"),
        ]
        for i, (what, text, url) in enumerate(links, start=2):
            c.addWidget(Label(what, None, 10.5, bold=True), i, 0)
            c.addWidget(Button(text, "link", lambda u=url: webbrowser.open_new_tab(u), height=28, bold=False), i, 1, Qt.AlignmentFlag.AlignLeft)
        c.addWidget(Label("Versión del Launcher:", "#4fc3d6", 10.5, bold=True), 4, 0)
        c.addWidget(Label(f"{APP_VERSION} (Recompilación Nativa PC)", "#eab84c", 10.5, bold=True), 4, 1)
        c.setColumnStretch(1, 1)
        lay.addWidget(credits)
        lay.addStretch(1)
        return _transparent_scroll(inner)


def main():
    qapp = QApplication(sys.argv)
    qapp.setStyleSheet(STYLE)
    qapp.setFont(font(10.5))
    qtshim.init_threading()
    app = MH3ULauncherApp(qapp)
    app.show()
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
