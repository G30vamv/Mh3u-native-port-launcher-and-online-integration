#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Publish a launcher release: ONE zip on the Release page, update files on the `updates` branch.

Release page (what users see): `MH3U_Port_Launcher_<ver>.zip` + a tiny `manifest.json` for the launcher.
Update files (what the in-app updater downloads, only the ones that changed): committed to the
`updates` branch and referenced by commit-pinned raw URLs (immutable, no CDN cache lag), tagged
`files-<ver>`. Older releases keep only their zip.

    python tools/publish_release.py --version v0.8.3 --dir "<built launcher folder>" \
        --title "v0.8.3 - Short title" --notes-file notes.md [--dry-run] [--replace]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import make_release as mr  # noqa: E402

REPO = mr.REPO
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UPDATES_DIR = os.path.join(ROOT, ".updates")  # separate git repo (branch `updates`), gitignored
RAW = f"https://raw.githubusercontent.com/{REPO}/"


def run(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def prepare_updates_repo():
    """Local clone of branch `updates` (created as an orphan branch the first time)."""
    url = f"https://github.com/{REPO}.git"
    if not os.path.isdir(os.path.join(UPDATES_DIR, ".git")):
        os.makedirs(UPDATES_DIR, exist_ok=True)
        run(["git", "init", "-q", "-b", "updates"], UPDATES_DIR)
        run(["git", "remote", "add", "origin", url], UPDATES_DIR)
    run(["git", "config", "core.autocrlf", "false"], UPDATES_DIR)
    run(["git", "config", "user.name", "G30vamv"], UPDATES_DIR)
    run(["git", "config", "user.email", "26340841+G30vamv@users.noreply.github.com"], UPDATES_DIR)
    if run(["git", "ls-remote", "--heads", "origin", "updates"], UPDATES_DIR):
        run(["git", "fetch", "-q", "origin", "updates"], UPDATES_DIR)
        run(["git", "checkout", "-q", "-B", "updates", "origin/updates"], UPDATES_DIR)


def commit_update_files(files_root, rels, version):
    # wipe tracked content, copy the current set (identical blobs are stored once by git)
    for name in os.listdir(UPDATES_DIR):
        if name != ".git":
            p = os.path.join(UPDATES_DIR, name)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    with open(os.path.join(UPDATES_DIR, ".gitattributes"), "w", newline="\n") as f:
        f.write("* -text\n")  # byte-exact: the updater verifies sha256
    with open(os.path.join(UPDATES_DIR, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# Archivos del actualizador\n\nRama técnica: el launcher descarga de aquí solo los archivos que cambian. "
                "No es una descarga para usuarios: baja el zip desde [Releases](../../releases/latest).\n")
    for rel in rels:
        dst = os.path.join(UPDATES_DIR, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(files_root, *rel.split("/")), dst)
    run(["git", "add", "-A", "-f"], UPDATES_DIR)
    if run(["git", "status", "--porcelain"], UPDATES_DIR):
        run(["git", "commit", "-q", "-m", f"Archivos del actualizador {version}"], UPDATES_DIR)
    return run(["git", "rev-parse", "HEAD"], UPDATES_DIR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--dir", required=True, help="built launcher folder")
    ap.add_argument("--title", required=True)
    ap.add_argument("--notes-file", required=True)
    ap.add_argument("--no-server", action="store_true")
    ap.add_argument("--summary", default="", help="one line shown in the launcher's update dialog")
    ap.add_argument("--dry-run", action="store_true", help="build assets only; no push, no release")
    ap.add_argument("--replace", action="store_true", help="release already exists: replace its assets")
    args = ap.parse_args()

    found = mr.launcher_version(args.dir)
    if found and found != args.version:
        sys.exit(f"APP_VERSION is {found}, not {args.version}")
    notes = open(args.notes_file, encoding="utf-8").read()
    rels = mr.collect(args.dir, ("server.exe",) if args.no_server else ())
    out = os.path.join(ROOT, "dist-release")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)

    zip_path = mr.build_zip(args.dir, rels, args.version, out)
    entries = [{"path": r, "sha256": mr.sha256(os.path.join(args.dir, *r.split("/"))),
                "size": os.path.getsize(os.path.join(args.dir, *r.split("/")))} for r in rels]
    print(f"zip {os.path.getsize(zip_path) / 1048576:.1f} MB, {len(entries)} files")
    if args.dry_run:
        print("dry-run: nothing published")
        return

    prepare_updates_repo()
    sha = commit_update_files(args.dir, rels, args.version)
    run(["git", "push", "-q", "origin", "updates"], UPDATES_DIR)
    tag = f"files-{args.version}"
    run(["git", "tag", "-f", tag], UPDATES_DIR)
    run(["git", "push", "-q", "-f", "origin", tag], UPDATES_DIR)
    for e in entries:
        e["url"] = f"{RAW}{sha}/{e['path']}"
    manifest = {"version": args.version, "notes": args.summary, "files": entries}
    mpath = os.path.join(out, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    exists = subprocess.run(["gh", "release", "view", args.version, "--repo", REPO], capture_output=True).returncode == 0
    if exists:
        if not args.replace:
            sys.exit(f"release {args.version} exists; pass --replace")
        names = json.loads(run(["gh", "release", "view", args.version, "--repo", REPO, "--json", "assets"]))["assets"]
        for a in names:
            run(["gh", "release", "delete-asset", args.version, a["name"], "-y", "--repo", REPO])
        run(["gh", "release", "upload", args.version, zip_path, mpath, "--clobber", "--repo", REPO])
        run(["gh", "release", "edit", args.version, "--title", args.title, "--notes-file", args.notes_file, "--latest", "--repo", REPO])
    else:
        run(["gh", "release", "create", args.version, zip_path, mpath, "--title", args.title,
             "--notes-file", args.notes_file, "--target", "main", "--latest", "--repo", REPO])

    # tidy: only the latest release carries manifest.json
    for rel in json.loads(run(["gh", "release", "list", "--repo", REPO, "--json", "tagName", "--limit", "100"])):
        if rel["tagName"] == args.version:
            continue
        assets = json.loads(run(["gh", "release", "view", rel["tagName"], "--repo", REPO, "--json", "assets"]))["assets"]
        for a in assets:
            if a["name"] != f"MH3U_Port_Launcher_{rel['tagName']}.zip":
                run(["gh", "release", "delete-asset", rel["tagName"], a["name"], "-y", "--repo", REPO])
    print(f"published {args.version}: updates@{sha[:10]}, tag {tag}")


if __name__ == "__main__":
    main()
