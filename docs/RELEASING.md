# Publicar una versión

## 1. Preparar

1. Sube `APP_VERSION` en `launcher/mh3u_launcher.py`, `version_info.txt` y los textos de `package/LEEME.txt`.
2. Si cambió la salida del traductor, sube también `TRANSLATOR_REV` (los usuarios recompilarán `game.dll`).
3. Reconstruye `MH3U.exe` (`pyinstaller MH3U.spec`) y deja la carpeta distribuible completa (`MH3U.exe`, `mh3u-tools.exe`, `libunwind.dll`, `assets/`, archivos de `package/`).
4. Prueba en esa carpeta antes de publicar (regla del proyecto: probar antes de subir versión).

## 2. Generar los archivos del Release

```powershell
python tools/make_release.py --version v0.8.0 --dir "<carpeta distribuible>" --out dist-release --notes "Qué cambia"
```

Genera en `dist-release/`: los archivos planos, `manifest.json` (SHA-256 y URLs) y `MH3U_Port_Launcher_v0.8.0.zip` para instalaciones nuevas. Falla si `--version` no coincide con `APP_VERSION`.

- `server.exe` (mh3u-revival v0.2.0-beta, sin modificar) se incluye por defecto; `--no-server` lo omite. Si lo actualizas a otra versión, cambia el tag en `package/SOURCE.txt` y `THIRD_PARTY.md`.
- Nunca se publican: `SI_WiiU_MonsterHunter3Ultimate.jpg`, `launcher_config.json`, `game.dll`, logs.

## 3. Publicar

Crea un Release con el tag `v0.8.0` y sube **todo** el contenido de `dist-release/` (el launcher lee `releases/latest/download/manifest.json`, así que el Release debe ser el "latest", no un pre-release ni borrador).

## 4. Verificar

- Con una copia del launcher anterior: *Buscar actualizaciones* debe ofrecer la versión nueva, aplicar y reabrir.
- Para probar sin publicar: `set MH3U_UPDATE_MANIFEST=file:///C:/ruta/manifest.json` apunta el launcher a un manifiesto local.

## Obligaciones de licencia (AGPL-3.0)

`mh3u-tools.exe` se compila a partir de `glinesbdev/mh3u-port` (AGPL-3.0) con modificaciones propias. Al distribuir el ejecutable hay que ofrecer su **código fuente correspondiente** (ver `source-patches/`; regenera los parches si cambia el código de `mh3u-port`) y enlazarlo en las notas del Release. `server.exe` es el de Matt-Wood-23 sin modificar: basta con enlazar su repositorio.

## Seguridad

El SHA-256 protege contra descargas corruptas, no contra una cuenta comprometida. Activa 2FA en la cuenta de GitHub y no compartas tokens de publicación.
