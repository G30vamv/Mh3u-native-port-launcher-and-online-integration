# Publishing a version

## 1. Prepare

1. Bump `APP_VERSION` in `launcher/core.py`, `launcher/version_info.txt` and the version text in `package/LEEME.txt`.
2. If the translator output changed, bump `TRANSLATOR_REV` too (users will rebuild `game.dll`).
3. Add the new section to [`CHANGELOG.md`](../CHANGELOG.md) (English, [Keep a Changelog](https://keepachangelog.com) style).
4. If `mh3u-port` changed, regenerate `source-patches/` (see its README) and build `mh3u-tools.exe` (`cargo build --release -p mh3u-tools`).
5. Rebuild `MH3U.exe`: `pip install PySide6-Essentials pillow pyinstaller`, then `cd launcher && python -m PyInstaller MH3U.spec`. Put it, `mh3u-tools.exe`, `libunwind.dll`, `server.exe`, `assets/` and the files of `package/` in a distributable folder (the previous release zip with the new files replaced works).
6. Test in that folder before publishing (project rule: test before bumping the version for everyone).

## 2. Check the update path

Old launchers validate every path and extension of the manifest (`updater.py`, `ALLOWED_EXT`), and every installed launcher reads the same global manifest. Before publishing:

- Load the new file list with the `updater.py` of the **previous** release (`git show <previous tag or commit>:launcher/updater.py`) and make sure every path passes `_safe_rel` and every extension is allowed.
- Do not add file types outside `ALLOWED_EXT` while older clients are still around.
- After publishing, update a copy of the previous release to the new one with the real release (the updater downloads only the changed files).

## 3. Publish (one zip)

```powershell
python tools/publish_release.py --version v0.9.0 --dir "<distributable folder>" --title "v0.9.0 - Short title" --notes-file notes.md --summary "One short sentence for the launcher's update dialog"
```

Requires an authenticated `gh`. `--dry-run` only builds the zip; `--replace` replaces the assets of an existing release. Push `main` first: the release tag is created on it.

**Rule:** the Release page shows **only `MH3U_Port_Launcher_<version>.zip`** (everything needed to run: launcher, `mh3u-tools.exe`, `server.exe`, `libunwind.dll`, assets, guides, `LICENSE.txt`, `SOURCE.txt`, `mods/hooks.txt`), plus a tiny `manifest.json` read only by the updater, kept only on the latest release. Release notes must say "download only the zip". Titles and notes are written in English.

The script:
1. Builds the zip (folder `MH3U_Port_Launcher/`) and computes the SHA-256 of every file.
2. Uploads the individual files to the `updates` branch (immutable commit, tag `files-<version>`); the updater downloads from there only what changed, with commit-pinned URLs (no stale cache).
3. Creates the Release with the zip and `manifest.json`, and leaves only the zip on previous releases.

- `server.exe` (mh3u-revival v0.2.0-beta, unmodified) is included by default; `--no-server` leaves it out. If you update it, change the tag in `package/SOURCE.txt` and `THIRD_PARTY.md`.
- Never published: `launcher_config.json`, `game.dll`, logs.
- If you change something already published, publish a new version instead: users who already have it would not receive the change.

## 4. After publishing

The launcher reads `releases/latest/download/manifest.json`, so the Release must be the "latest" (not a pre-release or draft). `tools/make_release.py` stays as a utility to generate the files without publishing.

- With a copy of the previous launcher: *Check for updates* must offer the new version, apply it and reopen.
- To test without publishing: `set MH3U_UPDATE_MANIFEST=file:///C:/path/manifest.json` points the launcher at a local manifest.

## License obligations (AGPL-3.0)

`mh3u-tools.exe` is built from `glinesbdev/mh3u-port` (AGPL-3.0) with our own modifications. When distributing the executable we must offer its **corresponding source** (see `source-patches/`; regenerate the patches if the `mh3u-port` code changes) and link it in the release notes. `server.exe` is Matt-Wood-23's, unmodified: linking its repository is enough. The FidelityFX FSR shaders are MIT; keep the notice in `THIRD_PARTY.md`.
