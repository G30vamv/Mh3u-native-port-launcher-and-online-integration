# Third-party components

This project is AGPL-3.0-only. The Releases include or download the following third-party components, each under its own license. The repository contains no game files.

| Component | Author | License | Use |
|---|---|---|---|
| [mh3u-port](https://github.com/glinesbdev/mh3u-port) | glinesbdev | AGPL-3.0 | Translator / runtime of the native port. `mh3u-tools.exe` in the Releases is a build with our own modifications (performance, FSR upscaling, online network, HID gamepads); its corresponding source must be available under the AGPL (see `source-patches/`). |
| [mh3u-revival](https://github.com/Matt-Wood-23/mh3u-revival) | Matt-Wood-23 | AGPL-3.0 | NEX server (`server.exe`), **unmodified**, version v0.2.0-beta (byte-identical to the `server.exe` in its `MH3U_Online_Bundle.zip`, SHA-256 `6c447a013f3d…`). Source: <https://github.com/Matt-Wood-23/mh3u-revival/tree/v0.2.0-beta>. |
| [FidelityFX Super Resolution 1.0](https://github.com/GPUOpen-Effects/FidelityFX-FSR) | Advanced Micro Devices, Inc. | MIT | EASU and RCAS shaders, ported to WGSL in `mh3u-gfx/src/fsr.rs` (part of `mh3u-tools.exe`). Notice below. |
| [llvm-mingw](https://github.com/mstorsjo/llvm-mingw) | Martin Storsjö | Apache-2.0 with LLVM exception / MIT | Portable Clang compiler that the launcher downloads on demand. |
| LLVM `libunwind.dll` | LLVM Project | Apache-2.0 with LLVM exception | Runtime required by `mh3u-tools.exe`. |
| [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/) | The Qt Company | LGPL-3.0 | Launcher interface (bundled dynamically in `MH3U.exe`). |
| [Pillow](https://python-pillow.org/) | Pillow contributors | HPND | Image handling (backdrop and glass rendering). |
| [PyInstaller](https://pyinstaller.org/) | PyInstaller team | GPL-2.0 with bootloader exception | Packaging of `MH3U.exe`. |

## AMD FidelityFX Super Resolution 1.0 notice

Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and / or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions : The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

*Monster Hunter 3 Ultimate* is owned by Capcom / Nintendo. This project is not affiliated with them.
