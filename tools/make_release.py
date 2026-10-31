#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build the assets of a launcher release: flat files + manifest.json + first-install zip.

Usage (from the repo root):
    python tools/make_release.py --version v0.8.0 --dir "<built launcher folder>" --out dist-release \
        --notes "What changed" [--no-server]

<built launcher folder> is the distributable folder (MH3U.exe, mh3u-tools.exe, assets/, ...).
Upload everything in --out to a GitHub Release tagged with the same version. The launcher reads
`manifest.json` from `releases/latest/download/` and downloads only files whose sha256 changed.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile

REPO = "G30vamv/Mh3u-native-port-launcher-and-online-integration"

# Files that may be part of an update (relative to the launcher folder).
UPDATE_FILES = [
    "MH3U.exe",
    "mh3u-tools.exe",
    "libunwind.dll",
    "ABRIR_FIREWALL_ONLINE.bat",
    "LEEME.txt",
    "INSTRUCCIONES_MULTIJUGADOR.txt",
    "WUA_EXTRACTION_GUIDE.txt",
    "LICENSE.txt",
    "SOURCE.txt",
    "mods/hooks.txt",
    "server.exe",
]
UPDATE_DIRS = ["assets"]  # + mods/hooks.txt above
# Never published: Nintendo artwork, per-user data, builds and logs.
NEVER = {
    "SI_WiiU_MonsterHunter3Ultimate.jpg",
    "launcher_config.json",
    "game.dll",
    "game.dll.rev",
    "server.log",
    "mh3u_latest.log",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(src, skip=()):
    rels = [f for f in UPDATE_FILES if f not in skip and os.path.isfile(os.path.join(src, f))]
    for d in UPDATE_DIRS:
        for root, _, files in os.walk(os.path.join(src, d)):
            for name in files:
                if name in NEVER:
                    continue
                rels.append(os.path.relpath(os.path.join(root, name), src).replace(os.sep, "/"))
    return rels


def build_zip(src, rels, version, out):
    """First-install zip: everything the launcher needs, inside MH3U_Port_Launcher/."""
    zip_path = os.path.join(out, f"MH3U_Port_Launcher_{version}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in rels:
            z.write(os.path.join(src, *rel.split("/")), "MH3U_Port_Launcher/" + rel)
    return zip_path


def launcher_version(src):
    for candidate in (os.path.join(os.path.dirname(__file__), "..", "launcher", "core.py"),):
        if os.path.isfile(candidate):
            m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', open(candidate, encoding="utf-8").read(), re.M)
            if m:
                return m.group(1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="e.g. v0.8.0 (must match APP_VERSION)")
    ap.add_argument("--dir", required=True, help="built launcher folder")
    ap.add_argument("--out", default="dist-release")
    ap.add_argument("--notes", default="")
    ap.add_argument("--no-server", action="store_true", help="leave server.exe out (unchanged third-party binary, mh3u-revival v0.2.0-beta)")
    args = ap.parse_args()

    found = launcher_version(args.dir)
    if found and found != args.version:
        sys.exit(f"APP_VERSION in launcher/core.py is {found}, not {args.version}. Fix one of them first.")
    if not os.path.isfile(os.path.join(args.dir, "MH3U.exe")):
        sys.exit("MH3U.exe not found in --dir")

    rels = collect(args.dir, ("server.exe",) if args.no_server else ())
    os.makedirs(args.out, exist_ok=True)
    base_url = f"https://github.com/{REPO}/releases/download/{args.version}/"
    entries = []
    for rel in rels:
        flat = rel.replace("/", "__")
        dst = os.path.join(args.out, flat)
        shutil.copy2(os.path.join(args.dir, *rel.split("/")), dst)
        entries.append({"path": rel, "url": base_url + flat, "sha256": sha256(dst), "size": os.path.getsize(dst)})

    manifest = {"version": args.version, "notes": args.notes, "files": entries}
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    zip_path = build_zip(args.dir, rels, args.version, args.out)

    print(f"{len(entries)} files, zip {os.path.getsize(zip_path) / 1048576:.1f} MB -> {args.out}")
    for e in entries:
        print(f"  {e['sha256'][:12]}  {e['size']:>10}  {e['path']}")


if __name__ == "__main__":
    main()
