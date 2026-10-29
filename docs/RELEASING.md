# Publicar una versión

## 1. Preparar

1. Sube `APP_VERSION` en `launcher/mh3u_launcher.py`, `version_info.txt` y los textos de `package/LEEME.txt`.
2. Si cambió la salida del traductor, sube también `TRANSLATOR_REV` (los usuarios recompilarán `game.dll`).
3. Reconstruye `MH3U.exe` (`pyinstaller MH3U.spec`) y deja la carpeta distribuible completa (`MH3U.exe`, `mh3u-tools.exe`, `libunwind.dll`, `assets/`, archivos de `package/`).
4. Prueba en esa carpeta antes de publicar (regla del proyecto: probar antes de subir versión).

## 2. Publicar (un solo zip)

```powershell
python tools/publish_release.py --version v0.8.3 --dir "<carpeta distribuible>" --title "v0.8.3 - Título corto" --notes-file notas.md
```

Requiere `gh` autenticado. `--dry-run` solo construye el zip; `--replace` reemplaza los archivos de un release ya existente.

**Regla:** la página del Release muestra **solo `MH3U_Port_Launcher_<versión>.zip`** (todo lo necesario para que funcione: launcher, `mh3u-tools.exe`, `server.exe`, `libunwind.dll`, assets, guías, `LICENSE.txt`, `SOURCE.txt`, `mods/hooks.txt`), más un `manifest.json` diminuto que solo lee el actualizador y que solo conserva el último release. Las notas deben decir "descarga solo el zip".

El script:
1. Construye el zip (carpeta `MH3U_Port_Launcher/`) y calcula el SHA-256 de cada archivo.
2. Sube los archivos individuales a la rama `updates` (commit inmutable, tag `files-<versión>`); el actualizador baja de ahí solo lo que cambió, con URLs fijadas al commit (sin caché obsoleta).
3. Crea el Release con el zip y el `manifest.json`, y deja solo el zip en los releases anteriores.

- `server.exe` (mh3u-revival v0.2.0-beta, sin modificar) se incluye por defecto; `--no-server` lo omite. Si lo actualizas, cambia el tag en `package/SOURCE.txt` y `THIRD_PARTY.md`.
- Nunca se publican: `SI_WiiU_MonsterHunter3Ultimate.jpg`, `launcher_config.json`, `game.dll`, logs.
- Si cambias algo ya publicado, mejor sube una versión nueva: los usuarios que ya la tienen no recibirían el cambio.

## 3. Publicado el Release

El launcher lee `releases/latest/download/manifest.json`, así que el Release debe ser el "latest" (no pre-release ni borrador). `tools/make_release.py` queda como utilidad para generar los archivos sin publicar.

## 4. Verificar

- Con una copia del launcher anterior: *Buscar actualizaciones* debe ofrecer la versión nueva, aplicar y reabrir.
- Para probar sin publicar: `set MH3U_UPDATE_MANIFEST=file:///C:/ruta/manifest.json` apunta el launcher a un manifiesto local.

## Obligaciones de licencia (AGPL-3.0)

`mh3u-tools.exe` se compila a partir de `glinesbdev/mh3u-port` (AGPL-3.0) con modificaciones propias. Al distribuir el ejecutable hay que ofrecer su **código fuente correspondiente** (ver `source-patches/`; regenera los parches si cambia el código de `mh3u-port`) y enlazarlo en las notas del Release. `server.exe` es el de Matt-Wood-23 sin modificar: basta con enlazar su repositorio.

## Seguridad

El SHA-256 protege contra descargas corruptas, no contra una cuenta comprometida. Activa 2FA en la cuenta de GitHub y no compartas tokens de publicación.
