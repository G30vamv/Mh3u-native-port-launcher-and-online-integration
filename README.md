# MH3U Native Port Launcher & Online Integration

Launcher gráfico para Windows del **port nativo de PC de Monster Hunter 3 Ultimate** (recompilación estática de la versión Wii U), con modo **multijugador online por VPN** y **actualizaciones automáticas** desde GitHub Releases.

> **Aviso legal.** Este repositorio no contiene ni distribuye ningún archivo del juego (ejecutables, modelos, texturas, audio). Necesitas tu propia copia legítima de *Monster Hunter 3 Ultimate* (Wii U, versión USA + actualización v32) extraída de tu consola. Proyecto de fans, sin afiliación con Capcom ni Nintendo.

## Qué incluye

- **Instalación guiada:** detecta tu dump (juego base + update), descarga un Clang portátil bajo demanda y compila `game.dll` para tu CPU (con LTO opcional).
- **Configuración gráfica:** escala interna 1x–4x, escalado AMD FSR 1.0 / CAS, backend Vulkan o DX12.
- **Multijugador online:** servidor de sala integrado, reglas de firewall automáticas (un solo aviso UAC) y guía para jugar con amigos por Radmin VPN. Ver [`package/INSTRUCCIONES_MULTIJUGADOR.txt`](package/INSTRUCCIONES_MULTIJUGADOR.txt).
- **Actualizaciones remotas:** botón *Buscar actualizaciones* (y comprobación al abrir) que descarga solo los archivos que cambiaron, los verifica con SHA-256, hace copia de seguridad y revierte si algo falla.
- Diseño propio con paleta Moga/Tanzia y registro en vivo de compilación y servidor.

## Requisitos

- Windows 10/11 de 64 bits y GPU con Vulkan o DirectX 12.
- Tu dump de MH3U (ver [`package/WUA_EXTRACTION_GUIDE.txt`](package/WUA_EXTRACTION_GUIDE.txt) si tienes un `.wua`).
- Espacio libre para el dump compilado y el Clang portátil (~400 MB).

## Instalación

1. Descarga `MH3U_Port_Launcher_vX.Y.Z.zip` desde [**Releases**](../../releases/latest) (incluye todo lo necesario: launcher, motor del port y servidor online) y descomprímelo en una carpeta con permisos de escritura (no `Program Files`).
2. Abre `MH3U.exe`, ve a **Instalación & Dump**, selecciona la carpeta de tu juego y pulsa **Traducir y Compilar** (solo la primera vez).
3. Pulsa **JUGAR**.

A partir de ahí, el propio launcher te avisa de nuevas versiones.

## Cómo funcionan las actualizaciones

Cada Release publica un `manifest.json` con la versión, las notas y la lista de archivos con su SHA-256. El launcher:

1. Lee `releases/latest/download/manifest.json`.
2. Compara con su versión y calcula qué archivos cambiaron.
3. Descarga solo esos archivos a `_update/` y verifica cada hash.
4. Se cierra; un script temporal respalda lo anterior en `_update_backup/`, copia los nuevos, **revierte si hay error** y reabre el launcher.

Nunca toca `launcher_config.json`, `game.dll`, `toolchain/` ni los logs. Si publicas un Release que cambia la salida del traductor, el launcher pedirá recompilar `game.dll` automáticamente.

## Compilar desde el código

```powershell
pip install customtkinter pillow pyinstaller
cd launcher
python mh3u_launcher.py            # ejecutar sin empaquetar
pyinstaller MH3U.spec              # generar MH3U.exe
```

Los binarios `mh3u-tools.exe` (motor del port) y `server.exe` (servidor NEX) no se versionan aquí: viajan en los Releases. Su código fuente correspondiente está en [`source-patches/`](source-patches/) (parches sobre `glinesbdev/mh3u-port`) y en el repositorio de [mh3u-revival v0.2.0-beta](https://github.com/Matt-Wood-23/mh3u-revival/tree/v0.2.0-beta). Para publicar una versión nueva, ver [`docs/RELEASING.md`](docs/RELEASING.md).

## Estructura

```
launcher/   Código del launcher (mh3u_launcher.py, updater.py), spec de PyInstaller y assets
package/    Archivos que van junto a MH3U.exe en los Releases (guías, firewall, LICENSE, SOURCE, hooks)
source-patches/  Código fuente correspondiente de mh3u-tools.exe (AGPL-3.0)
tools/      make_release.py: genera manifest.json + zip de un Release
tests/      Pruebas del actualizador
docs/       Guía de publicación
```

## Créditos

- **Launcher, integración online y optimizaciones de rendimiento:** g30wolff99 ([@G30vamv](https://github.com/G30vamv)).
- **Port nativo y recompilación PC:** [glinesbdev/mh3u-port](https://github.com/glinesbdev/mh3u-port) (AGPL-3.0).
- **Servidor y lógica de red online:** [Matt-Wood-23/mh3u-revival](https://github.com/Matt-Wood-23/mh3u-revival) (AGPL-3.0).
- Clang portátil: [llvm-mingw](https://github.com/mstorsjo/llvm-mingw).

## Licencia

Todo el proyecto se publica bajo **GNU AGPL-3.0-only** (ver [`LICENSE`](LICENSE)), la misma licencia que `mh3u-port` y `mh3u-revival`, por tratarse de un proyecto de preservación del videojuego. Los Releases incluyen `LICENSE.txt` y `SOURCE.txt` con los enlaces al código fuente de cada componente. La licencia no cubre el juego (© Capcom) ni las marcas de Capcom y Nintendo. Otros componentes: [`THIRD_PARTY.md`](THIRD_PARTY.md).
