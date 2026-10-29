# Código fuente correspondiente de `mh3u-tools.exe` (AGPL-3.0)

`mh3u-tools.exe` de los Releases se compila a partir de [glinesbdev/mh3u-port](https://github.com/glinesbdev/mh3u-port) (AGPL-3.0) más los cambios de estos parches. Los parches están bajo **AGPL-3.0**, igual que el proyecto original.

- **Base:** commit `1b32434` de `glinesbdev/mh3u-port` (14-oct-2026, *Merge pull request #30*).
- **Orden de aplicación:** `0001` y `0002` son independientes entre sí.

| Parche | Contenido |
|---|---|
| `0001-gfx-and-build-performance.patch` | `[profile.release]` con LTO fat, hasher rápido (`fxmap.rs`), cola de GPU en hilo propio (`queue.rs`; `MH3U_GFX_THREAD=off` la desactiva) y ajustes en `mh3u-gfx`. |
| `0002-runtime-online-and-translator.patch` | Red online del runtime (`net.rs`: redirección a servidor, NAT, IP local), ajustes en `game.rs`, `cafe.rs`, `sync.rs`, `kernel.rs`, `guest.rs` y el descubrimiento de funciones del traductor (`discover.rs`). |

## Reproducir el binario

```powershell
git clone https://github.com/glinesbdev/mh3u-port.git
cd mh3u-port
git checkout 1b32434
git apply --ignore-whitespace <ruta>/0001-gfx-and-build-performance.patch
git apply --ignore-whitespace <ruta>/0002-runtime-online-and-translator.patch
cargo build --release -p mh3u-tools
```

Verificado: ambos parches aplican limpios sobre `1b32434`. No se ha verificado el build en un clon limpio ni los checks (`fmt`, `clippy`) del proyecto original.
