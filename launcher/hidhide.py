# SPDX-License-Identifier: AGPL-3.0-only
"""Detect when HidHide hides the user's gamepad from MH3U, and let the launcher allow it.

HidHide (installed by DSX / DS4Windows / ViGEm setups) hides physical controllers from every program
that is not on its application list, so Windows answers "access denied" to `mh3u-tools.exe` and the
game never sees the pad. DSX/DS4Windows themselves are on the list and offer the game a virtual Xbox
pad instead; when that virtual pad exists nothing is needed. When it does not (DSX closed), the fix is
to add `mh3u-tools.exe` to HidHide's list (needs administrator; undo with `--app-unreg`).
"""

import ctypes
import os
import subprocess
import sys

# USB vendor ids of controllers whose hiding matters here: Sony and Nintendo
GAMEPAD_VENDORS = ("vid_054c", "vid&0002054c", "vid_057e", "vid&0002057e")


def find_cli():
    roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), r"C:\Program Files"]
    for root in filter(None, roots):
        cli = os.path.join(root, "Nefarius Software Solutions", "HidHide", "x64", "HidHideCLI.exe")
        if os.path.isfile(cli):
            return cli
    return None


def _norm(path):
    return os.path.normcase(os.path.abspath(path.strip().strip('"')))


def pad_is_hidden(cloak_out, inverse_out, hidden_out, app_out, tools_path):
    """True when HidHide's cloak hides a gamepad and `tools_path` is not on its application list."""
    if "--cloak-on" not in cloak_out or "--inv-on" in inverse_out:
        return False
    hidden = [line.lower() for line in hidden_out.splitlines() if "--dev-hide" in line]
    if not any(v in line for line in hidden for v in GAMEPAD_VENDORS):
        return False
    apps = []
    for line in app_out.splitlines():
        if "--app-reg" in line and '"' in line:
            apps.append(_norm(line.split('"')[1]))
    return _norm(tools_path) not in apps


def _run(cli, arg):
    r = subprocess.run(
        [cli, arg], capture_output=True, text=True, timeout=8,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return r.stdout or ""


def xinput_pad_connected():
    """True when an XInput pad (real, or the virtual one DSX / DS4Windows / Steam make) is connected."""
    if sys.platform != "win32":
        return False
    try:
        dll = ctypes.WinDLL("xinput1_4")
        state = ctypes.create_string_buffer(16)
        return any(dll.XInputGetState(i, state) == 0 for i in range(4))
    except Exception:
        return False


def hidden_pad_cli(tools_path):
    """The HidHideCLI path when it hides a gamepad from `tools_path` and no XInput pad stands in; else None."""
    if sys.platform != "win32":
        return None
    cli = find_cli()
    if not cli or xinput_pad_connected():
        return None
    try:
        hidden = pad_is_hidden(
            _run(cli, "--cloak-state"), _run(cli, "--inv-state"), _run(cli, "--dev-list"), _run(cli, "--app-list"), tools_path,
        )
    except Exception:
        return None
    return cli if hidden else None


def allow_command(cli, tools_path):
    return f'"{cli}" --app-reg "{os.path.abspath(tools_path)}"'


def is_allowed(cli, tools_path):
    try:
        return not pad_is_hidden("--cloak-on", "", "--dev-hide 054c vid_054c", _run(cli, "--app-list"), tools_path)
    except Exception:
        return False
