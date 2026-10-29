"""
Monster Hunter 3 Ultimate - PC Native Port Launcher
Author: g30wolff99
A modern, user-friendly graphical launcher for mh3u-port on Windows.
"""

import os
import sys
import json
import shutil
import threading
import subprocess
import datetime
import queue
import tempfile
import urllib.request
import zipfile
import time
import struct
import uuid
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image
import socket
import webbrowser

try:
    import updater
except Exception:  # update support is optional; the launcher must work without it
    updater = None

# Initialize CustomTkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Moga Village / Tanzia palette: deep-ocean navy, parchment text, gold + teal accents
_TH = ctk.ThemeManager.theme
_TH["CTk"]["fg_color"] = ["#f3ead2", "#0a131a"]
_TH["CTkFrame"]["fg_color"] = ["#e8dcc0", "#14242e"]
_TH["CTkFrame"]["top_fg_color"] = ["#e8dcc0", "#1b3441"]
_TH["CTkButton"].update({"fg_color": ["#b8791e", "#b8791e"], "hover_color": ["#d4922a", "#d4922a"], "text_color": ["#fff6e0", "#fff6e0"]})
_TH["CTkSegmentedButton"].update({"selected_color": ["#b8791e", "#b8791e"], "selected_hover_color": ["#d4922a", "#d4922a"], "unselected_color": ["#2b4a58", "#1b3441"], "unselected_hover_color": ["#3b6073", "#2b4a58"], "text_color": ["#fff6e0", "#fff6e0"]})
_TH["CTkSwitch"].update({"progress_color": ["#2f9488", "#2f9488"], "button_color": ["#eab84c", "#eab84c"], "button_hover_color": ["#f2c968", "#f2c968"]})
_TH["CTkCheckBox"].update({"fg_color": ["#2f9488", "#2f9488"], "hover_color": ["#257a70", "#257a70"]})
_TH["CTkSlider"].update({"progress_color": ["#2f9488", "#2f9488"], "button_color": ["#eab84c", "#eab84c"], "button_hover_color": ["#f2c968", "#f2c968"]})
_TH["CTkProgressBar"].update({"progress_color": ["#eab84c", "#eab84c"]})
_TH["CTkOptionMenu"].update({"fg_color": ["#2b4a58", "#2b4a58"], "button_color": ["#3b6073", "#3b6073"], "button_hover_color": ["#c98f2b", "#c98f2b"]})
_TH["CTkComboBox"].update({"button_color": ["#3b6073", "#3b6073"], "button_hover_color": ["#c98f2b", "#c98f2b"]})
_TH["CTkEntry"].update({"fg_color": ["#fff6e0", "#0d1820"], "border_color": ["#b9a97f", "#2b4a58"]})
_TH["CTkScrollbar"].update({"button_color": ["#3b6073", "#3b6073"], "button_hover_color": ["#c98f2b", "#c98f2b"]})

APP_VERSION = "v0.7.7"

# Bump when the translator output changes (e.g. more functions discovered). A game.dll built
# by an older translator lacks functions the online code needs ("not a translated function").
TRANSLATOR_REV = "2"


def dll_rev_path(out_dir):
    return os.path.join(out_dir, "game.dll.rev")


def game_dll_is_current(out_dir):
    try:
        with open(dll_rev_path(out_dir), "r", encoding="utf-8") as f:
            return f.read().strip() == TRANSLATOR_REV
    except OSError:
        return False
CONFIG_FILE = "launcher_config.json"
DEFAULT_OUT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "mh3u", "c")

# Base USA Title ID: 0005000010118300
# Update USA Title ID: 0005000e10118300
BASE_TITLE_ID = "0005000010118300"
UPDATE_TITLE_ID = "0005000e10118300"
LLVM_MINGW_URL = "https://github.com/mstorsjo/llvm-mingw/releases/download/20261020/llvm-mingw-20261020-ucrt-x86_64.zip"
DEFAULT_DISCORD_CLIENT_ID = "1564085149283651734"


def detect_route_ip(target):
    """Local IPv4 the OS would use to reach `target` (e.g. the Radmin adapter IP)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((target, 1223))
            return s.getsockname()[0]
    except Exception:
        return ""


def get_local_ip_addresses():
    """
    Returns categorized and prioritized IPv4 addresses with friendly labels:
    1. VPNs (Radmin VPN, Tailscale, ZeroTier) -> listed FIRST.
    2. Local Area Network (Ethernet, Wi-Fi).
    3. Localhost (127.0.0.1).
    Filters out invalid/APIPA addresses (169.254.*).
    """
    results = []

    # 1. Try Windows PowerShell for exact interface alias names
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-NetIPAddress -AddressFamily IPv4 | Select-Object IPAddress, InterfaceAlias | ConvertTo-Json",
        ]
        out = subprocess.check_output(cmd, text=True, timeout=1.5)
        items = json.loads(out)
        if isinstance(items, dict):
            items = [items]
        for it in items:
            ip = str(it.get("IPAddress", "")).strip()
            alias = str(it.get("InterfaceAlias", "")).strip()
            # Ignore APIPA (169.254.*) and loopback
            if not ip or ip.startswith("169.254.") or ip.startswith("127."):
                continue

            alias_lower = alias.lower()
            if "radmin" in alias_lower:
                label = f"{ip} (Radmin VPN)"
                priority = 1
            elif "tailscale" in alias_lower:
                label = f"{ip} (Tailscale)"
                priority = 1
            elif "zerotier" in alias_lower:
                label = f"{ip} (ZeroTier)"
                priority = 1
            elif "wi-fi" in alias_lower or "wifi" in alias_lower or "inalamb" in alias_lower:
                label = f"{ip} (Wi-Fi Local)"
                priority = 2
            elif "ethernet" in alias_lower or "local area" in alias_lower:
                label = f"{ip} (Ethernet Local)"
                priority = 2
            else:
                label = f"{ip} ({alias})"
                priority = 3
            results.append((priority, label, ip))
    except Exception:
        pass

    # 2. Heuristics fallback if PowerShell didn't return or failed
    if not results:
        try:
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                if ip.startswith("169.254.") or ip.startswith("127."):
                    continue
                if ip.startswith("26."):
                    results.append((1, f"{ip} (Radmin VPN)", ip))
                elif ip.startswith("100."):
                    results.append((1, f"{ip} (Tailscale)", ip))
                elif ip.startswith("10.147."):
                    results.append((1, f"{ip} (ZeroTier)", ip))
                elif ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
                    results.append((2, f"{ip} (Red Local LAN)", ip))
                else:
                    results.append((3, f"{ip} (Red Local)", ip))
        except Exception:
            pass

    # Deduplicate by IP keeping highest priority
    seen = set()
    unique_results = []
    # Sort: Priority 1 (VPNs) first, then Priority 2 (LAN), then Priority 3
    results.sort(key=lambda x: x[0])
    for prio, label, ip in results:
        if ip not in seen:
            seen.add(ip)
            unique_results.append(label)

    # Always provide Localhost as final option
    unique_results.append("127.0.0.1 (Localhost / Mismo PC)")
    return unique_results


def get_base_dir():
    """Gets the base directory where the launcher or script is located."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_assets_dir():
    """Gets the assets directory, checking PyInstaller bundle first, then local."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, "assets")
        if os.path.exists(bundled):
            return bundled
    local = os.path.join(get_base_dir(), "assets")
    return local


def get_tools_path():
    """Locates mh3u-tools.exe either locally, in target/release, or bundled."""
    base_dir = get_base_dir()
    candidates = [
        os.path.join(base_dir, "mh3u-tools.exe"),
        os.path.join(base_dir, "tools", "mh3u-tools.exe"),
        os.path.join(base_dir, "..", "mh3u-port", "target", "release", "mh3u-tools.exe"),
        os.path.join(base_dir, "target", "release", "mh3u-tools.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return candidates[0]


def get_clang_info():
    """Detects Clang compiler in local toolchain, system PATH, or WinGet package."""
    base_dir = get_base_dir()
    # 1. Local portable toolchain inside launcher directory
    local_toolchain = os.path.join(base_dir, "toolchain", "bin")
    if os.path.exists(os.path.join(local_toolchain, "clang.exe")):
        return local_toolchain, "Portátil (toolchain local)"

    # 2. Check if clang is in system PATH
    shutil_clang = shutil.which("clang")
    if shutil_clang:
        return os.path.dirname(shutil_clang), "Instalado en Windows (PATH)"

    # 3. Check LLVM-MinGW WinGet package directory
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    winget_dir = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
    if os.path.exists(winget_dir):
        for root, dirs, files in os.walk(winget_dir):
            if "clang.exe" in files and "bin" in root.lower() and "llvm-mingw" in root.lower():
                return root, "LLVM-MinGW detectado"

    # 4. Check standard Program Files LLVM
    pf_llvm = r"C:\Program Files\LLVM\bin"
    if os.path.exists(os.path.join(pf_llvm, "clang.exe")):
        return pf_llvm, "LLVM detectado"

    return None, None


def read_hunter_name_from_file(file_path):
    """Reads hunter name from a binary user save file (offset 0x2B, max 21 bytes)."""
    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) >= 35364:
            with open(file_path, "rb") as f:
                f.seek(0x2B)
                raw = f.read(0x15)
                end = raw.find(b"\x00")
                if end != -1:
                    raw = raw[:end]
                name = raw.decode("utf-8", errors="replace").strip()
                if name:
                    return name
    except Exception:
        pass
    return None


def get_hunter_name_from_save(out_dir):
    """
    Finds the active hunter's name by inspecting save files (user1, user2, user3)
    in out_dir/save, prioritizing the most recently modified save file.
    """
    if not out_dir:
        return None
    save_dir = os.path.join(out_dir, "save")
    if not os.path.exists(save_dir):
        return None

    candidates = []
    for root, dirs, files in os.walk(save_dir):
        for f in files:
            if f in ("user1", "user2", "user3"):
                full_path = os.path.join(root, f)
                try:
                    candidates.append((os.path.getmtime(full_path), full_path))
                except Exception:
                    pass

    # Sort descending by last modified time
    candidates.sort(key=lambda x: x[0], reverse=True)

    for _, path in candidates:
        name = read_hunter_name_from_file(path)
        if name:
            return name
    return None


CRLF = chr(13) + chr(10)


class DiscordRPCManager:
    """Manages lightweight, zero-overhead Discord Rich Presence via local Windows Named Pipe."""

    def __init__(self, client_id=DEFAULT_DISCORD_CLIENT_ID):
        self.client_id = str(client_id).strip()
        self.pipe = None
        self.connected = False
        self.start_time = int(time.time())

    def connect(self):
        if not self.client_id:
            return False
        for i in range(10):
            pipe_name = rf"\\.\pipe\discord-ipc-{i}"
            if os.path.exists(pipe_name):
                try:
                    self.pipe = open(pipe_name, "r+b", buffering=0)
                    payload = json.dumps({"v": 1, "client_id": self.client_id}).encode("utf-8")
                    self.pipe.write(struct.pack("<II", 0, len(payload)) + payload)
                    resp_hdr = self.pipe.read(8)
                    if len(resp_hdr) == 8:
                        op, length = struct.unpack("<II", resp_hdr)
                        resp_data = json.loads(self.pipe.read(length).decode("utf-8", errors="ignore"))
                        if op == 1:  # FRAME (SUCCESS)
                            self.connected = True
                            return True
                    self.close()
                except Exception:
                    self.close()
        return False

    def update_presence(self, details="Cazando", state="Cazador", large_text="Monster Hunter 3 Ultimate (PC Native Port)"):
        if not self.connected or not self.pipe:
            return False
        try:
            activity = {
                "details": details,
                "state": state,
                "timestamps": {"start": self.start_time},
                "assets": {
                    "large_image": "icon",
                    "large_text": large_text,
                },
            }
            frame = {
                "cmd": "SET_ACTIVITY",
                "args": {"pid": os.getpid(), "activity": activity},
                "nonce": str(uuid.uuid4()),
            }
            payload = json.dumps(frame).encode("utf-8")
            self.pipe.write(struct.pack("<II", 1, len(payload)) + payload)
            resp_hdr = self.pipe.read(8)
            if len(resp_hdr) == 8:
                op, length = struct.unpack("<II", resp_hdr)
                self.pipe.read(length)
                return True
        except Exception:
            self.close()
            return False

    def close(self):
        self.connected = False
        if self.pipe:
            try:
                self.pipe.close()
            except Exception:
                pass
            self.pipe = None


class MH3ULauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"Monster Hunter 3 Ultimate - PC Port Launcher {APP_VERSION}")
        self.geometry("1140x820")
        self.minsize(980, 680)
        self.resizable(True, True)

        # Assets folder
        self.assets_dir = get_assets_dir()
        self.icon_path = os.path.join(self.assets_dir, "app_icon.ico")
        if os.path.exists(self.icon_path):
            try:
                self.iconbitmap(self.icon_path)
            except Exception:
                pass

        # Load configuration
        self.config = self.load_config()

        # Build execution state
        self.is_compiling = False
        self.is_running = False
        self.is_downloading_toolchain = False
        self.game_process = None

        # Thread-safe UI event queue
        self.ui_queue = queue.Queue()

        self.server_process = None
        self.protocol("WM_DELETE_WINDOW", self.on_app_close)

        self.setup_ui()
        self.after(50, self._process_ui_queue)
        self.refresh_status()
        if updater and self.config.get("auto_check_updates", True):
            self.after(4000, lambda: self.check_for_updates(silent=True))

    def _process_ui_queue(self):
        try:
            while not self.ui_queue.empty():
                msg_type, data = self.ui_queue.get_nowait()
                if msg_type == "log":
                    self.txt_log.insert(tk.END, data + "\n")
                    self.txt_log.see(tk.END)
                elif msg_type == "server_log":
                    if hasattr(self, "txt_server_log") and self.txt_server_log.winfo_exists():
                        self.txt_server_log.insert(tk.END, data + "\n")
                        self.txt_server_log.see(tk.END)
                elif msg_type == "server_status":
                    if hasattr(self, "lbl_server_status") and self.lbl_server_status.winfo_exists():
                        self.lbl_server_status.configure(**data)
                elif msg_type == "ping_result":
                    success, elapsed_ms, detail = data
                    self._on_ping_result(success, elapsed_ms, detail)
                elif msg_type == "progress":
                    self.progress_bar.set(data)
                elif msg_type == "btn_compile":
                    self.btn_compile_action.configure(**data)
                elif msg_type == "btn_download":
                    self.btn_download_toolchain.configure(**data)
                elif msg_type == "tab":
                    self.tabview.set(data)
                elif msg_type == "refresh":
                    self.refresh_status()
                elif msg_type == "info":
                    messagebox.showinfo(data[0], data[1])
                elif msg_type == "error":
                    messagebox.showerror(data[0], data[1])
                elif msg_type == "warning":
                    messagebox.showwarning(data[0], data[1])
                elif msg_type == "update_state":
                    if hasattr(self, "lbl_update_status") and self.lbl_update_status.winfo_exists():
                        self.lbl_update_status.configure(**data)
                elif msg_type == "update_btn":
                    if hasattr(self, "btn_update") and self.btn_update.winfo_exists():
                        self.btn_update.configure(**data)
                elif msg_type == "update_prompt":
                    self._prompt_update(*data)
        except Exception as e:
            print(f"UI Queue error: {e}")
        finally:
            self.after(50, self._process_ui_queue)

    def load_config(self):
        """Loads configuration from JSON file or returns defaults with auto-detection."""
        config_path = os.path.join(get_base_dir(), CONFIG_FILE)
        defaults = {
            "games_dir": "",
            "out_dir": DEFAULT_OUT_DIR,
            "scale": "2",
            "fullscreen": True,
            "pad_layout": "xbox",
            "overlay": True,
            "native_menu": True,
            "native_text": True,
            "fps": False,
            "audio": True,
            "audio_fx": True,
            # Online section
            "online_enabled": False,
            "online_relay": "auto",
            "online_mode": "client",
            "online_server": "127.0.0.1",
            "online_hunter_name": "Hunter",
            "online_room_id": "1001",
            "hunter_name": "Hunter",
            "discord_rpc": True,
            "discord_client_id": DEFAULT_DISCORD_CLIENT_ID,
            "gfx_backend": "vulkan",
            "present_mode": "mailbox",
            "upscaler": "fsr",
            "fsr_sharpness": 75,
            "build_lto": False,
        }
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    defaults.update(saved)
            except Exception as e:
                print(f"Error loading config: {e}")

        # Sanitize out_dir: if it contains an absolute path from another machine that does not exist, reset to current user's default
        cfg_out = defaults.get("out_dir", "")
        if not cfg_out or not os.path.exists(os.path.dirname(cfg_out)):
            defaults["out_dir"] = DEFAULT_OUT_DIR

        # Auto-detect hunter name from existing save file if default or empty
        detected_hunter = get_hunter_name_from_save(defaults.get("out_dir", DEFAULT_OUT_DIR))
        if detected_hunter:
            if defaults.get("hunter_name", "Hunter") == "Hunter" or not defaults.get("hunter_name"):
                defaults["hunter_name"] = detected_hunter

        # Auto-detect dumps if not configured or if configured games_dir does not exist
        cfg_games = defaults.get("games_dir", "")
        has_base, has_upd, _, _ = self.check_dump_status(cfg_games) if cfg_games else (False, False, None, None)
        if not (has_base and has_upd):
            base_dir = get_base_dir()
            candidate_dirs = [
                os.path.join(base_dir, "MH3U_Dump"),
                os.path.join(base_dir, "dump"),
                os.path.join(base_dir, "dumps"),
                os.path.join(base_dir, "games"),
                os.path.join(os.path.dirname(base_dir), "MH3U_Dump"),
                base_dir,
            ]
            for c_dir in candidate_dirs:
                if os.path.exists(c_dir):
                    hb, hu, bp, up = self.check_dump_status(c_dir)
                    if hb and hu and bp and up:
                        try:
                            defaults["games_dir"] = os.path.commonpath([bp, up])
                        except Exception:
                            defaults["games_dir"] = c_dir
                        break
        return defaults

    def save_config(self):
        """Saves current configuration to JSON file."""
        config_path = os.path.join(get_base_dir(), CONFIG_FILE)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def setup_ui(self):
        # Configure layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header with Banner
        self.create_header()

        # Navigation Tabs
        self.tabview = ctk.CTkTabview(
            self, corner_radius=12, border_width=1, border_color="#2b4a58",
            fg_color="#10202a", segmented_button_fg_color="#0d1820",
            segmented_button_selected_color="#b8791e", segmented_button_selected_hover_color="#d4922a",
            segmented_button_unselected_color="#14242e", segmented_button_unselected_hover_color="#22414f",
            text_color="#e3d8bd",
        )
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 15))

        self.tab_main = self.tabview.add("  🎮 Principal  ")
        self.tab_install = self.tabview.add("  ⚙️ Instalación & Dump  ")
        self.tab_settings = self.tabview.add("  🛠️ Configuración Gráfica  ")
        self.tab_online = self.tabview.add("  🌐 Modo Online (Beta)  ")
        self.tab_tools = self.tabview.add("  💾 Partidas & Logs  ")

        self.setup_tab_main()
        self.setup_tab_install()
        self.setup_tab_settings()
        self.setup_tab_online()
        self.setup_tab_tools()

        # Footer Bar with dev credits
        self.create_footer()

    def create_header(self):
        # Look for custom artwork first, then fallback to banner.png
        banner_candidates = [
            os.path.join(self.assets_dir, "SI_WiiU_MonsterHunter3Ultimate.jpg"),
            os.path.join(get_base_dir(), "SI_WiiU_MonsterHunter3Ultimate.jpg"),
            os.path.join(os.path.dirname(get_base_dir()), "SI_WiiU_MonsterHunter3Ultimate.jpg"),
            os.path.join(self.assets_dir, "banner.png"),
        ]
        banner_path = next((p for p in banner_candidates if os.path.exists(p)), None)

        header_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#0d1820")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        if banner_path:
            try:
                pil_banner = Image.open(banner_path)
                bw, bh = pil_banner.size
                ratio = 110 / bh
                nw = int(bw * ratio)
                self.banner_img = ctk.CTkImage(light_image=pil_banner, dark_image=pil_banner, size=(nw, 110))
                banner_label = ctk.CTkLabel(header_frame, image=self.banner_img, text="", corner_radius=8)
                banner_label.grid(row=0, column=0, rowspan=2, padx=12, pady=8)
            except Exception as e:
                print(f"Error loading banner: {e}")

        text_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        text_container.grid(row=0, column=1, rowspan=2, sticky="w", padx=10, pady=8)

        title_label = ctk.CTkLabel(
            text_container,
            text="MONSTER HUNTER 3 ULTIMATE",
            font=ctk.CTkFont(family="Georgia", size=24, weight="bold"),
            text_color="#f2b94b",
        )
        title_label.pack(anchor="w", pady=(2, 2))

        subtitle_label = ctk.CTkLabel(
            text_container,
            text=f"PC Native Port Launcher {APP_VERSION} • Monster Hunter 3 Ultimate (Vulkan / DX12 / LTO)",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#9db3ba",
        )
        subtitle_label.pack(anchor="w", pady=(0, 2))

        # Developer badge on the right
        dev_badge = ctk.CTkFrame(header_frame, fg_color="#14242e", corner_radius=8, border_width=1, border_color="#2b4a58")
        dev_badge.grid(row=0, column=2, rowspan=2, padx=(10, 18), pady=12, sticky="e")

        ctk.CTkLabel(
            dev_badge,
            text=f"🛠️ Versión {APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#eab84c",
        ).pack(padx=14, pady=(6, 1))

        ctk.CTkLabel(
            dev_badge,
            text="g30wolff99",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#4fc3d6",
        ).pack(padx=14, pady=(0, 6))

    def create_footer(self):
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.grid(row=2, column=0, sticky="ew", padx=25, pady=(0, 6))
        footer_frame.grid_columnconfigure(0, weight=1)
        footer_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            footer_frame,
            text=f"Monster Hunter 3 Ultimate (Wii U) • Recompilación Nativa para PC | {APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#6f8c99",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            footer_frame,
            text="Launcher desarrollado por g30wolff99",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#e3d8bd",
        ).grid(row=0, column=1, sticky="e")

    # =========================================================================
    # TAB 1: PRINCIPAL / JUGAR
    # =========================================================================
    def setup_tab_main(self):
        self.tab_main.grid_columnconfigure(0, weight=1)
        self.tab_main.grid_columnconfigure(1, weight=1)

        # Status Card
        status_card = ctk.CTkFrame(self.tab_main, corner_radius=10, fg_color="#14242e")
        status_card.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        status_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            status_card, text="ESTADO DEL JUEGO:", font=ctk.CTkFont(weight="bold", size=14)
        ).grid(row=0, column=0, padx=15, pady=(10, 2), sticky="w")

        self.lbl_main_status = ctk.CTkLabel(
            status_card,
            text="Verificando instalación...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#eab84c",
        )
        self.lbl_main_status.grid(row=0, column=1, padx=10, pady=(10, 2), sticky="w")

        ctk.CTkLabel(
            status_card, text="MODO ONLINE:", font=ctk.CTkFont(weight="bold", size=13)
        ).grid(row=1, column=0, padx=15, pady=(2, 10), sticky="w")

        self.lbl_main_online_status = ctk.CTkLabel(
            status_card,
            text="Comprobando...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#e3d8bd",
        )
        self.lbl_main_online_status.grid(row=1, column=1, padx=10, pady=(2, 10), sticky="w")

        # Big Play Button
        self.btn_play = ctk.CTkButton(
            self.tab_main,
            text="⚔️  JUGAR MONSTER HUNTER 3 ULTIMATE",
            font=ctk.CTkFont(size=20, weight="bold"),
            height=60,
            fg_color="#2f9488",
            hover_color="#257a70",
            corner_radius=12,
            command=self.launch_game,
        )
        self.btn_play.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(15, 15))

        # Quick summary cards
        quick_left = ctk.CTkFrame(self.tab_main, corner_radius=10, fg_color="#14242e")
        quick_left.grid(row=2, column=0, sticky="nsew", padx=(10, 5), pady=10)
        quick_left.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            quick_left, text="Ajustes Rápidos Activos", font=ctk.CTkFont(weight="bold", size=14), text_color="#4fc3d6"
        ).grid(row=0, column=0, columnspan=2, padx=15, pady=10, sticky="w")

        scale_map_quick = {"1": "1x (720p)", "2": "2x (1440p 2K)", "3": "3x (4K UHD)", "4": "4x (5K Ultra)"}
        quick_scale_text = scale_map_quick.get(str(self.config.get("scale", "2")), "2x (1440p 2K)")
        self.lbl_quick_scale = ctk.CTkLabel(quick_left, text=f"Resolución: {quick_scale_text}")
        self.lbl_quick_scale.grid(row=1, column=0, columnspan=2, padx=15, pady=3, sticky="w")

        self.lbl_quick_pad = ctk.CTkLabel(quick_left, text="Mando: Disposición Xbox")
        self.lbl_quick_pad.grid(row=2, column=0, columnspan=2, padx=15, pady=3, sticky="w")

        self.lbl_quick_mods = ctk.CTkLabel(quick_left, text="Mods: Overlay F1 Activo")
        self.lbl_quick_mods.grid(row=3, column=0, columnspan=2, padx=15, pady=3, sticky="w")

        quick_backend_text = "DirectX 12" if self.config.get("gfx_backend") == "dx12" else "Vulkan"
        self.lbl_quick_backend = ctk.CTkLabel(quick_left, text=f"API Gráfica: {quick_backend_text}")
        self.lbl_quick_backend.grid(row=4, column=0, columnspan=2, padx=15, pady=3, sticky="w")

        self.lbl_quick_online = ctk.CTkLabel(quick_left, text="Online: Comprobando...")
        self.lbl_quick_online.grid(row=5, column=0, columnspan=2, padx=15, pady=(3, 8), sticky="w")

        # Quick action right
        quick_right = ctk.CTkFrame(self.tab_main, corner_radius=10, fg_color="#14242e")
        quick_right.grid(row=2, column=1, sticky="nsew", padx=(5, 10), pady=10)
        quick_right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            quick_right, text="Acciones Frecuentes", font=ctk.CTkFont(weight="bold", size=14), text_color="#4fc3d6"
        ).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        btn_goto_install = ctk.CTkButton(
            quick_right,
            text="📦 Seleccionar / Cambiar Carpeta del Dump",
            fg_color="#2b4a58",
            hover_color="#3b6073",
            command=lambda: self.tabview.set("  ⚙️ Instalación & Dump  "),
        )
        btn_goto_install.grid(row=1, column=0, padx=15, pady=5, sticky="ew")

        btn_recompile = ctk.CTkButton(
            quick_right,
            text="🔨 Recompilar Librería del Juego",
            fg_color="#2b4a58",
            hover_color="#3b6073",
            command=self.start_build_process,
        )
        btn_recompile.grid(row=2, column=0, padx=15, pady=5, sticky="ew")

        btn_open_save = ctk.CTkButton(
            quick_right,
            text="📂 Abrir Carpeta de Guardado",
            fg_color="#2b4a58",
            hover_color="#3b6073",
            command=self.open_save_folder,
        )
        btn_open_save.grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        # Gameplay Tip Card
        tip_card = ctk.CTkFrame(self.tab_main, corner_radius=10, fg_color="#0d1820", border_width=1, border_color="#2b4a58")
        tip_card.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        tip_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tip_card, text="💡", font=ctk.CTkFont(size=20)).grid(row=0, column=0, padx=(15, 8), pady=10)
        ctk.CTkLabel(
            tip_card,
            text="Consejo para Puerto Tanzia (Offline): Para jugar las misiones de la taberna (Rango Bajo, Alto y G) en solitario, habla con el marinero del barco y elige 'Puerto Tanzia -> Individual -> Marina o Taberna'. No selecciones 'Multijugador' si estás jugando sin conexión.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#e3d8bd",
            wraplength=760,
            justify="left",
        ).grid(row=0, column=1, padx=5, pady=10, sticky="w")

    # =========================================================================
    # TAB 2: INSTALACIÓN & VERIFICACIÓN DEL DUMP
    # =========================================================================
    def setup_tab_install(self):
        self.scroll_install = ctk.CTkScrollableFrame(self.tab_install, fg_color="transparent")
        self.scroll_install.pack(fill="both", expand=True, padx=4, pady=2)
        self.scroll_install.grid_columnconfigure(0, weight=1)

        # Folder selection frame
        folder_frame = ctk.CTkFrame(self.scroll_install, corner_radius=10, fg_color="#14242e")
        folder_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        folder_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            folder_frame,
            text="Carpeta de Dumps de Monster Hunter 3 Ultimate (USA):",
            font=ctk.CTkFont(weight="bold", size=13),
        ).grid(row=0, column=0, padx=15, pady=(8, 4), sticky="w")

        path_row = ctk.CTkFrame(folder_frame, fg_color="transparent")
        path_row.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 8))
        path_row.grid_columnconfigure(0, weight=1)

        self.entry_games_path = ctk.CTkEntry(
            path_row, placeholder_text="Ej: D:\\Juegos\\WiiU\\Monster Hunter 3 Ultimate Dumps", height=35
        )
        self.entry_games_path.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        if self.config.get("games_dir"):
            self.entry_games_path.insert(0, self.config["games_dir"])

        btn_browse = ctk.CTkButton(
            path_row, text="Examinar...", width=100, height=35, command=self.browse_games_folder
        )
        btn_browse.grid(row=0, column=1)

        # Verification Badges
        badges_frame = ctk.CTkFrame(self.scroll_install, corner_radius=10, fg_color="#14242e")
        badges_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        badges_frame.grid_columnconfigure(0, weight=1)
        badges_frame.grid_columnconfigure(1, weight=1)

        self.lbl_badge_base = ctk.CTkLabel(
            badges_frame,
            text="⚪ Juego Base USA (0005000010118300): No detectado",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e3d8bd",
        )
        self.lbl_badge_base.grid(row=0, column=0, padx=15, pady=6, sticky="w")

        self.lbl_badge_update = ctk.CTkLabel(
            badges_frame,
            text="⚪ Actualización v32 USA (0005000e10118300): No detectada",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e3d8bd",
        )
        self.lbl_badge_update.grid(row=0, column=1, padx=15, pady=6, sticky="w")

        self.lbl_badge_compiler = ctk.CTkLabel(
            badges_frame,
            text="⚪ Compilador Clang: Comprobando...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e3d8bd",
        )
        self.lbl_badge_compiler.grid(row=1, column=0, columnspan=2, padx=15, pady=(2, 8), sticky="w")

        # Compilation actions & progress
        build_box = ctk.CTkFrame(self.scroll_install, corner_radius=10, fg_color="#14242e")
        build_box.grid(row=2, column=0, sticky="ew", padx=10, pady=8)
        build_box.grid_columnconfigure(0, weight=1)

        btn_row = ctk.CTkFrame(build_box, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="ew", padx=15, pady=8)
        btn_row.grid_columnconfigure(0, weight=1)

        self.btn_compile_action = ctk.CTkButton(
            btn_row,
            text="⚡ Traducir y Compilar Port (Crear game.dll)",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            fg_color="#e08e4a",
            hover_color="#eab84c",
            text_color="#0d1820",
            command=self.start_build_process,
        )
        self.btn_compile_action.grid(row=0, column=0, sticky="ew")

        self.btn_download_toolchain = ctk.CTkButton(
            btn_row,
            text="⬇️ Descargar Clang Portátil",
            width=190,
            height=40,
            fg_color="#2b4a58",
            hover_color="#3b6073",
            command=self.start_download_toolchain,
        )
        self.btn_download_toolchain.grid(row=0, column=1, padx=(10, 0))

        self.chk_lto = ctk.CTkCheckBox(
            build_box,
            text="🚀 Optimización Inter-archivos LTO (-flto=thin + -O3) para mayor rendimiento en CPU",
            command=self.save_settings_from_ui,
        )
        self.chk_lto.grid(row=1, column=0, padx=15, pady=(0, 8), sticky="w")
        if self.config.get("build_lto", False):
            self.chk_lto.select()

        self.progress_bar = ctk.CTkProgressBar(build_box, height=12)
        self.progress_bar.grid(row=2, column=0, padx=15, pady=(0, 8), sticky="ew")
        self.progress_bar.set(0)

        # Terminal / Log Text Area
        ctk.CTkLabel(build_box, text="Registro del compilador en tiempo real:", font=ctk.CTkFont(size=12)).grid(
            row=3, column=0, padx=15, pady=(0, 4), sticky="w"
        )

        self.txt_log = ctk.CTkTextbox(
            build_box, height=220, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#0d1820"
        )
        self.txt_log.grid(row=4, column=0, padx=15, pady=(0, 15), sticky="ew")

    # =========================================================================
    # TAB 3: CONFIGURACIÓN GRÁFICA & CONTROLES
    # =========================================================================
    def setup_tab_settings(self):
        self.scroll_settings = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        self.scroll_settings.pack(fill="both", expand=True, padx=4, pady=2)
        self.scroll_settings.grid_columnconfigure(0, weight=1)
        self.scroll_settings.grid_columnconfigure(1, weight=1)

        # Graphics Box
        gfx_box = ctk.CTkFrame(self.scroll_settings, corner_radius=10, fg_color="#14242e")
        gfx_box.grid(row=0, column=0, sticky="new", padx=(5, 5), pady=5)
        gfx_box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            gfx_box, text="Opciones Gráficas", font=ctk.CTkFont(weight="bold", size=15), text_color="#4fc3d6"
        ).grid(row=0, column=0, padx=15, pady=8, sticky="w")

        ctk.CTkLabel(gfx_box, text="Escala de Resolución Interna:", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=1, column=0, padx=15, pady=(5, 2), sticky="w"
        )
        self.opt_scale = ctk.CTkSegmentedButton(
            gfx_box,
            values=["1x (720p)", "2x (1440p 2K)", "3x (4K UHD)", "4x (5K Ultra)"],
            command=self.on_scale_changed,
        )
        self.opt_scale.grid(row=2, column=0, padx=15, pady=(0, 4), sticky="ew")
        scale_map = {
            "1": "1x (720p)",
            "2": "2x (1440p 2K)",
            "3": "3x (4K UHD)",
            "4": "4x (5K Ultra)",
            "1x (Nativo)": "1x (720p)",
            "2x (1440p/4K)": "2x (1440p 2K)",
            "3x (Super)": "3x (4K UHD)",
            "4x (Ultra)": "4x (5K Ultra)",
        }
        self.opt_scale.set(scale_map.get(str(self.config.get("scale", "2")), "2x (1440p 2K)"))

        lbl_scale_info = ctk.CTkLabel(
            gfx_box,
            text="• 1x (720p): Nativo Wii U (Ideal para laptops/iGPU y asegurar 60 FPS)\n• 2x (1440p / 2K): 4x más píxeles (Gran nitidez para monitores 1080p/1440p)\n• 3x (4K UHD): 9x más píxeles | 4x (5K Ultra): 16x más píxeles (GPUs potentes)",
            font=ctk.CTkFont(size=11),
            text_color="#e3d8bd",
            justify="left",
            wraplength=480,
        )
        lbl_scale_info.grid(row=3, column=0, padx=15, pady=(0, 10), sticky="w")

        self.chk_fullscreen = ctk.CTkCheckBox(
            gfx_box, text="Pantalla Completa sin bordes (Borderless)", command=self.save_settings_from_ui
        )
        self.chk_fullscreen.grid(row=4, column=0, padx=15, pady=6, sticky="w")
        if self.config.get("fullscreen", True):
            self.chk_fullscreen.select()

        self.chk_fps = ctk.CTkCheckBox(
            gfx_box, text="Mostrar Contador de FPS en pantalla", command=self.save_settings_from_ui
        )
        self.chk_fps.grid(row=5, column=0, padx=15, pady=6, sticky="w")
        if self.config.get("fps", False):
            self.chk_fps.select()

        # API Gráfica Backend (Vulkan vs DirectX 12)
        ctk.CTkLabel(gfx_box, text="Motor Gráfico (Backend):", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=6, column=0, padx=15, pady=(10, 2), sticky="w"
        )
        self.opt_backend = ctk.CTkSegmentedButton(
            gfx_box,
            values=["Vulkan (Recomendado)", "DirectX 12 (DX12)"],
            command=self.on_backend_changed,
        )
        self.opt_backend.grid(row=7, column=0, padx=15, pady=(0, 4), sticky="ew")
        backend_val = self.config.get("gfx_backend", "vulkan")
        self.opt_backend.set("DirectX 12 (DX12)" if backend_val == "dx12" else "Vulkan (Recomendado)")

        ctk.CTkLabel(
            gfx_box,
            text="💡 Usa DirectX 12 si tienes gráfica integrada Intel o notas tirones con Vulkan.",
            font=ctk.CTkFont(size=11),
            text_color="#e3d8bd",
            justify="left",
            wraplength=480,
        ).grid(row=8, column=0, padx=15, pady=(0, 6), sticky="w")

        # Sincronización Vertical (VSync / Present Mode)
        ctk.CTkLabel(gfx_box, text="Sincronización Vertical (VSync):", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=9, column=0, padx=15, pady=(8, 2), sticky="w"
        )
        self.opt_present = ctk.CTkSegmentedButton(
            gfx_box,
            values=["Mailbox (Fast-Sync)", "VSync Clásico (Fifo)", "Desactivado (OFF)"],
            command=self.on_present_changed,
        )
        self.opt_present.grid(row=10, column=0, padx=15, pady=(0, 4), sticky="ew")
        present_val = self.config.get("present_mode", "mailbox")
        present_map = {"mailbox": "Mailbox (Fast-Sync)", "fifo": "VSync Clásico (Fifo)", "immediate": "Desactivado (OFF)"}
        self.opt_present.set(present_map.get(present_val, "Mailbox (Fast-Sync)"))

        ctk.CTkLabel(
            gfx_box,
            text="💡 Mailbox evita tirones y reduce la latencia al mínimo sin cortes de pantalla.",
            font=ctk.CTkFont(size=11),
            text_color="#e3d8bd",
            justify="left",
            wraplength=480,
        ).grid(row=11, column=0, padx=15, pady=(0, 6), sticky="w")

        # Perfiles de Calidad / Rendimiento FSR
        ctk.CTkLabel(gfx_box, text="Perfil / Modo FSR (Presets):", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=12, column=0, padx=15, pady=(8, 2), sticky="w"
        )
        self.opt_fsr_preset = ctk.CTkSegmentedButton(
            gfx_box,
            values=["Rendimiento (1x+FSR)", "Calidad (2x+FSR)", "Ultra (3x+FSR)", "Manual"],
            command=self.on_fsr_preset_changed,
        )
        self.opt_fsr_preset.grid(row=13, column=0, padx=15, pady=(0, 4), sticky="ew")

        # Reescalado & Nitidez (FSR 1.0 / CAS)
        ctk.CTkLabel(gfx_box, text="Tecnología de Reescalado & Nitidez:", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=14, column=0, padx=15, pady=(8, 2), sticky="w"
        )
        self.opt_upscaler = ctk.CTkSegmentedButton(
            gfx_box,
            values=["FSR 1.0 (EASU + RCAS)", "AMD CAS (Solo Nitidez)", "Desactivado (Nativo)"],
            command=self.on_upscaler_changed,
        )
        self.opt_upscaler.grid(row=15, column=0, padx=15, pady=(0, 4), sticky="ew")
        upscaler_val = self.config.get("upscaler", "fsr")
        if upscaler_val == "cas":
            self.opt_upscaler.set("AMD CAS (Solo Nitidez)")
        elif upscaler_val == "off":
            self.opt_upscaler.set("Desactivado (Nativo)")
        else:
            self.opt_upscaler.set("FSR 1.0 (EASU + RCAS)")

        ctk.CTkLabel(
            gfx_box,
            text="💡 FSR 1.0 ejecuta EASU + RCAS (CAS) en conjunto. 'AMD CAS' por separado es para nitidez sin reescalado.",
            font=ctk.CTkFont(size=11),
            text_color="#e3d8bd",
            justify="left",
            wraplength=480,
        ).grid(row=16, column=0, padx=15, pady=(0, 6), sticky="w")

        # FSR / CAS Sharpness Slider Card
        sharp_card = ctk.CTkFrame(gfx_box, fg_color="#0d1820", corner_radius=8)
        sharp_card.grid(row=17, column=0, padx=15, pady=(0, 10), sticky="ew")
        sharp_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            sharp_card,
            text="Nitidez de Reescalado (FSR / CAS):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=10, pady=(6, 2), sticky="w")

        raw_sharp = self.config.get("fsr_sharpness", 75)
        self.lbl_sharpness_val = ctk.CTkLabel(
            sharp_card,
            text=f"{raw_sharp}%",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#4fc3d6",
        )
        self.lbl_sharpness_val.grid(row=0, column=1, padx=10, pady=(6, 2), sticky="e")

        self.slider_sharpness = ctk.CTkSlider(
            sharp_card,
            from_=20,
            to=100,
            number_of_steps=80,
            command=self.on_fsr_sharpness_changed,
        )
        self.slider_sharpness.set(raw_sharp)
        self.slider_sharpness.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 8), sticky="ew")

        # Audio Box
        ctk.CTkLabel(gfx_box, text="Audio & Efectos", font=ctk.CTkFont(weight="bold", size=13)).grid(
            row=18, column=0, padx=15, pady=(10, 2), sticky="w"
        )

        self.chk_audio = ctk.CTkCheckBox(
            gfx_box, text="Sonido Activado (CPAL WASAPI)", command=self.save_settings_from_ui
        )
        self.chk_audio.grid(row=19, column=0, padx=15, pady=5, sticky="w")
        if self.config.get("audio", True):
            self.chk_audio.select()

        self.chk_audio_fx = ctk.CTkCheckBox(
            gfx_box, text="Efectos de Reverberación y Filtros", command=self.save_settings_from_ui
        )
        self.chk_audio_fx.grid(row=23, column=0, padx=15, pady=5, sticky="w")
        if self.config.get("audio_fx", True):
            self.chk_audio_fx.select()

        self.update_fsr_preset_indicator()

        # Input & Mods Box
        right_box = ctk.CTkFrame(self.scroll_settings, corner_radius=10, fg_color="#14242e")
        right_box.grid(row=0, column=1, sticky="new", padx=(5, 5), pady=5)
        right_box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right_box, text="Controles & Mandos", font=ctk.CTkFont(weight="bold", size=15), text_color="#7fcfa6"
        ).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        ctk.CTkLabel(right_box, text="Disposición de Botones del Mando:").grid(
            row=1, column=0, padx=15, pady=(5, 2), sticky="w"
        )
        self.opt_pad = ctk.CTkSegmentedButton(
            right_box,
            values=["Xbox (A abajo, B der)", "Nintendo (B abajo, A der)"],
            command=self.on_pad_changed,
        )
        self.opt_pad.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="ew")
        self.opt_pad.set("Xbox (A abajo, B der)" if self.config.get("pad_layout") == "xbox" else "Nintendo (B abajo, A der)")

        # Mouse Camera Sensitivity Slider
        sens_card = ctk.CTkFrame(right_box, fg_color="#0d1820", corner_radius=8)
        sens_card.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")
        sens_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            sens_card,
            text="Sensibilidad de Cámara (Ratón):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=10, pady=(6, 2), sticky="w")

        raw_sens = self.config.get("mouse_sensitivity", 0.0008)
        self.lbl_sens_val = ctk.CTkLabel(
            sens_card,
            text=f"{int(round(raw_sens * 10000))}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#4fc3d6",
        )
        self.lbl_sens_val.grid(row=0, column=1, padx=10, pady=(6, 2), sticky="e")

        self.slider_sens = ctk.CTkSlider(
            sens_card,
            from_=2,
            to=30,
            number_of_steps=28,
            command=self.on_mouse_sens_changed,
        )
        self.slider_sens.set(int(round(raw_sens * 10000)))
        self.slider_sens.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(
            right_box, text="Mejoras & Mods Nativos", font=ctk.CTkFont(weight="bold", size=15), text_color="#eab84c"
        ).grid(row=4, column=0, padx=15, pady=(10, 5), sticky="w")

        self.chk_overlay = ctk.CTkCheckBox(
            right_box, text="Overlay de Lista de Deseos de Forja (Tecla F1)", command=self.save_settings_from_ui
        )
        self.chk_overlay.grid(row=5, column=0, padx=15, pady=6, sticky="w")
        if self.config.get("overlay", True):
            self.chk_overlay.select()

        self.chk_native_menu = ctk.CTkCheckBox(
            right_box,
            text="Menú de Mods en Pausa (Mantener R-Shift/ZL en Menú Pausa -> Cazador)",
            command=self.save_settings_from_ui,
        )
        self.chk_native_menu.grid(row=6, column=0, padx=15, pady=6, sticky="w")
        if self.config.get("native_menu", True):
            self.chk_native_menu.select()

        self.chk_native_text = ctk.CTkCheckBox(
            right_box, text="Estado de Forja en el menú de objetos del juego", command=self.save_settings_from_ui
        )
        self.chk_native_text.grid(row=7, column=0, padx=15, pady=6, sticky="w")
        if self.config.get("native_text", True):
            self.chk_native_text.select()

        # Hunter Name Field (Auto-fills character creation and displays detected save)
        ctk.CTkLabel(
            right_box, text="Nombre del Cazador (Nombre en Creación / Partida):", font=ctk.CTkFont(weight="bold", size=13), text_color="#4fc3d6"
        ).grid(row=8, column=0, padx=15, pady=(15, 2), sticky="w")
        self.entry_hunter_name_cfg = ctk.CTkEntry(right_box, width=280)
        self.entry_hunter_name_cfg.grid(row=9, column=0, padx=15, pady=(0, 10), sticky="w")
        current_hunter = self.config.get("hunter_name", "Hunter")
        if current_hunter == "Hunter":
            detected_h = get_hunter_name_from_save(self.config.get("out_dir", DEFAULT_OUT_DIR))
            if detected_h:
                current_hunter = detected_h
                self.config["hunter_name"] = detected_h
        self.entry_hunter_name_cfg.insert(0, current_hunter)
        self.entry_hunter_name_cfg.bind("<KeyRelease>", lambda e: self.save_settings_from_ui())

        # Discord Rich Presence Section
        ctk.CTkLabel(
            right_box, text="Discord Rich Presence (Estado en Discord):", font=ctk.CTkFont(weight="bold", size=13), text_color="#5865f2"
        ).grid(row=10, column=0, padx=15, pady=(12, 2), sticky="w")
        self.chk_discord_rpc = ctk.CTkCheckBox(
            right_box,
            text="Mostrar estado en Discord (Rich Presence)",
            command=self.save_settings_from_ui,
        )
        self.chk_discord_rpc.grid(row=11, column=0, padx=15, pady=(4, 15), sticky="w")
        if self.config.get("discord_rpc", True):
            self.chk_discord_rpc.select()

    # =========================================================================
    # TAB 4: MODO ONLINE / MULTIJUGADOR (ARQUITECTURA MATT-WOOD-23)
    # =========================================================================
    def setup_tab_online(self):
        self.scroll_online = ctk.CTkScrollableFrame(self.tab_online, fg_color="transparent")
        self.scroll_online.pack(fill="both", expand=True, padx=4, pady=2)
        self.scroll_online.grid_columnconfigure(0, weight=1)

        # Informative Notice
        info_banner = ctk.CTkFrame(self.scroll_online, corner_radius=10, fg_color="#1b3441")
        info_banner.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 10))
        info_banner.grid_columnconfigure(1, weight=1)

        icon_lbl = ctk.CTkLabel(info_banner, text="🌐", font=ctk.CTkFont(size=36))
        icon_lbl.grid(row=0, column=0, rowspan=2, padx=15, pady=10)

        ctk.CTkLabel(
            info_banner,
            text="Multijugador Online de Tanzia (Protocolo Matt-Wood-23 / mh3u-revival)",
            font=ctk.CTkFont(weight="bold", size=15),
            text_color="#4fc3d6",
        ).grid(row=0, column=1, sticky="w", pady=(10, 2))

        ctk.CTkLabel(
            info_banner,
            text="Módulo de red con soporte P2P y servidor relay de baja latencia. Permite crear o unirte a partidas de hasta 4 cazadores. Para jugar por Internet sin abrir puertos en el router, se recomienda que tú y tus amigos usen una red virtual como Radmin VPN, ZeroTier o Tailscale.",
            font=ctk.CTkFont(size=12),
            text_color="#e3d8bd",
            wraplength=640,
            justify="left",
        ).grid(row=1, column=1, sticky="w", pady=(0, 10))

        # Top Control Card: Master Switch & Mode Segmented Button
        top_card = ctk.CTkFrame(self.scroll_online, corner_radius=10, fg_color="#14242e")
        top_card.grid(row=1, column=0, sticky="ew", padx=6, pady=6)
        top_card.grid_columnconfigure(0, weight=1)

        self.switch_online = ctk.CTkSwitch(
            top_card,
            text="Habilitar Modo Multijugador Online al iniciar el juego",
            font=ctk.CTkFont(weight="bold", size=13),
            command=self.on_online_switch_toggled,
        )
        self.switch_online.grid(row=0, column=0, padx=15, pady=12, sticky="w")
        if self.config.get("online_enabled", False):
            self.switch_online.select()

        # Mode Selector
        ctk.CTkLabel(
            top_card, text="Selecciona tu función en la partida:", font=ctk.CTkFont(weight="bold", size=12), text_color="#9db3ba"
        ).grid(row=1, column=0, padx=15, pady=(4, 4), sticky="w")

        current_mode = self.config.get("online_mode", "client")
        init_mode_val = "👑 Crear Servidor de Sala (Host)" if current_mode == "host" else "🎮 Unirse a una Sala (Cliente)"
        self.seg_online_mode = ctk.CTkSegmentedButton(
            top_card,
            values=["🎮 Unirse a una Sala (Cliente)", "👑 Crear Servidor de Sala (Host)"],
            font=ctk.CTkFont(weight="bold", size=13),
            command=self.on_online_mode_changed,
        )
        self.seg_online_mode.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="ew")
        self.seg_online_mode.set(init_mode_val)

        # ---------------------------------------------------------------------
        # CLIENT MODE FRAME
        # ---------------------------------------------------------------------
        self.frame_client_mode = ctk.CTkFrame(self.scroll_online, corner_radius=10, fg_color="#14242e")
        self.frame_client_mode.grid(row=2, column=0, sticky="ew", padx=6, pady=6)
        self.frame_client_mode.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.frame_client_mode,
            text="🎮 Conexión a la Partida de tu Amigo (Cliente)",
            font=ctk.CTkFont(weight="bold", size=14),
            text_color="#7fcfa6",
        ).grid(row=0, column=0, columnspan=2, padx=15, pady=(12, 6), sticky="w")

        # Host IP
        ctk.CTkLabel(self.frame_client_mode, text="IP del Anfitrión / Amigo:").grid(row=1, column=0, padx=15, pady=6, sticky="w")
        host_row = ctk.CTkFrame(self.frame_client_mode, fg_color="transparent")
        host_row.grid(row=1, column=1, padx=15, pady=6, sticky="w")
        self.entry_server_host = ctk.CTkEntry(host_row, width=220)
        self.entry_server_host.pack(side="left", padx=(0, 8))
        self.entry_server_host.insert(0, self.config.get("online_server", "127.0.0.1"))

        self.btn_ping_host = ctk.CTkButton(
            host_row,
            text="🔍 Probar Ping",
            width=110,
            fg_color="#2b4a58",
            hover_color="#3b6073",
            command=self.test_host_ping,
        )
        self.btn_ping_host.pack(side="left")

        # Ping status label
        self.lbl_ping_result = ctk.CTkLabel(
            self.frame_client_mode, text="Estado: Listo para probar conexión", font=ctk.CTkFont(size=12), text_color="#9db3ba"
        )
        self.lbl_ping_result.grid(row=2, column=1, padx=15, pady=(0, 6), sticky="w")

        # Room ID
        ctk.CTkLabel(self.frame_client_mode, text="ID de Sala / Taberna:").grid(row=4, column=0, padx=15, pady=6, sticky="w")
        self.entry_room_id = ctk.CTkEntry(self.frame_client_mode, width=120)
        self.entry_room_id.grid(row=4, column=1, padx=15, pady=6, sticky="w")
        self.entry_room_id.insert(0, self.config.get("online_room_id", "1001"))

        # Hunter Tag
        ctk.CTkLabel(self.frame_client_mode, text="Tu Nombre de Cazador:").grid(row=5, column=0, padx=15, pady=(6, 15), sticky="w")
        self.entry_hunter_name = ctk.CTkEntry(self.frame_client_mode, width=220)
        self.entry_hunter_name.grid(row=5, column=1, padx=15, pady=(6, 15), sticky="w")
        detected_h = get_hunter_name_from_save(self.config.get("out_dir", DEFAULT_OUT_DIR))
        hunter_val = self.config.get("online_hunter_name") or detected_h or "Hunter"
        self.entry_hunter_name.insert(0, hunter_val)

        # ---------------------------------------------------------------------
        # HOST MODE FRAME
        # ---------------------------------------------------------------------
        self.frame_host_mode = ctk.CTkFrame(self.scroll_online, corner_radius=10, fg_color="#14242e")
        self.frame_host_mode.grid(row=3, column=0, sticky="ew", padx=6, pady=6)
        self.frame_host_mode.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.frame_host_mode,
            text="👑 Servidor de Salas Integrado (Crear Partida)",
            font=ctk.CTkFont(weight="bold", size=14),
            text_color="#eab84c",
        ).grid(row=0, column=0, columnspan=2, padx=15, pady=(12, 4), sticky="w")

        ctk.CTkLabel(
            self.frame_host_mode,
            text="Inicia el servidor de retransmisión local para que tus amigos se conecten contigo a Puerto Tanzia.",
            font=ctk.CTkFont(size=12),
            text_color="#9db3ba",
        ).grid(row=1, column=0, columnspan=2, padx=15, pady=(0, 10), sticky="w")

        # Local IPs Detected
        ctk.CTkLabel(self.frame_host_mode, text="Tu IP para amigos:").grid(row=2, column=0, padx=15, pady=6, sticky="w")
        ip_row = ctk.CTkFrame(self.frame_host_mode, fg_color="transparent")
        ip_row.grid(row=2, column=1, padx=15, pady=6, sticky="w")

        detected_ips = get_local_ip_addresses()
        self.opt_local_ips = ctk.CTkOptionMenu(ip_row, values=detected_ips, width=270)
        self.opt_local_ips.pack(side="left", padx=(0, 8))
        if detected_ips:
            self.opt_local_ips.set(detected_ips[0])

        btn_copy_ip = ctk.CTkButton(
            ip_row, text="📋 Copiar IP", width=95, fg_color="#2b4a58", hover_color="#3b6073", command=self.copy_selected_ip
        )
        btn_copy_ip.pack(side="left")

        self.lbl_copy_feedback = ctk.CTkLabel(ip_row, text="", font=ctk.CTkFont(size=11), text_color="#7fcfa6")
        self.lbl_copy_feedback.pack(side="left", padx=8)

        # Default Room
        ctk.CTkLabel(self.frame_host_mode, text="ID de Sala por Defecto:").grid(row=4, column=0, padx=15, pady=6, sticky="w")
        self.entry_host_room = ctk.CTkEntry(self.frame_host_mode, width=120)
        self.entry_host_room.grid(row=4, column=1, padx=15, pady=6, sticky="w")
        self.entry_host_room.insert(0, self.config.get("online_room_id", "1001"))

        # Server Control Actions
        action_row = ctk.CTkFrame(self.frame_host_mode, fg_color="transparent")
        action_row.grid(row=5, column=0, columnspan=2, padx=15, pady=(10, 8), sticky="w")

        self.btn_toggle_server = ctk.CTkButton(
            action_row,
            text="▶  Iniciar Servidor de Sala (Host)",
            font=ctk.CTkFont(weight="bold", size=13),
            fg_color="#2f9488",
            hover_color="#257a70",
            command=self.toggle_host_server,
        )
        self.btn_toggle_server.pack(side="left", padx=(0, 15))

        self.lbl_server_status = ctk.CTkLabel(
            action_row,
            text="⚪ Servidor Inactivo",
            font=ctk.CTkFont(weight="bold", size=12),
            text_color="#9db3ba",
        )
        self.lbl_server_status.pack(side="left")

        # Real-time Server Log Console
        ctk.CTkLabel(
            self.frame_host_mode, text="Registro del Servidor en Tiempo Real:", font=ctk.CTkFont(weight="bold", size=12), text_color="#4fc3d6"
        ).grid(row=6, column=0, columnspan=2, padx=15, pady=(8, 2), sticky="w")

        self.txt_server_log = ctk.CTkTextbox(self.frame_host_mode, height=130, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_server_log.grid(row=7, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="ew")

        # Save Button at Bottom
        btn_save_online = ctk.CTkButton(
            self.scroll_online,
            text="💾 Guardar Parámetros de Red",
            fg_color="#2b4a58",
            hover_color="#3b6073",
            font=ctk.CTkFont(weight="bold", size=13),
            command=self.save_online_settings,
        )
        btn_save_online.grid(row=4, column=0, padx=6, pady=(10, 15), sticky="w")

        # Apply visibility based on initial mode
        self.on_online_mode_changed(init_mode_val)

    # =========================================================================
    # TAB 5: PARTIDAS & LOGS
    # =========================================================================
    def setup_tab_tools(self):
        self.tab_tools.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(self.tab_tools, corner_radius=10, fg_color="#14242e")
        card.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card, text="Gestión de Datos y Partidas", font=ctk.CTkFont(weight="bold", size=15), text_color="#4fc3d6"
        ).grid(row=0, column=0, columnspan=2, padx=15, pady=12, sticky="w")

        btn_open_saves = ctk.CTkButton(
            card, text="📂 Abrir Carpeta de Saves", width=220, command=self.open_save_folder
        )
        btn_open_saves.grid(row=1, column=0, padx=15, pady=8, sticky="w")
        ctk.CTkLabel(card, text="Ubicación donde el port guarda tu progreso y personaje.").grid(
            row=1, column=1, padx=10, pady=8, sticky="w"
        )

        btn_backup_saves = ctk.CTkButton(
            card, text="🛡️ Respaldar Partidas Ahora", width=220, fg_color="#7fcfa6", hover_color="#7fcfa6", text_color="#0d1820", command=self.backup_save_folder
        )
        btn_backup_saves.grid(row=2, column=0, padx=15, pady=8, sticky="w")
        ctk.CTkLabel(card, text="Crea un archivo comprimido .zip con la fecha actual.").grid(
            row=2, column=1, padx=10, pady=8, sticky="w"
        )

        btn_open_logs = ctk.CTkButton(
            card, text="📄 Abrir Registro (Log Reciente)", width=220, fg_color="#2b4a58", command=self.open_latest_log
        )
        btn_open_logs.grid(row=3, column=0, padx=15, pady=8, sticky="w")
        ctk.CTkLabel(card, text="Abre 'mh3u_latest.log' para revisar errores de Vulkan o del juego.").grid(
            row=3, column=1, padx=10, pady=8, sticky="w"
        )

        btn_clean_cache = ctk.CTkButton(
            card, text="🧹 Limpiar Caché de Shaders", width=220, fg_color="#e0675c", hover_color="#a9493f", command=self.clean_cache
        )
        btn_clean_cache.grid(row=4, column=0, padx=15, pady=8, sticky="w")
        ctk.CTkLabel(card, text="Elimina la caché de pipelines si notas artefactos gráficos.").grid(
            row=4, column=1, padx=10, pady=8, sticky="w"
        )

        # Developer & Community Credits Card
        credits_card = ctk.CTkFrame(self.tab_tools, corner_radius=10, fg_color="#14242e")
        credits_card.grid(row=1, column=0, sticky="ew", padx=10, pady=(10, 10))
        credits_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            credits_card, text="Créditos y Agradecimientos", font=ctk.CTkFont(weight="bold", size=15), text_color="#4fc3d6"
        ).grid(row=0, column=0, columnspan=2, padx=15, pady=12, sticky="w")

        # Launcher Development
        ctk.CTkLabel(
            credits_card,
            text="Desarrollo del Launcher:",
            font=ctk.CTkFont(weight="bold", size=13),
            text_color="#eab84c",
        ).grid(row=1, column=0, padx=15, pady=5, sticky="w")
        ctk.CTkLabel(
            credits_card,
            text="g30wolff99",
            font=ctk.CTkFont(weight="bold", size=13),
            text_color="#7fcfa6",
        ).grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # glinesbdev
        ctk.CTkLabel(
            credits_card,
            text="Port Nativo & Recompilación PC:",
            font=ctk.CTkFont(weight="bold", size=13),
            text_color="#e3d8bd",
        ).grid(row=2, column=0, padx=15, pady=5, sticky="w")
        glines_btn = ctk.CTkButton(
            credits_card,
            text="glinesbdev / mh3u-port ↗",
            fg_color="#22414f",
            hover_color="#3b6073",
            height=26,
            command=lambda: webbrowser.open_new_tab("https://github.com/glinesbdev/mh3u-port"),
        )
        glines_btn.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        # Matt Wood
        ctk.CTkLabel(
            credits_card,
            text="Lógica de Red & Servidor Online:",
            font=ctk.CTkFont(weight="bold", size=13),
            text_color="#e3d8bd",
        ).grid(row=3, column=0, padx=15, pady=5, sticky="w")
        matt_btn = ctk.CTkButton(
            credits_card,
            text="Matt-Wood-23 / mh3u-revival ↗",
            fg_color="#22414f",
            hover_color="#3b6073",
            height=26,
            command=lambda: webbrowser.open_new_tab("https://github.com/Matt-Wood-23/mh3u-revival"),
        )
        matt_btn.grid(row=3, column=1, padx=10, pady=5, sticky="w")

        # Version
        ctk.CTkLabel(
            credits_card,
            text="Versión del Launcher:",
            font=ctk.CTkFont(weight="bold", size=13),
            text_color="#4fc3d6",
        ).grid(row=4, column=0, padx=15, pady=5, sticky="w")
        ctk.CTkLabel(
            credits_card,
            text=f"{APP_VERSION} (Recompilación Nativa PC)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#eab84c",
        ).grid(row=4, column=1, padx=10, pady=5, sticky="w")

        # Remote updates
        if updater:
            ctk.CTkLabel(
                credits_card,
                text="Actualizaciones:",
                font=ctk.CTkFont(weight="bold", size=13),
                text_color="#4fc3d6",
            ).grid(row=5, column=0, padx=15, pady=(5, 12), sticky="w")
            upd_frame = ctk.CTkFrame(credits_card, fg_color="transparent")
            upd_frame.grid(row=5, column=1, padx=10, pady=(5, 12), sticky="w")
            self.btn_update = ctk.CTkButton(
                upd_frame, text="Buscar actualizaciones", height=26, command=lambda: self.check_for_updates(silent=False)
            )
            self.btn_update.pack(side="left")
            self.lbl_update_status = ctk.CTkLabel(upd_frame, text="", font=ctk.CTkFont(size=12), text_color="#e3d8bd")
            self.lbl_update_status.pack(side="left", padx=10)

    # =========================================================================
    # REMOTE UPDATES
    # =========================================================================
    def check_for_updates(self, silent=False):
        if not updater or getattr(self, "_update_busy", False):
            return
        self._update_busy = True
        self.ui_queue.put(("update_btn", {"state": "disabled"}))
        self.ui_queue.put(("update_state", {"text": "Buscando..."}))

        def worker():
            try:
                manifest = updater.fetch_manifest()
                if not updater.is_newer(manifest, APP_VERSION):
                    self.ui_queue.put(("update_state", {"text": f"Estás al día ({APP_VERSION})"}))
                    self._update_busy = False
                    self.ui_queue.put(("update_btn", {"state": "normal"}))
                    return
                todo = updater.files_to_update(manifest, get_base_dir())
                self._update_busy = False
                self.ui_queue.put(("update_btn", {"state": "normal"}))
                self.ui_queue.put(("update_state", {"text": f"Disponible: {manifest['version']}"}))
                if not silent or todo:
                    self.ui_queue.put(("update_prompt", (manifest, todo)))
            except Exception as e:
                self._update_busy = False
                self.ui_queue.put(("update_btn", {"state": "normal"}))
                self.ui_queue.put(("update_state", {"text": "Sin conexión" if silent else f"Error: {e}"}))

        threading.Thread(target=worker, daemon=True).start()

    def _prompt_update(self, manifest, todo):
        size_mb = sum(int(e.get("size") or 0) for e in todo) / (1024 * 1024)
        notes = manifest.get("notes", "").strip()
        msg = (
            f"Nueva versión {manifest['version']} (actual {APP_VERSION}).\n"
            f"Se descargarán {len(todo)} archivo(s), {size_mb:.1f} MB.\n\n"
            + (f"{notes}\n\n" if notes else "")
            + "Tu configuración, game.dll y toolchain no se tocan. El launcher se cerrará y reabrirá solo.\n¿Actualizar ahora?"
        )
        if self.is_running or self.is_compiling:
            messagebox.showwarning("Actualización", "Cierra el juego y espera a que termine la compilación antes de actualizar.")
            return
        if not todo:
            messagebox.showinfo("Actualización", "Los archivos ya están al día.")
            return
        if not messagebox.askyesno("Actualización disponible", msg):
            return
        self._update_busy = True
        self.ui_queue.put(("update_btn", {"state": "disabled"}))

        def worker():
            try:
                def progress(frac, name):
                    self.ui_queue.put(("update_state", {"text": f"Descargando {name} ({int(frac * 100)}%)"}))

                updater.download_files(todo, get_base_dir(), progress)
                script = updater.write_apply_script(todo, get_base_dir(), manifest["version"])
                self.ui_queue.put(("update_state", {"text": "Aplicando... el launcher se reiniciará"}))
                self.after(0, lambda: self._finish_update(script))
            except Exception as e:
                self._update_busy = False
                self.ui_queue.put(("update_btn", {"state": "normal"}))
                self.ui_queue.put(("update_state", {"text": "Falló la actualización"}))
                self.ui_queue.put(("error", ("Actualización", f"No se pudo actualizar (no se modificó nada):\n{e}")))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_update(self, script):
        updater.launch_apply_script(script)
        self.on_app_close()

    # =========================================================================
    # EVENT HANDLERS & LOGIC
    # =========================================================================
    def on_scale_changed(self, value):
        mapping = {
            "1x (720p)": "1",
            "2x (1440p 2K)": "2",
            "3x (4K UHD)": "3",
            "4x (5K Ultra)": "4",
            "1x (Nativo)": "1",
            "2x (1440p/4K)": "2",
            "3x (Super)": "3",
            "4x (Ultra)": "4",
        }
        self.config["scale"] = mapping.get(value, "2")
        self.update_fsr_preset_indicator()
        self.save_config()
        self.lbl_quick_scale.configure(text=f"Resolución: {value}")

    def on_fsr_preset_changed(self, value):
        if "Rendimiento" in value:
            self.opt_scale.set("1x (720p)")
            self.config["scale"] = "1"
            self.opt_upscaler.set("FSR 1.0 (EASU + RCAS)")
            self.config["upscaler"] = "fsr"
            self.lbl_quick_scale.configure(text="Resolución: 1x (720p)")
        elif "Calidad" in value:
            self.opt_scale.set("2x (1440p 2K)")
            self.config["scale"] = "2"
            self.opt_upscaler.set("FSR 1.0 (EASU + RCAS)")
            self.config["upscaler"] = "fsr"
            self.lbl_quick_scale.configure(text="Resolución: 2x (1440p 2K)")
        elif "Ultra" in value:
            self.opt_scale.set("3x (4K UHD)")
            self.config["scale"] = "3"
            self.opt_upscaler.set("FSR 1.0 (EASU + RCAS)")
            self.config["upscaler"] = "fsr"
            self.lbl_quick_scale.configure(text="Resolución: 3x (4K UHD)")
        self.save_config()

    def update_fsr_preset_indicator(self):
        if not hasattr(self, "opt_fsr_preset"):
            return
        scale = str(self.config.get("scale", "2"))
        upscaler = self.config.get("upscaler", "fsr")
        if upscaler == "fsr":
            if scale == "1":
                self.opt_fsr_preset.set("Rendimiento (1x+FSR)")
            elif scale == "2":
                self.opt_fsr_preset.set("Calidad (2x+FSR)")
            elif scale == "3":
                self.opt_fsr_preset.set("Ultra (3x+FSR)")
            else:
                self.opt_fsr_preset.set("Manual")
        else:
            self.opt_fsr_preset.set("Manual")

    def on_pad_changed(self, value):
        self.config["pad_layout"] = "xbox" if "Xbox" in value else "nintendo"
        self.save_config()
        self.lbl_quick_pad.configure(text=f"Mando: Disposición {'Xbox' if self.config['pad_layout'] == 'xbox' else 'Nintendo'}")

    def on_backend_changed(self, value):
        self.config["gfx_backend"] = "dx12" if "DirectX" in value else "vulkan"
        self.save_config()
        if hasattr(self, "lbl_quick_backend"):
            self.lbl_quick_backend.configure(text=f"API Gráfica: {'DirectX 12' if self.config['gfx_backend'] == 'dx12' else 'Vulkan'}")

    def on_mouse_sens_changed(self, value):
        sens_int = int(round(value))
        sens_float = round(sens_int / 10000.0, 5)
        self.lbl_sens_val.configure(text=f"{sens_int}")
        self.config["mouse_sensitivity"] = sens_float
        self.save_config()
        self._sync_bindings_mouse_sensitivity(sens_float)

    def _sync_bindings_mouse_sensitivity(self, sens_float):
        out_dir = self.config.get("out_dir", DEFAULT_OUT_DIR)
        bindings_paths = [
            os.path.join(out_dir, "input", "bindings.json"),
            os.path.join(DEFAULT_OUT_DIR, "input", "bindings.json"),
        ]
        for bp in bindings_paths:
            if os.path.exists(bp):
                try:
                    with open(bp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["mouse_sensitivity"] = sens_float
                    with open(bp, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                except Exception as e:
                    print(f"Error syncing bindings.json: {e}")

    def on_present_changed(self, value):
        if "Mailbox" in value:
            self.config["present_mode"] = "mailbox"
        elif "OFF" in value:
            self.config["present_mode"] = "immediate"
        else:
            self.config["present_mode"] = "fifo"
        self.save_config()

    def on_upscaler_changed(self, value):
        if "FSR" in value:
            self.config["upscaler"] = "fsr"
        elif "CAS" in value:
            self.config["upscaler"] = "cas"
        else:
            self.config["upscaler"] = "off"
        self.update_fsr_preset_indicator()
        self.save_config()

    def on_fsr_sharpness_changed(self, value):
        val_int = int(round(value))
        self.lbl_sharpness_val.configure(text=f"{val_int}%")
        self.config["fsr_sharpness"] = val_int
        self.save_config()

    def save_settings_from_ui(self):
        self.config["fullscreen"] = bool(self.chk_fullscreen.get())
        self.config["fps"] = bool(self.chk_fps.get())
        self.config["audio"] = bool(self.chk_audio.get())
        self.config["audio_fx"] = bool(self.chk_audio_fx.get())
        self.config["overlay"] = bool(self.chk_overlay.get())
        self.config["native_menu"] = bool(self.chk_native_menu.get())
        self.config["native_text"] = bool(self.chk_native_text.get())
        if hasattr(self, "chk_lto"):
            self.config["build_lto"] = bool(self.chk_lto.get())
        if hasattr(self, "chk_discord_rpc"):
            self.config["discord_rpc"] = bool(self.chk_discord_rpc.get())
        if hasattr(self, "entry_hunter_name_cfg"):
            val = self.entry_hunter_name_cfg.get().strip() or "Hunter"
            self.config["hunter_name"] = val
            self.config["online_hunter_name"] = val
            if hasattr(self, "entry_hunter_name"):
                self.entry_hunter_name.delete(0, tk.END)
                self.entry_hunter_name.insert(0, val)
        self.save_config()

        mods_text = "F1 Wishlist" if self.config["overlay"] else "Sin overlay"
        if self.config["native_menu"]:
            mods_text += " + Menú Nativo"
        self.lbl_quick_mods.configure(text=f"Mods: {mods_text}")

    def on_online_mode_changed(self, value):
        if "Host" in value:
            self.frame_client_mode.grid_remove()
            self.frame_host_mode.grid()
            self.config["online_mode"] = "host"
        else:
            self.frame_host_mode.grid_remove()
            self.frame_client_mode.grid()
            self.config["online_mode"] = "client"
        self.save_config()

    def copy_selected_ip(self):
        val = self.opt_local_ips.get()
        if val:
            ip_only = val.split()[0]
            self.clipboard_clear()
            self.clipboard_append(ip_only)
            self.lbl_copy_feedback.configure(text=f"¡Copiado: {ip_only}!")
            self.after(3000, lambda: self.lbl_copy_feedback.configure(text=""))

    def test_host_ping(self):
        host = self.entry_server_host.get().strip()
        if not host:
            self.lbl_ping_result.configure(
                text="⚠️ Ingresa la dirección IP del Anfitrión para probar conexión",
                text_color="#eab84c"
            )
            return

        self.btn_ping_host.configure(text="Probando...", state="disabled")
        self.lbl_ping_result.configure(text=f"Conectando a {host}...", text_color="#eab84c")

        def worker():
            t0 = time.time()
            is_local = host in ["127.0.0.1", "localhost"]
            if not is_local:
                try:
                    detected = [x.split()[0] for x in get_local_ip_addresses()]
                    if host in detected:
                        is_local = True
                except Exception:
                    pass

            if is_local:
                if self.server_process:
                    self.ui_queue.put(("ping_result", (True, 1, "Servidor NEX ACTIVO (UDP 1223/1224)")))
                else:
                    self.ui_queue.put(("ping_result", (True, 1, "Localhost listo (Se iniciará automáticamente al pulsar JUGAR)")))
                return

            try:
                creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                proc = subprocess.run(
                    ["ping", "-n", "3", "-w", "3000", host],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=creationflags
                )
                times = [int(x) for x in re.findall(r"(?:tiempo|time)[=<] *([0-9]+) *ms", proc.stdout or "", re.I)]
                elapsed = max(1, round(sum(times) / len(times))) if times else 0
                if proc.returncode == 0 and times:
                    self.ui_queue.put(("ping_result", (True, elapsed, host)))
                else:
                    self.ui_queue.put(("ping_result", (False, 0, f"Host inalcanzable ({host}) - Revisa Radmin VPN")))
            except Exception as e:
                self.ui_queue.put(("ping_result", (False, 0, str(e))))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ping_result(self, success, elapsed_ms, detail):
        self.btn_ping_host.configure(text="🔍 Probar Ping", state="normal")
        if success:
            self.lbl_ping_result.configure(
                text=f"🟢 Conexión exitosa al Host (Ping: {elapsed_ms} ms)",
                text_color="#7fcfa6"
            )
        else:
            self.lbl_ping_result.configure(
                text=f"🔴 No se pudo conectar al Host ({detail})",
                text_color="#e0675c"
            )

    def _find_server_exe(self):
        cur_dir = get_base_dir()
        candidates = [
            os.path.join(cur_dir, "server.exe"),
            os.path.join(cur_dir, "launcher", "server.exe"),
            os.path.join(os.path.dirname(cur_dir), "launcher dev", "launcher", "server.exe"),
            os.path.join(os.path.dirname(cur_dir), "launcher dev", "server.exe"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def _host_public_ip(self):
        """IP shown in 'Tu IP para amigos' (Radmin/LAN); '' if only loopback."""
        ip = ""
        try:
            ip = self.opt_local_ips.get().split()[0]
        except Exception:
            pass
        if not ip or ip.startswith("127."):
            ip = self.config.get("online_server", "").strip()
        return "" if ip in ("", "127.0.0.1", "localhost") else ip

    def _kill_stale_servers(self, server_exe):
        """An orphan server.exe (old launcher session) keeps the ports and its old MH3U_ADVERTISE."""
        if sys.platform != "win32":
            return
        try:
            exe = os.path.abspath(server_exe).replace("'", "''")
            ps = (
                "Get-CimInstance Win32_Process -Filter \"Name='server.exe'\" | "
                f"Where-Object {{ $_.ExecutablePath -eq '{exe}' }} | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=15,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            time.sleep(0.5)
        except Exception:
            pass

    def _start_server_process(self, server_exe):
        self._kill_stale_servers(server_exe)
        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            server_dir = os.path.dirname(server_exe)
            server_env = os.environ.copy()
            adv_ip = self._host_public_ip()
            if adv_ip:
                server_env["MH3U_ADVERTISE"] = adv_ip
            relay_mode = str(self.config.get("online_relay", "auto")).lower()
            if relay_mode in ("auto", "force", "off"):
                server_env["MH3U_RELAY"] = relay_mode

            self.server_process = subprocess.Popen(
                [server_exe],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creationflags,
                cwd=server_dir,
                env=server_env,
            )

            def _reader():
                try:
                    for line in iter(self.server_process.stdout.readline, ""):
                        if not line:
                            break
                        clean = line.rstrip()
                        self._queue_server_log(clean)
                        if "STATUS" in clean and "players=" in clean:
                            parts = clean.split("STATUS", 1)[-1].strip()
                            self.ui_queue.put(("server_status", {
                                "text": f"🟢 Servidor ACTIVO | {parts}",
                                "text_color": "#7fcfa6"
                            }))
                except Exception:
                    pass
                finally:
                    if self.server_process:
                        try:
                            self.server_process.stdout.close()
                        except Exception:
                            pass

            t = threading.Thread(target=_reader, daemon=True)
            t.start()

            self.btn_toggle_server.configure(
                text="⏹  Detener Servidor de Sala",
                fg_color="#e0675c",
                hover_color="#a9493f"
            )
            self.lbl_server_status.configure(
                text="🟢 Servidor NEX Activo (UDP 1223/1224)",
                text_color="#7fcfa6"
            )
            self._queue_server_log(f"[Launcher] Servidor Quazal NEX iniciado exitosamente ({server_exe})")
            return True
        except Exception as e:
            self._queue_server_log(f"[Launcher] Error al iniciar server.exe: {e}")
            messagebox.showerror("Error Servidor", f"No se pudo ejecutar server.exe: {e}")
            self.server_process = None
            return False

    def _stop_server_process(self):
        if self.server_process:
            self._queue_server_log("[Launcher] Deteniendo servidor...")
            proc = self.server_process
            self.server_process = None
            try:
                if sys.platform == "win32":
                    # onefile server.exe = bootloader + Python child: terminate() only hits the parent
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        exe = self._find_server_exe()
        if exe:
            self._kill_stale_servers(exe)

    def toggle_host_server(self):
        if self.server_process:
            self._stop_server_process()
            self.btn_toggle_server.configure(
                text="▶  Iniciar Servidor de Sala (Host)",
                fg_color="#2f9488",
                hover_color="#257a70"
            )
            self.lbl_server_status.configure(text="⚪ Servidor Inactivo", text_color="#9db3ba")
            return

        server_exe = self._find_server_exe()
        if server_exe:
            self._start_server_process(server_exe)
            return
        messagebox.showerror("Error Servidor", "No se encontró server.exe junto al launcher.")

    def _queue_server_log(self, text):
        self.ui_queue.put(("server_log", text))

    # ------------------------------------------------------------------
    # Online environment (firewall + relay policy), tied to the master switch
    # ------------------------------------------------------------------
    FW_GROUP = "MH3U Online"

    def _fw_rules_state(self):
        """'missing' | 'enabled' | 'disabled' for the MH3U firewall group (no admin needed)."""
        if sys.platform != "win32":
            return "enabled"
        try:
            out = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={self.FW_GROUP} UDP 1224"],
                capture_output=True, text=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            txt = out.stdout or ""
            if out.returncode != 0 or "1224" not in txt:
                return "missing"
            import re as _re
            m = _re.search(r"(?:enabled|habilitada)\s*:\s*(\S+)", txt, _re.I)
            return "enabled" if m and m.group(1).lower() in ("yes", "sí", "si") else "disabled"
        except Exception:
            return "missing"

    def _run_elevated_batch(self, lines):
        """Run netsh commands in one elevated (UAC) cmd window; returns True when launched."""
        if sys.platform != "win32":
            return False
        try:
            bat = os.path.join(tempfile.gettempdir(), "mh3u_online_fw.bat")
            with open(bat, "w", encoding="utf-8") as f:
                f.write("@echo off" + CRLF + CRLF.join(lines) + CRLF)
            ps = (
                f"Start-Process -FilePath cmd.exe -ArgumentList '/c','\"{bat}\"' "
                "-Verb RunAs -WindowStyle Hidden -Wait"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                timeout=120, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return True
        except Exception as e:
            self._queue_server_log(f"[Launcher] No se pudo elevar permisos para el firewall: {e}")
            return False

    def _tools_exe_path(self):
        res = get_tools_path()
        return res[0] if isinstance(res, tuple) else res

    def _fw_enable_lines(self):
        g = self.FW_GROUP
        lines = [
            f'netsh advfirewall firewall delete rule name=all group="{g}" >nul 2>&1',
        ]
        for label, port in (("1223", "1223"), ("1224", "1224"), ("10025", "10025"), ("33335", "33335"), ("relay", "27100-27387")):
            name = f"{g} UDP {label}" if label != "relay" else f"{g} UDP relay"
            lines.append(
                f'netsh advfirewall firewall add rule name="{name}" group="{g}" dir=in action=allow '
                f'protocol=UDP localport={port} profile=any >nul'
            )
        for exe in (self._tools_exe_path(), self._find_server_exe()):
            if exe and os.path.isfile(exe):
                lines.append(
                    f'netsh advfirewall firewall add rule name="{g} {os.path.basename(exe)}" group="{g}" '
                    f'dir=in action=allow program="{exe}" enable=yes profile=any >nul'
                )
        return lines

    def prepare_online_environment(self):
        """Switch ON: open firewall (UAC once), relay policy; host/client then only wait for the IP."""
        def worker():
            self._queue_server_log("[Launcher] Preparando entorno online (firewall + relé UDP)...")
            state = self._fw_rules_state()
            if state == "enabled":
                self._queue_server_log("[Launcher] Reglas de firewall MH3U ya activas.")
            elif state == "disabled":
                ok = self._run_elevated_batch([f'netsh advfirewall firewall set rule group="{self.FW_GROUP}" new enable=yes >nul'])
                self._queue_server_log("[Launcher] Reglas de firewall reactivadas." if ok else "[Launcher] No se pudo reactivar el firewall.")
            else:
                ok = self._run_elevated_batch(self._fw_enable_lines())
                self._queue_server_log("[Launcher] Reglas de firewall creadas (UDP 1223/1224/10025/33335/27100-27387)." if ok else "[Launcher] No se pudo crear el firewall.")
            mode = self.config.get("online_relay", "auto")
            self._queue_server_log(f"[Launcher] Relé UDP: {mode}. Entorno listo: elige tu rol y la IP.")
        threading.Thread(target=worker, daemon=True).start()

    def teardown_online_environment(self):
        """Switch OFF: stop the server and disable the firewall rules."""
        try:
            self.btn_toggle_server.configure(text="▶  Iniciar Servidor de Sala (Host)", fg_color="#2f9488", hover_color="#257a70")
            self.lbl_server_status.configure(text="⚪ Servidor Inactivo", text_color="#9db3ba")
        except Exception:
            pass
        threading.Thread(target=self._stop_server_process, daemon=True).start()

        def worker():
            if self._fw_rules_state() == "enabled":
                self._run_elevated_batch([f'netsh advfirewall firewall set rule group="{self.FW_GROUP}" new enable=no >nul'])
                self._queue_server_log("[Launcher] Entorno online desactivado (firewall y servidor).")
        threading.Thread(target=worker, daemon=True).start()

    def on_online_switch_toggled(self):
        enabled = bool(self.switch_online.get())
        self.save_online_settings_silent()
        if enabled:
            self.prepare_online_environment()
        else:
            self.teardown_online_environment()

    def save_online_settings_silent(self):
        self.config["online_enabled"] = bool(self.switch_online.get())
        self.save_config()
        self.refresh_status()

    def save_online_settings(self):
        self.config["online_enabled"] = bool(self.switch_online.get())
        mode_val = self.seg_online_mode.get()
        self.config["online_mode"] = "host" if "Host" in mode_val else "client"

        if hasattr(self, "entry_hunter_name"):
            h_name = self.entry_hunter_name.get().strip()
            if h_name:
                self.config["online_hunter_name"] = h_name
                self.config["hunter_name"] = h_name
                if hasattr(self, "entry_hunter_name_cfg"):
                    self.entry_hunter_name_cfg.delete(0, tk.END)
                    self.entry_hunter_name_cfg.insert(0, h_name)

        if hasattr(self, "entry_server_host"):
            self.config["online_server"] = self.entry_server_host.get().strip() or "127.0.0.1"

        room_val = self.entry_host_room.get().strip() if self.config["online_mode"] == "host" else self.entry_room_id.get().strip()
        self.config["online_room_id"] = room_val or "1001"

        self.save_config()
        self.refresh_status()
        messagebox.showinfo("Configuración Online", "Parámetros de red y salas guardados correctamente.")

    def on_app_close(self):
        self._stop_server_process()
        self.destroy()

    def browse_games_folder(self):
        folder = filedialog.askdirectory(title="Selecciona la carpeta que contiene tu copia de Monster Hunter 3 Ultimate")
        if folder:
            has_base, has_update, base_p, upd_p = self.check_dump_status(folder)
            target_dir = folder
            if base_p and upd_p:
                try:
                    target_dir = os.path.commonpath([base_p, upd_p])
                except Exception:
                    target_dir = folder
            elif base_p:
                target_dir = os.path.dirname(base_p)

            self.entry_games_path.delete(0, tk.END)
            self.entry_games_path.insert(0, target_dir)
            self.config["games_dir"] = target_dir
            self.save_config()
            self.refresh_status()

    def check_dump_status(self, games_dir):
        """Verifies if the games folder has base and update dumps (searches up to 3 levels deep)."""
        if not games_dir or not os.path.exists(games_dir):
            return False, False, None, None

        base_path = None
        update_path = None

        try:
            for root, dirs, files in os.walk(games_dir):
                depth = os.path.relpath(root, games_dir).count(os.sep)
                if depth > 3:
                    continue
                if "code" in dirs and "content" in dirs:
                    folder_name = os.path.basename(root).lower()
                    parent_name = os.path.basename(os.path.dirname(root)).lower()
                    meta_xml = os.path.join(root, "meta", "meta.xml")
                    xml_text = ""
                    if os.path.exists(meta_xml):
                        try:
                            with open(meta_xml, "r", encoding="utf-8", errors="ignore") as f:
                                xml_text = f.read().lower()
                        except Exception:
                            pass

                    is_base = (BASE_TITLE_ID in folder_name or BASE_TITLE_ID in parent_name or BASE_TITLE_ID in xml_text)
                    is_update = (UPDATE_TITLE_ID in folder_name or UPDATE_TITLE_ID in parent_name or UPDATE_TITLE_ID in xml_text or "update" in folder_name or "v32" in folder_name)

                    if is_update and not update_path:
                        update_path = root
                    elif is_base and not base_path:
                        base_path = root
                    elif "game" in folder_name and not base_path:
                        base_path = root
        except Exception:
            pass

        return (base_path is not None), (update_path is not None), base_path, update_path

    def refresh_status(self):
        games_dir = self.config.get("games_dir", "")
        out_dir = self.config.get("out_dir", DEFAULT_OUT_DIR)
        game_dll = os.path.join(out_dir, "game.dll")

        has_base, has_update, _, _ = self.check_dump_status(games_dir)
        clang_dir, clang_source = get_clang_info()

        # Update badges
        if has_base:
            self.lbl_badge_base.configure(
                text="🟢 Juego Base USA (0005000010118300): DETECTADO", text_color="#7fcfa6"
            )
        else:
            self.lbl_badge_base.configure(
                text="🔴 Juego Base USA (0005000010118300): NO ENCONTRADO", text_color="#e0675c"
            )

        if has_update:
            self.lbl_badge_update.configure(
                text="🟢 Actualización v32 (0005000e10118300): DETECTADA", text_color="#7fcfa6"
            )
        else:
            self.lbl_badge_update.configure(
                text="🔴 Actualización v32 (0005000e10118300): NO ENCONTRADA", text_color="#e0675c"
            )

        if clang_dir:
            self.lbl_badge_compiler.configure(
                text=f"🟢 Compilador Clang: DETECTADO ({clang_source})", text_color="#7fcfa6"
            )
            self.btn_download_toolchain.configure(state="normal", text="Reinstalar Clang")
        else:
            self.lbl_badge_compiler.configure(
                text="🔴 Compilador Clang: NO DETECTADO (Usa el botón a la derecha para descargarlo)", text_color="#e0675c"
            )
            self.btn_download_toolchain.configure(state="normal", text="⬇️ Descargar Clang Portátil")

        # Game Ready check
        if os.path.exists(game_dll) and not game_dll_is_current(out_dir):
            self.lbl_main_status.configure(
                text="ACTUALIZACIÓN: recompila game.dll (traductor nuevo, requerido para el online)",
                text_color="#eab84c",
            )
        elif os.path.exists(game_dll):
            self.lbl_main_status.configure(
                text="LISTO PARA JUGAR (game.dll compilado)", text_color="#7fcfa6"
            )
            self.btn_play.configure(state="normal", fg_color="#2f9488")
            self.btn_compile_action.configure(
                text="✅ ¡Todo Listo! (Port Compilado - Clic para Recompilar)",
                fg_color="#2f9488",
                hover_color="#257a70",
                text_color="#fff6e0",
            )
        elif has_base and has_update:
            self.lbl_main_status.configure(
                text="DUMPS LISTOS • REQUIERE COMPILAR (Haz clic en 'Traducir y Compilar')",
                text_color="#eab84c",
            )
            self.btn_play.configure(state="disabled", fg_color="#2b4a58")
            self.btn_compile_action.configure(
                text="⚡ Traducir y Compilar Port (Crear game.dll)",
                fg_color="#e08e4a",
                hover_color="#eab84c",
                text_color="#0d1820",
            )
        else:
            self.lbl_main_status.configure(
                text="FALTAN ARCHIVOS DEL DUMP (Configura la carpeta en 'Instalación & Dump')",
                text_color="#e0675c",
            )
            self.btn_play.configure(state="disabled", fg_color="#2b4a58")
            self.btn_compile_action.configure(
                text="⚡ Traducir y Compilar Port (Requiere Dumps)",
                fg_color="#2b4a58",
                hover_color="#2a4b5a",
                text_color="#e3d8bd",
            )

        # Online Status badges
        online_on = self.config.get("online_enabled", False)
        if online_on:
            mode_str = "Host" if self.config.get("online_mode", "client") == "host" else "Cliente"
            srv = self.config.get("online_server", "127.0.0.1")
            if hasattr(self, "lbl_main_online_status"):
                self.lbl_main_online_status.configure(
                    text=f"🟢 ACTIVADO ({mode_str} • {srv})",
                    text_color="#7fcfa6",
                )
            if hasattr(self, "lbl_quick_online"):
                self.lbl_quick_online.configure(
                    text=f"Online: 🟢 Activo ({mode_str} • {srv})",
                    text_color="#7fcfa6",
                )
        else:
            if hasattr(self, "lbl_main_online_status"):
                self.lbl_main_online_status.configure(
                    text="⚪ Desactivado (Juego en Modo Solitario / Offline)",
                    text_color="#e3d8bd",
                )
            if hasattr(self, "lbl_quick_online"):
                self.lbl_quick_online.configure(
                    text="Online: ⚪ Desactivado",
                    text_color="#e3d8bd",
                )

    # =========================================================================
    # TOOLCHAIN AUTO-DOWNLOADER
    # =========================================================================
    def start_download_toolchain(self):
        if self.is_downloading_toolchain or self.is_compiling:
            messagebox.showwarning("En progreso", "Ya hay una descarga o compilación activa.")
            return

        msg = "Se descargará un paquete portátil de LLVM-MinGW Clang (~140MB comprimido) directamente en la carpeta del launcher.\n\nEsto permitirá compilar el port de forma 100% autónoma sin instalar nada en tu sistema.\n\n¿Deseas continuar?"
        if not messagebox.askyesno("Descarga de Compilador Portátil", msg):
            return

        self.is_downloading_toolchain = True
        self.btn_download_toolchain.configure(state="disabled")
        self.progress_bar.set(0.05)
        self._log("Iniciando descarga de compilador portátil LLVM-MinGW...")

        thread = threading.Thread(target=self._run_toolchain_download_worker, daemon=True)
        thread.start()

    def _run_toolchain_download_worker(self):
        base_dir = get_base_dir()
        toolchain_dir = os.path.join(base_dir, "toolchain")

        # Try saving temp zip locally, or fallback to %TEMP% if local directory is write-protected (e.g. MINEDUCYT / Documents)
        temp_candidates = [
            os.path.join(base_dir, "llvm_mingw_temp.zip"),
            os.path.join(tempfile.gettempdir(), "llvm_mingw_temp.zip"),
        ]

        temp_zip = None
        for candidate in temp_candidates:
            try:
                with open(candidate, "wb") as f:
                    pass
                os.remove(candidate)
                temp_zip = candidate
                break
            except Exception:
                continue

        if not temp_zip:
            temp_zip = os.path.join(tempfile.gettempdir(), "llvm_mingw_temp.zip")

        try:
            self._log(f"Descargando desde: {LLVM_MINGW_URL}")
            req = urllib.request.Request(LLVM_MINGW_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response, open(temp_zip, "wb") as out_file:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                block_size = 1024 * 64
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        self.ui_queue.put(("progress", (downloaded / total_size) * 0.7))

            self._log("Descarga completa. Descomprimiendo archivos en toolchain/...")
            self.ui_queue.put(("progress", 0.75))

            # Unpack
            os.makedirs(toolchain_dir, exist_ok=True)
            with zipfile.ZipFile(temp_zip, "r") as zip_ref:
                first_dir = zip_ref.namelist()[0].split("/")[0]
                zip_ref.extractall(base_dir)

            extracted_folder = os.path.join(base_dir, first_dir)
            if os.path.exists(extracted_folder) and extracted_folder != toolchain_dir:
                if os.path.exists(toolchain_dir):
                    shutil.rmtree(toolchain_dir, ignore_errors=True)
                os.rename(extracted_folder, toolchain_dir)

            if os.path.exists(temp_zip):
                try:
                    os.remove(temp_zip)
                except Exception:
                    pass

            self.ui_queue.put(("progress", 1.0))
            self._log("¡Compilador portátil instalado correctamente en la carpeta toolchain/!")
            self.ui_queue.put(("info", ("Compilador Listo", "LLVM-MinGW se configuró correctamente en la carpeta del launcher.")))
        except Exception as e:
            self._log(f"Error descargando compilador: {e}")
            self.ui_queue.put(("error", ("Error de descarga", f"No se pudo descargar o extraer el compilador: {e}")))
            self.ui_queue.put(("progress", 0))
        finally:
            self.is_downloading_toolchain = False
            self.ui_queue.put(("btn_download", {"state": "normal"}))
            self.ui_queue.put(("refresh", None))

    # =========================================================================
    # COMPILATION WORKER
    # =========================================================================
    def start_build_process(self):
        if self.is_compiling:
            messagebox.showwarning("Proceso en curso", "Ya hay una compilación en ejecución.")
            return

        games_dir = self.config.get("games_dir", "")
        if not games_dir or not os.path.exists(games_dir):
            messagebox.showerror(
                "Carpeta requerida",
                "Por favor selecciona primero la carpeta donde tienes los dumps del juego.",
            )
            self.tabview.set("  ⚙️ Instalación & Dump  ")
            return

        out_dir = self.config.get("out_dir", DEFAULT_OUT_DIR)
        game_dll = os.path.join(out_dir, "game.dll")
        if os.path.exists(game_dll) and game_dll_is_current(out_dir):
            if not messagebox.askyesno(
                "Port ya compilado",
                "El port nativo ya se encuentra traducido y compilado correctamente, ¡todo está listo para jugar!\n\n¿Deseas volver a compilar game.dll de todos modos?",
            ):
                return

        has_base, has_update, _, _ = self.check_dump_status(games_dir)
        if not has_base or not has_update:
            msg = "Atención: No se detectó el juego base o la actualización v32 en la carpeta seleccionada.\n\n¿Deseas intentar compilar de todos modos?"
            if not messagebox.askyesno("Verificación de Dumps", msg):
                return

        clang_dir, _ = get_clang_info()
        if not clang_dir:
            msg = "No se detectó el compilador Clang en tu sistema ni en la carpeta del launcher.\n\n¿Deseas descargarlo automáticamente ahora?"
            if messagebox.askyesno("Compilador Requerido", msg):
                self.start_download_toolchain()
            return

        self.is_compiling = True
        self.btn_compile_action.configure(state="disabled")
        self.progress_bar.set(0.1)
        self.txt_log.delete("1.0", tk.END)
        self.tabview.set("  ⚙️ Instalación & Dump  ")

        thread = threading.Thread(target=self._run_build_worker, daemon=True)
        thread.start()

    def _log(self, text):
        self.ui_queue.put(("log", text))

    def _run_build_worker(self):
        try:
            tools = get_tools_path()
            games_dir = self.config.get("games_dir", "")
            out_dir = self.config.get("out_dir", DEFAULT_OUT_DIR)
            os.makedirs(out_dir, exist_ok=True)

            self._log("=== INICIANDO COMPILACIÓN NATIVA DE MONSTER HUNTER 3 ULTIMATE ===")
            self._log(f"• Motor del port: {tools}")
            self._log(f"• Carpeta de dumps: {games_dir}")
            self._log(f"• Carpeta de destino C: {out_dir}")
            self._log("-" * 65)

            if not os.path.exists(tools):
                self._log(f"ERROR: No se encontró 'mh3u-tools.exe' en la ruta:\n{tools}")
                self.ui_queue.put(("error", ("Motor no encontrado", f"No se encontró 'mh3u-tools.exe' en la carpeta del launcher:\n{tools}\n\nAsegúrate de haber extraído todos los archivos del launcher.")))
                self.ui_queue.put(("progress", 0))
                return

            # 1. Translate step if needed
            game_h = os.path.join(out_dir, "game.h")
            if not os.path.exists(game_h):
                self._log("> PASO 1/2: Traduciendo ejecutable PowerPC (Wii U) a código C...")
                self.ui_queue.put(("progress", 0.15))
                cmd = [tools, "translate", games_dir, out_dir]
                success = self._run_subprocess(cmd)
                if not success:
                    self._log("ERROR: La traducción del juego falló. Revisa que el dump sea USA v32.")
                    self.ui_queue.put(("error", ("Error de Traducción", "La traducción falló. Verifica que tu dump contenga el juego base y la actualización v32.")))
                    self.ui_queue.put(("progress", 0))
                    return
            else:
                self._log("> PASO 1/2: El código C ya fue traducido previamente. Continuando...")

            # 2. Build-game step with clang
            self._log("-" * 65)
            self._log("> PASO 2/2: Compilando 387 archivos C a 'game.dll' con Clang...")
            self._log("⏳ Compilando con múltiples núcleos de CPU en paralelo.")
            self._log("ℹ️ Este paso toma aprox. 1 a 2 minutos la primera vez. La barra avanzará en tiempo real.")
            self.ui_queue.put(("progress", 0.25))
            cmd = [tools, "build-game", out_dir, "--native"]
            if self.config.get("build_lto", False):
                cmd.extend(["--lto", "--opt", "3"])
                self._log("🚀 LTO activado: Compilando con optimización global -flto=thin y nivel -O3...")
            success = self._run_subprocess(cmd, monitor_dir=out_dir, total_expected=387)

            if success:
                try:
                    with open(dll_rev_path(out_dir), "w", encoding="utf-8") as f:
                        f.write(TRANSLATOR_REV)
                except OSError:
                    pass
                self.ui_queue.put(("progress", 1.0))
                self._log("-" * 65)
                self._log("🎉 ¡COMPILACIÓN EXITOSA! 'game.dll' ha sido generado correctamente.")
                self.ui_queue.put(("info", (
                    "¡Listo para cazar!",
                    "La compilación nativa de Monster Hunter 3 Ultimate finalizó con éxito.\nYa puedes hacer clic en JUGAR.",
                )))
                self.ui_queue.put(("tab", "  🎮 Principal  "))
            else:
                self.ui_queue.put(("progress", 0))
                self._log("ERROR: La compilación con Clang falló. Revisa el registro anterior.")
                self.ui_queue.put(("error", (
                    "Error en compilación",
                    "Hubo un error al compilar game.dll con Clang. Revisa los registros.",
                )))
        except Exception as e:
            self._log(f"EXCEPCIÓN EN HILO DE COMPILACIÓN: {e}")
            self.ui_queue.put(("error", ("Error Inesperado", f"Ocurrió un error inesperado al compilar:\n{e}")))
            self.ui_queue.put(("progress", 0))
        finally:
            self.is_compiling = False
            self.ui_queue.put(("btn_compile", {"state": "normal"}))
            self.ui_queue.put(("refresh", None))

    def _run_subprocess(self, cmd, monitor_dir=None, total_expected=387):
        try:
            env = os.environ.copy()
            base_dir = get_base_dir()

            # Set hooks path if available
            hooks_candidates = [
                os.path.join(base_dir, "mods", "hooks.txt"),
                os.path.join(base_dir, "..", "mh3u-port", "mods", "hooks.txt"),
            ]
            for h in hooks_candidates:
                if os.path.exists(h):
                    env["MH3U_HOOKS"] = os.path.abspath(h)
                    break

            # Set Clang path
            clang_bin, _ = get_clang_info()
            if clang_bin:
                env["PATH"] = f"{clang_bin};{env.get('PATH', '')}"
                env["MH3U_CC"] = os.path.join(clang_bin, "clang.exe")

            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )

            # Background thread to monitor progress of .o file generation
            stop_monitor = threading.Event()
            def monitor_worker():
                last_reported = -1
                while not stop_monitor.is_set():
                    if monitor_dir and os.path.exists(monitor_dir):
                        try:
                            o_files = [f for f in os.listdir(monitor_dir) if f.endswith(".o")]
                            count = len(o_files)
                            pct = min(0.95, 0.25 + (count / float(total_expected)) * 0.70)
                            self.ui_queue.put(("progress", pct))
                            if count != last_reported and (count % 35 == 0 or count == total_expected or count == 1):
                                last_reported = count
                                self._log(f"⚡ [Compilador Clang] {count} / {total_expected} archivos procesados ({int(count * 100 / total_expected)}%)...")
                        except Exception:
                            pass
                    stop_monitor.wait(0.6)

            monitor_thread = None
            if monitor_dir:
                monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
                monitor_thread.start()

            # Unbuffered line-by-line reading
            while True:
                line = p.stdout.readline()
                if not line:
                    break
                line_str = line.strip()
                if line_str:
                    self._log(line_str)

            p.wait()
            stop_monitor.set()
            if monitor_thread:
                monitor_thread.join(timeout=1.0)

            return p.returncode == 0
        except Exception as e:
            self._log(f"Excepción en subproceso: {e}")
            return False

    # =========================================================================
    # GAME RUNNER
    # =========================================================================
    def launch_game(self):
        if self.is_running:
            messagebox.showinfo("Juego en ejecución", "El juego ya se está ejecutando.")
            return

        tools = get_tools_path()
        games_dir = self.config.get("games_dir", "")
        out_dir = self.config.get("out_dir", DEFAULT_OUT_DIR)
        game_dll = os.path.join(out_dir, "game.dll")

        if not os.path.exists(game_dll):
            messagebox.showerror(
                "No compilado",
                "El juego no ha sido compilado todavía. Haz clic en 'Traducir y Compilar Port' primero.",
            )
            return

        if not game_dll_is_current(out_dir):
            if messagebox.askyesno(
                "Recompilación necesaria",
                "Tu game.dll fue creado con una versión anterior del traductor y le faltan funciones "
                "(el modo en red cierra el juego).\n\n¿Recompilar ahora? (tarda unos minutos)",
            ):
                self.start_build_process()
            return

        # Prepare arguments
        run_args = [tools, "run", games_dir, out_dir, "--window", "--max-imports", "1000000000000"]
        if self.config.get("fullscreen", True):
            run_args.append("--fullscreen")

        # Prepare environment variables
        env = os.environ.copy()
        base_dir = get_base_dir()

        # Set hooks
        hooks_candidates = [
            os.path.join(base_dir, "mods", "hooks.txt"),
            os.path.join(base_dir, "..", "mh3u-port", "mods", "hooks.txt"),
        ]
        for h in hooks_candidates:
            if os.path.exists(h):
                env["MH3U_HOOKS"] = os.path.abspath(h)
                break

        # Set Clang / toolchain bin on PATH for runtime DLLs
        clang_bin, _ = get_clang_info()
        if clang_bin:
            env["PATH"] = f"{clang_bin};{env.get('PATH', '')}"

        if self.config.get("pad_layout"):
            env["MH3U_PAD_LAYOUT"] = self.config["pad_layout"]
        if self.config.get("scale"):
            env["MH3U_GFX_RESOLUTION_SCALE"] = str(self.config["scale"])
        if self.config.get("native_menu"):
            env["MH3U_NATIVE_MENU"] = "1"
        if self.config.get("native_text"):
            env["MH3U_NATIVE_TEXT"] = "1"
        if self.config.get("fps"):
            env["MH3U_FPS"] = "1"
        # Only turn off overlay if BOTH overlay and fps are false, as FPS counter is drawn in overlay
        if not self.config.get("overlay", True) and not self.config.get("fps", False):
            env["MH3U_OVERLAY"] = "off"
        if not self.config.get("audio", True):
            env["MH3U_AUDIO"] = "off"
        if not self.config.get("audio_fx", True):
            env["MH3U_AUDIO_FX"] = "off"

        # Graphics Backend (Vulkan vs DirectX 12)
        backend = self.config.get("gfx_backend", "vulkan")
        if backend == "dx12":
            env["WGPU_BACKEND"] = "dx12"
        else:
            env["WGPU_BACKEND"] = "vulkan"

        # Present Mode (VSync / Mailbox)
        env["MH3U_PRESENT_MODE"] = self.config.get("present_mode", "mailbox")

        # Upscaler & Sharpness (AMD FidelityFX FSR 1.0 / CAS)
        env["MH3U_UPSCALER"] = self.config.get("upscaler", "fsr")
        sharpness_pct = self.config.get("fsr_sharpness", 75)
        env["MH3U_FSR_SHARPNESS"] = str(round(float(sharpness_pct) / 100.0, 2))

        # Hunter Name and Software Keyboard for character creation
        detected_hunter = get_hunter_name_from_save(self.config.get("out_dir", DEFAULT_OUT_DIR))
        hunter_name = detected_hunter or self.config.get("hunter_name") or self.config.get("online_hunter_name", "Hunter")
        if hunter_name:
            env["MH3U_SWKBD_TEXT"] = hunter_name
            env["MH3U_HUNTER_NAME"] = hunter_name

        # Online hooks environment preparation
        if self.config.get("online_enabled", False):
            env["MH3U_ONLINE_ENABLED"] = "1"
            is_host = self.config.get("online_mode", "client") == "host"

            if is_host:
                if not self.server_process:
                    server_exe = self._find_server_exe()
                    if server_exe:
                        self._start_server_process(server_exe)
                env["MH3U_ONLINE_MODE"] = "host"
                env["MH3U_ONLINE_SERVER"] = "127.0.0.1"
                pub_ip = self._host_public_ip()
                if pub_ip:
                    env["MH3U_LOCAL_IP"] = pub_ip
            else:
                target_server = self.config.get("online_server", "127.0.0.1").strip()
                is_local = target_server in ["127.0.0.1", "localhost"]
                if not is_local:
                    try:
                        detected = [x.split()[0] for x in get_local_ip_addresses()]
                        if target_server in detected:
                            is_local = True
                    except Exception:
                        pass
                if is_local:
                    if not self.server_process:
                        server_exe = self._find_server_exe()
                        if server_exe:
                            self._start_server_process(server_exe)
                    env["MH3U_ONLINE_MODE"] = "host"
                    env["MH3U_ONLINE_SERVER"] = "127.0.0.1"
                    own_ip = target_server if target_server not in ("127.0.0.1", "localhost") else self._host_public_ip()
                    if own_ip:
                        env["MH3U_LOCAL_IP"] = own_ip
                else:
                    env["MH3U_ONLINE_MODE"] = "client"
                    env["MH3U_ONLINE_SERVER"] = target_server
                    my_ip = detect_route_ip(target_server)
                    if my_ip:
                        env["MH3U_LOCAL_IP"] = my_ip

            env["MH3U_ONLINE_ROOM"] = str(self.config.get("online_room_id", "1001"))
            if os.environ.get("MH3U_DEBUG_DUMP") == "1":
                env["MH3U_DUMP_AFTER"] = "10"

        # Sync mouse sensitivity before launch
        sens_float = self.config.get("mouse_sensitivity", 0.0008)
        self._sync_bindings_mouse_sensitivity(sens_float)

        self.is_running = True
        self.btn_play.configure(
            text="🛑  DETENER JUEGO",
            fg_color="#e0675c",
            hover_color="#a9493f",
            command=self.stop_game,
            state="normal",
        )

        thread = threading.Thread(target=self._run_game_worker, args=(run_args, env), daemon=True)
        thread.start()

    def stop_game(self):
        if not self.is_running or not self.game_process:
            return
        if messagebox.askyesno("Detener Juego", "¿Deseas cerrar Monster Hunter 3 Ultimate de forma segura?"):
            self._log("Deteniendo el juego de forma segura...")
            try:
                self.game_process.terminate()
            except Exception as e:
                self._log(f"Error al terminar proceso: {e}")
                try:
                    self.game_process.kill()
                except Exception:
                    pass

    def _run_game_worker(self, run_args, env):
        log_file_path = os.path.join(get_base_dir(), "mh3u_latest.log")
        discord_rpc = None
        out_dir = self.config.get("out_dir", DEFAULT_OUT_DIR)

        # Detect real hunter name from save file, or fallback to config
        saved_hunter = get_hunter_name_from_save(out_dir)
        hunter_name = saved_hunter or self.config.get("hunter_name", "Hunter")

        if self.config.get("discord_rpc", True):
            try:
                client_id = self.config.get("discord_client_id", DEFAULT_DISCORD_CLIENT_ID)
                discord_rpc = DiscordRPCManager(client_id)
                if discord_rpc.connect():
                    discord_rpc.update_presence(
                        details="Iniciando el juego...",
                        state=f"Cazador: {hunter_name}",
                        large_text="Monster Hunter 3 Ultimate (PC Native Port)",
                    )
            except Exception as e:
                print(f"Discord RPC init error: {e}")

        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

            with open(log_file_path, "w", encoding="utf-8", errors="replace") as log_f:
                p = subprocess.Popen(
                    run_args,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    creationflags=creationflags,
                )
                self.game_process = p

                # Monitor loop for scene changes & Discord RPC updates while game is running
                last_area = None
                last_hunter = hunter_name
                while p.poll() is None:
                    if discord_rpc and discord_rpc.connected:
                        try:
                            current_area = "Cazando en el Mundo"
                            if os.path.exists(log_file_path):
                                with open(log_file_path, "r", encoding="utf-8", errors="ignore") as lf:
                                    lines = lf.readlines()[-40:]
                                    for line in reversed(lines):
                                        # Detect live hunter name from overlay log if available
                                        m_name = re.search(r"\[overlay\] the live save is at [^:]+:\s*([^\r\n]+)", line)
                                        if m_name:
                                            live_name = m_name.group(1).strip()
                                            if live_name:
                                                hunter_name = live_name

                                        # Detect scene
                                        if "aVillageSquare" in line:
                                            current_area = "Aldea de Moga (Plaza)"
                                            break
                                        elif "aVillageHouse" in line:
                                            current_area = "Casa del Cazador (Moga)"
                                            break
                                        elif "aVillageFarm" in line:
                                            current_area = "Granja de Moga"
                                            break
                                        elif "aVillage" in line:
                                            current_area = "Aldea de Moga"
                                            break
                                        elif "aHarborSquare" in line or "aHarbor" in line or "aMarina" in line:
                                            current_area = "Puerto Tanzia (Marina)"
                                            break
                                        elif "aHarborGuild" in line or "aHarborRoomGuild" in line or "aTavern" in line:
                                            current_area = "Gremio / Taberna de Tanzia"
                                            break
                                        elif "aHarborRoomSquare" in line:
                                            current_area = "Casa de Huéspedes (Tanzia)"
                                            break
                                        elif "aQuest" in line or "aQuestArea" in line:
                                            current_area = "En Misión de Caza"
                                            break
                                        elif "aFreeQuest" in line or "aFreeQuestArea" in line:
                                            current_area = "Bosque Moga (Caza Libre)"
                                            break
                                        elif "aArenaMenu" in line:
                                            current_area = "Arena de Combate"
                                            break
                                        elif "aResult" in line:
                                            current_area = "Recompensas de Misión"
                                            break
                                        elif "Title" in line or "aStartMenu" in line or "aBoot" in line:
                                            current_area = "Menú Principal"
                                            break

                            # In case save was saved during play, re-check save files if name is still default
                            if not hunter_name or hunter_name == "Hunter":
                                fresh_save_name = get_hunter_name_from_save(out_dir)
                                if fresh_save_name:
                                    hunter_name = fresh_save_name

                            if current_area != last_area or hunter_name != last_hunter:
                                last_area = current_area
                                last_hunter = hunter_name
                                discord_rpc.update_presence(
                                    details=current_area,
                                    state=f"Cazador: {hunter_name}",
                                    large_text="Monster Hunter 3 Ultimate (PC Native Port)",
                                )
                        except Exception:
                            pass
                    time.sleep(3.0)

                p.wait()
        except Exception as e:
            print(f"Error launching game: {e}")
        finally:
            if discord_rpc:
                discord_rpc.close()
            self.game_process = None
            self.is_running = False
            self.after(200, lambda: self.btn_play.configure(
                text="⚔️  JUGAR MONSTER HUNTER 3 ULTIMATE",
                fg_color="#2f9488",
                hover_color="#257a70",
                command=self.launch_game,
                state="normal",
            ))

    # =========================================================================
    # TOOLS ACTIONS
    # =========================================================================
    def open_save_folder(self):
        out_dir = self.config.get("out_dir", DEFAULT_OUT_DIR)
        save_dir = os.path.join(out_dir, "save")
        os.makedirs(save_dir, exist_ok=True)
        try:
            os.startfile(save_dir)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta: {e}")

    def backup_save_folder(self):
        out_dir = self.config.get("out_dir", DEFAULT_OUT_DIR)
        save_dir = os.path.join(out_dir, "save")
        if not os.path.exists(save_dir) or not os.listdir(save_dir):
            messagebox.showwarning("Sin partidas", "Aún no hay archivos de guardado en la carpeta.")
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_name = f"mh3u_save_backup_{timestamp}"
        dest_zip = os.path.join(get_base_dir(), backup_name)
        try:
            shutil.make_archive(dest_zip, "zip", save_dir)
            messagebox.showinfo("Respaldo Creado", f"Copia de seguridad guardada como:\n{dest_zip}.zip")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear el respaldo: {e}")

    def open_latest_log(self):
        log_file_path = os.path.join(get_base_dir(), "mh3u_latest.log")
        if os.path.exists(log_file_path):
            try:
                os.startfile(log_file_path)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el log: {e}")
        else:
            messagebox.showinfo("Log no encontrado", "Aún no se ha generado 'mh3u_latest.log'. Inicia el juego primero.")

    def clean_cache(self):
        out_dir = self.config.get("out_dir", DEFAULT_OUT_DIR)
        cache_dir = os.path.join(out_dir, "cache")
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                messagebox.showinfo("Caché Limpia", "Se ha eliminado la caché de pipelines y shaders correctamente.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo limpiar la caché: {e}")
        else:
            messagebox.showinfo("Caché limpia", "No se encontró carpeta de caché que eliminar.")


if __name__ == "__main__":
    app = MH3ULauncherApp()
    app.mainloop()
