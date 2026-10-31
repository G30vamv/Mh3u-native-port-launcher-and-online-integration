# MH3U Native Port Launcher & Online Integration

A graphical launcher for Windows for the **native PC port of Monster Hunter 3 Ultimate** (a static recompilation of the Wii U version), with **online multiplayer over a VPN** and **automatic updates** from GitHub Releases.

> **Legal notice.** This repository does not contain or distribute any game file (executables, models, textures, audio). You need your own legitimate copy of *Monster Hunter 3 Ultimate* (Wii U, USA version + update v32) dumped from your console. Fan project, not affiliated with Capcom or Nintendo.

## What it includes

- **Guided setup:** finds your dump (base game + update), downloads a portable Clang on demand and builds `game.dll` for your CPU (optional LTO).
- **Graphics settings:** internal resolution 1x-4x, **AMD FidelityFX Super Resolution 1.0** (real EASU + RCAS) or CAS sharpening, Vulkan or DirectX 12 backend, VSync modes, FPS counter.
- **Controls tab:** controller layout and camera sensitivity, plus the interface for the upcoming universal button mapper.
- **Online multiplayer:** built-in room server, automatic firewall rules (a single UAC prompt) and a guide to play with friends over Radmin VPN. See [`package/INSTRUCCIONES_MULTIJUGADOR.txt`](package/INSTRUCCIONES_MULTIJUGADOR.txt).
- **Remote updates:** *Check for updates* button (and a silent check on start) that downloads only the files that changed, verifies them with SHA-256, makes a backup and rolls back if anything fails.
- **Glass interface** in the Moga / Tanzia palette: frosted panels over a soft backdrop, in-window title bar, optional Windows Acrylic, live summary of your active settings and live compile / server logs.

The launcher itself is currently in Spanish; a full English translation is planned for the next release.

## Requirements

- 64-bit Windows 10/11 and a GPU with Vulkan or DirectX 12.
- Your MH3U dump (see [`package/WUA_EXTRACTION_GUIDE.txt`](package/WUA_EXTRACTION_GUIDE.txt) if you have a `.wua`).
- Free disk space for the compiled dump and the portable Clang (~400 MB).

## Installation

1. Download `MH3U_Port_Launcher_vX.Y.Z.zip` from [**Releases**](../../releases/latest) (it contains everything needed: launcher, port engine and online server) and extract it to a writable folder (not `Program Files`).
2. Open `MH3U.exe`, go to **Instalación & Dump**, select your game folder and press **Traducir y Compilar** (first time only).
3. Press **JUGAR**.

After that, the launcher tells you about new versions by itself.

## How updates work

Every Release publishes a `manifest.json` with the version, the notes and the list of files with their SHA-256. The launcher:

1. Reads `releases/latest/download/manifest.json`.
2. Compares versions and works out which files changed.
3. Downloads only those files to `_update/` and verifies each hash.
4. Closes itself; a temporary script backs up the old files to `_update_backup/`, copies the new ones, **rolls back on error** and reopens the launcher.

It never touches `launcher_config.json`, `game.dll`, `toolchain/` or the logs. If a Release changes the translator output, the launcher asks to rebuild `game.dll` automatically.

## Building from source

```powershell
pip install PySide6-Essentials pillow pyinstaller
cd launcher
python mh3u_launcher_qt.py         # run without packaging
pyinstaller MH3U.spec              # build MH3U.exe
python -m unittest discover -s ../tests
```

The binaries `mh3u-tools.exe` (the port engine) and `server.exe` (NEX server) are not versioned here: they ship in the Releases. Their corresponding source is in [`source-patches/`](source-patches/) (patches on top of `glinesbdev/mh3u-port`) and in the [mh3u-revival v0.2.0-beta](https://github.com/Matt-Wood-23/mh3u-revival/tree/v0.2.0-beta) repository. To publish a new version, see [`docs/RELEASING.md`](docs/RELEASING.md). Version history: [`CHANGELOG.md`](CHANGELOG.md).

## Layout

```
launcher/        Launcher code: core.py (logic), mh3u_launcher_qt.py (window), qt*.py (glass UI), updater.py, PyInstaller spec, assets
package/         Files shipped next to MH3U.exe in the Releases (guides, firewall script, LICENSE, SOURCE, hooks)
source-patches/  Corresponding source of mh3u-tools.exe (AGPL-3.0)
tools/           make_release.py / publish_release.py: build the zip + manifest.json and publish a Release
tests/           Tests (updater, HidHide, toolchain installer, glass UI)
docs/            Release guide
```

## Credits

- **Launcher, online integration and performance work:** g30wolff99 ([@G30vamv](https://github.com/G30vamv)).
- **Native port and PC recompilation:** [glinesbdev/mh3u-port](https://github.com/glinesbdev/mh3u-port) (AGPL-3.0).
- **Server and online network logic:** [Matt-Wood-23/mh3u-revival](https://github.com/Matt-Wood-23/mh3u-revival) (AGPL-3.0).
- Upscaling: [AMD FidelityFX Super Resolution 1.0](https://github.com/GPUOpen-Effects/FidelityFX-FSR) (MIT).
- Portable Clang: [llvm-mingw](https://github.com/mstorsjo/llvm-mingw).

## License

The whole project is published under the **GNU AGPL-3.0-only** (see [`LICENSE`](LICENSE)), the same license as `mh3u-port` and `mh3u-revival`, as it is a game preservation project. Releases include `LICENSE.txt` and `SOURCE.txt` with links to the source of each component. The license does not cover the game (© Capcom) nor the Capcom and Nintendo trademarks. Other components: [`THIRD_PARTY.md`](THIRD_PARTY.md).
