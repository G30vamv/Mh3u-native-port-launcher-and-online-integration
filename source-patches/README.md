# Corresponding source of `mh3u-tools.exe` (AGPL-3.0)

`mh3u-tools.exe` in the Releases is built from [glinesbdev/mh3u-port](https://github.com/glinesbdev/mh3u-port) (AGPL-3.0) plus the changes in these patches. The patches are under **AGPL-3.0**, like the original project.

- **Base:** commit `41d3a9b` of `glinesbdev/mh3u-port` (26 Oct 2026, *Merge pull request #34*).
- **Order:** `0001` and `0002` are independent of each other; `0003` goes after `0002`, and `0004` after `0003`.

| Patch | Contents |
|---|---|
| `0001-gfx-and-build-performance.patch` | Release profile with fat LTO, fast hasher (`fxmap.rs`), GPU queue on its own thread (`queue.rs`; `MH3U_GFX_THREAD=off` disables it), **AMD FidelityFX Super Resolution 1.0** (`fsr.rs`: EASU + RCAS ported to WGSL from AMD's MIT-licensed `ffx_fsr1.h`; used when `MH3U_UPSCALER=fsr`, the default) and other `mh3u-gfx` adjustments. |
| `0002-runtime-online-and-translator.patch` | Online networking of the runtime (`net.rs`: server redirection, NAT, local IP), changes in `game.rs`, `cafe.rs`, `sync.rs`, `kernel.rs`, `guest.rs` and the translator's function discovery (`discover.rs`). |
| `0003-gamepad-hid-support.patch` | DualSense, DualShock 4 and generic HID gamepads read straight from the device (`hidpad.rs`; `MH3U_HID_PADS=0` disables it). |
| `0004-ingame-settings.patch` | The in-game settings window (F1 / F2) in the overlay (`settings.rs`, `overlay.rs`, `gx2.rs`): resolution, upscaler, sharpness, present mode, FPS counter, language and camera sensitivity; text for the game's keyboard prompts (`swkbd.rs`); right-stick sensitivity (`input.rs`). |

## Reproducing the binary

```powershell
git clone https://github.com/glinesbdev/mh3u-port.git
cd mh3u-port
git checkout 41d3a9b
git apply --ignore-whitespace <path>/0001-gfx-and-build-performance.patch
git apply --ignore-whitespace <path>/0002-runtime-online-and-translator.patch
git apply --ignore-whitespace <path>/0003-gamepad-hid-support.patch
git apply --ignore-whitespace <path>/0004-ingame-settings.patch
cargo build --release -p mh3u-tools
```

Verified: the four patches apply cleanly on `41d3a9b`, and the `mh3u-gfx` tests (including the FSR shader checks) pass on that tree. The original project's own checks (`fmt`, `clippy -D warnings`) were not run on the patched tree as a whole.
