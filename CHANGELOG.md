# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/) while it is below 1.0 (minor versions may add features and change behavior).

Every entry is also published as the notes of its [GitHub Release](../../releases). The interface of the launcher is still in Spanish; a full English translation is planned.

## [0.9.0] - 2026-10-30

A big visual and graphics release.

### Added
- **AMD FidelityFX Super Resolution 1.0**, the real one: EASU upscaling followed by RCAS sharpening, ported to WGSL from AMD's MIT-licensed reference (`mh3u-gfx/src/fsr.rs`). It replaces the previous home-made "FSR" (a four-tap bilinear with a sharpening term). It is independent of the internal resolution; when the internal image is already as large as the window, only the RCAS sharpening is applied. FSR 2/3/4 are not an option for this port: they are temporal and need motion vectors, depth and jitter that a recompiled Wii U game does not provide (FSR 4 also needs an RDNA 4 GPU).
- **New glass interface** (PySide6 / Qt): frosted translucent panels over a soft backdrop in the Moga / Tanzia palette, the game banner fading into the header, an in-window title bar with palette-gold hover on the window buttons, and a footer drawn straight on the background.
- **Optional Windows Acrylic** (Graphics tab, restart required): lets the desktop show through the window. Leave it off on Windows 10.
- **Controls tab** with the interface for the upcoming universal button mapper (marked as coming soon). The controller layout and mouse camera sensitivity moved here from the Graphics tab.
- **Live "Active settings" summary** on the main tab: resolution, upscaler and sharpness, VSync, graphics API, window mode, FPS counter, input, controller layout, camera sensitivity, mods, audio, LTO and online status, updated as you change them.
- Link to this repository in the credits.

### Changed
- The launcher is now built with PySide6 instead of CustomTkinter. The launcher logic moved to `core.py` unchanged; the executable grows from about 22 MB to 34 MB, starts as fast as before, uses no CPU while idle and about 85 MB more RAM (around 160 MB in total).
- The Graphics tab no longer has the "FSR preset" selector: it silently changed the internal resolution and could not be combined with 4x. Resolution and upscaler are now independent settings.
- `mh3u-gfx`: the hasher no longer needs a deprecated slice iterator (same output, clean `clippy`).
- Repository documentation, release titles and notes are now in English.

### Fixed
- Visible square edges in the glass backdrop gradient.
- The update path was re-verified against the updater of the previous release (every manifest path and extension is accepted by it).

## [0.8.9] - 2026-10-30

### Fixed
- Auto-update was broken for every installed version because v0.8.8 shipped `assets/banner.jpg`, an extension the updater of older launchers rejects, and the update manifest is global. The banner is a PNG again and the updater now also accepts `.jpg`.

## [0.8.8] - 2026-10-30
### Changed
- Original launcher artwork replaces the official Capcom artwork that had been used by mistake; `logo.png` removed.

## [0.8.7] - 2026-10-30
### Added
- Detects a gamepad hidden by HidHide (for example by DSX) and offers to let `mh3u-tools.exe` use it (one UAC prompt).
### Changed
- The HID gamepad reader steps aside while an XInput pad is connected, to avoid double input.

## [0.8.6] - 2026-10-30
### Added
- Direct DualSense, DualShock 4 and generic HID gamepad support, read straight from the device (USB and Bluetooth). `MH3U_HID_PADS=0` turns it off.

## [0.8.5] - 2026-10-29
### Fixed
- The launcher relaunches cleanly after an update (it no longer inherits PyInstaller's environment, which caused "Failed to load Python DLL").

## [0.8.4] - 2026-10-29
### Changed
- The portable Clang download is partial (about 90 MB instead of 182 MB).
- Translating and compiling no longer opens a black console window.

## [0.8.3] - 2026-10-29
### Fixed
- The update script no longer dies silently (it was launched detached and its `tasklist | find` pipe failed); UTF-8 paths with accents work.

## [0.8.2] - 2026-10-29
### Changed
- The update button and status moved to the header badge.

## [0.8.1] - 2026-10-29
### Added
- Custom colour selector fix (GX2 tiling apertures), gamepad input while the window is unfocused, and a "gamepad or keyboard" selector, synced with upstream pull requests #31-#34.

## [0.8.0] - 2026-10-29
### Added
- Remote updates with SHA-256 verification, backup and rollback; full package in a single zip; AGPL-3.0 licensing with the corresponding source in `source-patches/`.

[0.9.0]: ../../releases/tag/v0.9.0
[0.8.9]: ../../releases/tag/v0.8.9
