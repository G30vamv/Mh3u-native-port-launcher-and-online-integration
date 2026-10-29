# SPDX-License-Identifier: AGPL-3.0-only
"""Portable LLVM-MinGW installer that fetches only what translating/compiling needs.

The release zip is ~190 MB / 9000 files; the port needs ~5500 of them (~90 MB compressed). The
list lives in assets/toolchain_files.txt (regenerate with tools/make_toolchain_list.py when
LLVM_MINGW_URL changes). The zip is read with HTTP Range requests so unneeded members are never
downloaded; if Range is unavailable the whole zip is downloaded and extracted with the same filter.
"""

import io
import os
import shutil
import tempfile
import urllib.request
import zipfile

USER_AGENT = {"User-Agent": "Mozilla/5.0"}
BLOCK_MIN = 1 << 20  # smallest on-demand fetch (central directory etc.)
RUN_GAP = 512 * 1024  # merge needed members closer than this into one request
RUN_MAX = 24 * 1024 * 1024  # largest single ranged request kept in memory
REQUIRED = ("bin/clang.exe",)


def load_allowlist(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            names = {line.strip() for line in f if line.strip()}
        return names or None
    except OSError:
        return None


class RangeFile(io.RawIOBase):
    """Read-only seekable view of a remote file, backed by HTTP Range requests."""

    def __init__(self, url):
        self.url = url
        self.pos = 0
        self.fetched = 0  # bytes actually downloaded
        self.seg_start = 0
        self.seg = b""
        req = urllib.request.Request(url, headers={**USER_AGENT, "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 206:
                raise OSError("el servidor no admite descargas parciales (Range)")
            self.size = int(r.headers["Content-Range"].rsplit("/", 1)[1])

    def _fetch(self, start, end):
        end = min(end, self.size)
        for attempt in range(3):
            try:
                req = urllib.request.Request(self.url, headers={**USER_AGENT, "Range": f"bytes={start}-{end - 1}"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    if r.status != 206:
                        raise OSError("respuesta sin Range")
                    data = r.read()
                if len(data) != end - start:
                    raise OSError("descarga parcial incompleta")
                self.fetched += len(data)
                self.seg_start, self.seg = start, data
                return
            except OSError:
                if attempt == 2:
                    raise

    def prefetch(self, start, end):
        if not (self.seg_start <= start and end <= self.seg_start + len(self.seg)):
            self._fetch(start, end)

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        if n == 0:
            return b""
        if not (self.seg_start <= self.pos and self.pos + n <= self.seg_start + len(self.seg)):
            self._fetch(self.pos, self.pos + max(n, BLOCK_MIN))
        off = self.pos - self.seg_start
        data = self.seg[off:off + n]
        self.pos += n
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def _select(infos, allow):
    """(member, relative path) pairs to install, in archive order."""
    out = []
    for i in infos:
        if i.filename.endswith("/") or "/" not in i.filename:
            continue
        rel = i.filename.split("/", 1)[1]
        if allow is None or rel in allow:
            out.append((i, rel))
    out.sort(key=lambda t: t[0].header_offset)
    return out


def _write_member(zf, info, rel, dest):
    target = os.path.normpath(os.path.join(dest, *rel.split("/")))
    if not target.startswith(os.path.normpath(dest) + os.sep):
        raise OSError(f"ruta no permitida en el zip: {rel}")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with zf.open(info) as src, open(target, "wb") as out:
        shutil.copyfileobj(src, out, 1 << 20)


def _finish(stage, final):
    if not os.path.isfile(os.path.join(stage, *REQUIRED[0].split("/"))):
        raise OSError("faltan archivos esenciales del compilador")
    if os.path.exists(final):
        shutil.rmtree(final, ignore_errors=True)
    os.rename(stage, final)


def _extract_ranged(url, base_dir, allow, progress, log):
    rf = RangeFile(url)
    zf = zipfile.ZipFile(rf)
    infos = zf.infolist()
    picked = _select(infos, allow)
    if allow is not None:
        have = {rel for _, rel in picked}
        if len(have) < 0.9 * len(allow):
            log("La lista de archivos no coincide con esta versión de LLVM-MinGW; se instalará completa.")
            picked = _select(infos, None)
    total = sum(i.compress_size for i, _ in picked) or 1
    log(f"Descargando solo lo necesario: {len(picked)} archivos (~{total / 1048576:.0f} MB de {rf.size / 1048576:.0f} MB).")
    stage = os.path.join(base_dir, "toolchain.part")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    try:
        done = 0
        idx = 0
        while idx < len(picked):
            first = picked[idx][0]
            run_start = first.header_offset
            run_end = first.header_offset + 4096 + first.compress_size
            j = idx + 1
            while j < len(picked):
                nxt = picked[j][0]
                nxt_end = nxt.header_offset + 4096 + nxt.compress_size
                if nxt.header_offset - run_end > RUN_GAP or nxt_end - run_start > RUN_MAX:
                    break
                run_end = max(run_end, nxt_end)
                j += 1
            rf.prefetch(run_start, run_end)
            for info, rel in picked[idx:j]:
                _write_member(zf, info, rel, stage)
                done += info.compress_size
            progress(min(done / total, 1.0))
            idx = j
        _finish(stage, os.path.join(base_dir, "toolchain"))
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return rf.fetched


def _extract_full(url, base_dir, allow, progress, log):
    candidates = [os.path.join(base_dir, "llvm_mingw_temp.zip"), os.path.join(tempfile.gettempdir(), "llvm_mingw_temp.zip")]
    temp_zip = next((c for c in candidates if _writable(c)), candidates[1])
    try:
        req = urllib.request.Request(url, headers=USER_AGENT)
        with urllib.request.urlopen(req) as r, open(temp_zip, "wb") as out:
            total = int(r.headers.get("Content-Length", 0))
            got = 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                if total:
                    progress(got / total * 0.7)
        log("Descarga completa. Extrayendo solo los archivos necesarios...")
        with zipfile.ZipFile(temp_zip) as zf:
            picked = _select(zf.infolist(), allow)
            if allow is not None and len({rel for _, rel in picked}) < 0.9 * len(allow):
                picked = _select(zf.infolist(), None)
            stage = os.path.join(base_dir, "toolchain.part")
            shutil.rmtree(stage, ignore_errors=True)
            os.makedirs(stage)
            try:
                for n, (info, rel) in enumerate(picked, 1):
                    _write_member(zf, info, rel, stage)
                    if n % 200 == 0:
                        progress(0.7 + 0.3 * n / len(picked))
                _finish(stage, os.path.join(base_dir, "toolchain"))
            except Exception:
                shutil.rmtree(stage, ignore_errors=True)
                raise
    finally:
        try:
            os.remove(temp_zip)
        except OSError:
            pass


def _writable(path):
    try:
        with open(path, "wb"):
            pass
        os.remove(path)
        return True
    except OSError:
        return False


def install(url, base_dir, allow, progress=lambda f: None, log=lambda m: None):
    """Install into <base_dir>/toolchain. `progress` gets 0..1. Raises on failure (nothing half-installed)."""
    try:
        fetched = _extract_ranged(url, base_dir, allow, progress, log)
        log(f"Descargados {fetched / 1048576:.0f} MB.")
    except Exception as e:
        log(f"Descarga parcial no disponible ({e}); se usará la descarga completa.")
        _extract_full(url, base_dir, allow, progress, log)
