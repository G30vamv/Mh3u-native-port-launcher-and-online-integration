"""Remote update support for the MH3U launcher.

Flow: fetch `manifest.json` from the latest GitHub Release -> compare versions -> download only
the files whose sha256 differs into `_update/` -> verify -> write `apply_update.bat`, which waits
for the launcher to exit, backs up the old files to `_update_backup/`, moves the new ones in,
rolls back on any failure and relaunches. Nothing outside PROTECTED is ever touched.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

UPDATE_REPO = "G30vamv/Mh3u-native-port-launcher-and-online-integration"
MANIFEST_URL = f"https://github.com/{UPDATE_REPO}/releases/latest/download/manifest.json"
MANIFEST_ENV = "MH3U_UPDATE_MANIFEST"  # override (tests): http(s):// or file:/// URL
UPDATE_DIR = "_update"
BACKUP_DIR = "_update_backup"
USER_AGENT = "MH3U-Launcher-Updater"

# Never replaced or deleted by an update (user data, per-machine builds, logs).
PROTECTED = {
    "launcher_config.json",
    "game.dll",
    "game.dll.rev",
    "server.log",
    "mh3u_latest.log",
}
PROTECTED_DIRS = {"toolchain", UPDATE_DIR, BACKUP_DIR, "mh3u_dump"}
ALLOWED_EXT = {".exe", ".dll", ".py", ".bat", ".txt", ".png", ".ico", ".json", ".md"}


# cmd.exe system tools by full path (a user PATH may shadow find/timeout with other tools).
S32 = "%SystemRoot%" + chr(92) + "System32" + chr(92)


class UpdateError(Exception):
    pass


def parse_version(text):
    """'v0.7.7' -> (0, 7, 7); non-numeric parts are ignored."""
    nums = re.findall(r"\d+", str(text))
    return tuple(int(n) for n in nums) if nums else (0,)


def _open(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_manifest():
    url = os.environ.get(MANIFEST_ENV) or MANIFEST_URL
    try:
        with _open(url) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise UpdateError(f"No se pudo leer el manifiesto de actualización: {e}")
    if not isinstance(data, dict) or "version" not in data or not isinstance(data.get("files"), list):
        raise UpdateError("Manifiesto de actualización inválido.")
    return data


def is_newer(manifest, current_version):
    return parse_version(manifest["version"]) > parse_version(current_version)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_rel(path):
    """Validate a manifest path: relative, no traversal, not protected, known extension."""
    norm = os.path.normpath(path.replace("/", os.sep))
    if os.path.isabs(norm) or norm.startswith("..") or os.sep + ".." + os.sep in os.sep + norm + os.sep:
        raise UpdateError(f"Ruta no permitida en el manifiesto: {path}")
    parts = norm.split(os.sep)
    if norm.lower() in PROTECTED or parts[0].lower() in PROTECTED_DIRS:
        raise UpdateError(f"El manifiesto intenta tocar un archivo protegido: {path}")
    if os.path.splitext(norm)[1].lower() not in ALLOWED_EXT:
        raise UpdateError(f"Tipo de archivo no permitido en el manifiesto: {path}")
    return norm


def files_to_update(manifest, base_dir):
    """Entries whose local sha256 differs (or that are missing)."""
    todo = []
    for entry in manifest["files"]:
        rel = _safe_rel(entry["path"])
        if not entry.get("sha256") or not entry.get("url"):
            raise UpdateError(f"Entrada incompleta en el manifiesto: {entry.get('path')}")
        local = os.path.join(base_dir, rel)
        if os.path.isfile(local) and sha256_file(local) == entry["sha256"].lower():
            continue
        todo.append({**entry, "rel": rel})
    return todo


def download_files(todo, base_dir, progress=None):
    """Download + verify into _update/. Returns the staging dir. Cleans up on failure."""
    stage = os.path.join(base_dir, UPDATE_DIR)
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    total = sum(int(e.get("size") or 0) for e in todo) or 1
    done = 0
    try:
        for e in todo:
            dest = os.path.join(stage, e["rel"])
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            h = hashlib.sha256()
            with _open(e["url"], timeout=60) as r, open(dest, "wb") as out:
                while True:
                    chunk = r.read(1 << 18)
                    if not chunk:
                        break
                    out.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(min(done / total, 1.0), e["rel"])
            if h.hexdigest() != e["sha256"].lower():
                raise UpdateError(f"Verificación sha256 fallida: {e['rel']}")
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return stage


def _relaunch_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'


def write_apply_script(todo, base_dir, version):
    """Create apply_update.bat (CRLF). It waits for this process, swaps files, rolls back on failure."""
    stage = os.path.join(base_dir, UPDATE_DIR)
    backup = os.path.join(base_dir, BACKUP_DIR, str(version))
    lines = [
        "@echo off",
        "setlocal",
        f'cd /d "{base_dir}"',
        f"set PID={os.getpid()}",
        ":wait",
        '"{S32}tasklist.exe" /FI "PID eq %PID%" 2>nul | "{S32}find.exe" "%PID%" >nul'.replace('{S32}', S32),
        'if not errorlevel 1 ("{S32}ping.exe" -n 2 127.0.0.1 >nul & goto wait)'.replace('{S32}', S32),
        '"{S32}taskkill.exe" /F /IM mh3u-tools.exe >nul 2>&1'.replace('{S32}', S32),
        '"{S32}taskkill.exe" /F /IM server.exe >nul 2>&1'.replace('{S32}', S32),
        '"{S32}ping.exe" -n 2 127.0.0.1 >nul'.replace('{S32}', S32),
        f'if exist "{backup}" rmdir /S /Q "{backup}"',
        f'mkdir "{backup}"',
        "set FAIL=0",
    ]
    for e in todo:
        rel = e["rel"]
        dst = os.path.join(base_dir, rel)
        src = os.path.join(stage, rel)
        bak = os.path.join(backup, rel)
        lines += [
            f'if exist "{dst}" (',
            f'  if not exist "{os.path.dirname(bak)}" mkdir "{os.path.dirname(bak)}"',
            f'  copy /Y "{dst}" "{bak}" >nul || set FAIL=1',
            ")",
            f'if not exist "{os.path.dirname(dst)}" mkdir "{os.path.dirname(dst)}"',
            f'move /Y "{src}" "{dst}" >nul || set FAIL=1',
        ]
    lines += ["if %FAIL%==1 goto rollback", "goto done", ":rollback"]
    for e in todo:
        rel = e["rel"]
        lines.append(f'if exist "{os.path.join(backup, rel)}" copy /Y "{os.path.join(backup, rel)}" "{os.path.join(base_dir, rel)}" >nul')
    lines += [
        ":done",
        f'rmdir /S /Q "{stage}" >nul 2>&1',
        f"start \"\" {_relaunch_command()}",
        '(goto) 2>nul & del "%~f0"',
    ]
    script = os.path.join(base_dir, "apply_update.bat")
    with open(script, "w", encoding="ascii", errors="replace", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return script


def launch_apply_script(script):
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(["cmd.exe", "/c", script], creationflags=flags, close_fds=True)
