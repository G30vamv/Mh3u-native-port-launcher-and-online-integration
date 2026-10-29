# Componentes de terceros

Este repositorio **no contiene** código de terceros ni archivos del juego. Los lanzamientos (Releases) distribuyen o descargan los siguientes componentes, cada uno bajo su propia licencia:

| Componente | Autor | Licencia | Uso |
|---|---|---|---|
| [mh3u-port](https://github.com/glinesbdev/mh3u-port) | glinesbdev | AGPL-3.0 | Traductor/runtime del port nativo. `mh3u-tools.exe` de los Releases es una compilación con modificaciones propias (rendimiento y red online); su código fuente correspondiente debe estar disponible según la AGPL (ver `source-patches/`). |
| [mh3u-revival](https://github.com/Matt-Wood-23/mh3u-revival) | Matt-Wood-23 | AGPL-3.0 | Servidor NEX (`server.exe`), sin modificaciones. |
| [llvm-mingw](https://github.com/mstorsjo/llvm-mingw) | Martin Storsjö | Apache-2.0 con excepción LLVM / MIT | Compilador Clang portátil que el launcher descarga bajo demanda. |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | Tom Schimansky | MIT | Interfaz del launcher. |
| [Pillow](https://python-pillow.org/) | Pillow contributors | HPND | Manejo de imágenes. |
| [PyInstaller](https://pyinstaller.org/) | PyInstaller team | GPL-2.0 con excepción de bootloader | Empaquetado de `MH3U.exe`. |

*Monster Hunter 3 Ultimate* es propiedad de Capcom / Nintendo. Este proyecto no está afiliado a ellas.
