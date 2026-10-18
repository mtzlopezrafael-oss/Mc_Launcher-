# MC Launcher

Launcher de Minecraft (Java Edition, modo offline) escrito en Python con `customtkinter`, inspirado en Prism Launcher: cada perfil es una instancia independiente con su propia carpeta de mods y mundos.

## Características
- **Perfiles/instancias** con versión de Minecraft, loader (Fabric, Forge, NeoForge), RAM, usuario y carpeta propios.
- **Mods** desde Modrinth y CurseForge: búsqueda, instalación, activar/desactivar y eliminar por instancia.
- **Modpacks** (`.mrpack` de Modrinth y `.zip` de CurseForge): descarga en paralelo, verificación SHA-1 y ajuste automático del perfil a la versión de Minecraft/loader que pide el modpack.
- **Java automático**: usa el runtime de Java que Mojang publica para cada versión (8, 17 o 21 según corresponda). No hace falta tener Java instalado; si lo tienes, se usa como respaldo.
- Consola integrada con la salida del juego coloreada por nivel.
- Noticias de Minecraft, temas claro/oscuro y auto-actualización desde GitHub Releases.
- Logs de diagnóstico rotativos en `~/.ctk-mc-launcher/logs/`.

## Requisitos
- Windows 10/11 (instalador `.exe` en [Releases](https://github.com/mtzlopezrafael-oss/Mc_Launcher-/releases)), o Python 3.10+ en Windows, macOS o Linux para ejecutar desde el código.
- Conexión a internet para descargar versiones, mods y el runtime de Java.

## Ejecutar desde el código
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
En Linux puede hacer falta instalar Tk: `sudo apt install python3-tk`.

## Tests
```bash
python -m unittest discover -s tests -t . -v
```
El workflow `CI` ejecuta `pyflakes` y estos tests en cada push y pull request.

## Publicar una versión
1. Cambia `"version"` en `version.json` (es la única fuente de la versión; el launcher la lee al arrancar).
2. Crea y sube el tag: `git tag v3.3.0 && git push origin v3.3.0`.
3. El workflow *Build & Release* compila el EXE con PyInstaller, genera el instalador con Inno Setup y crea el Release.

## Estructura
```
main.py                 Punto de entrada: parches de Tk, logging y manejo de errores
src/gui/                Ventana principal, componentes, diálogos y vistas
src/launcher/           Instalación y lanzamiento (core), loaders, Java, mods y modpacks
src/utils/              Configuración, perfiles, logging, red y E/S de JSON
src/updater.py          Auto-actualización
tests/                  Tests unitarios (sin interfaz gráfica)
```

## Datos del usuario
Todo se guarda en `~/.ctk-mc-launcher/`: `profiles.json`, `settings.json`, `instances/` y `logs/`. Los JSON se escriben de forma atómica; si `profiles.json` se corrompe, se guarda una copia `profiles.json.corrupt-<fecha>` antes de sobrescribirlo.

## Problemas frecuentes
- **El juego no arranca:** revisa la pestaña *Log* y, si hace falta, *Ajustes → Diagnósticos → Copiar log*.
- **Un modpack no carga:** si algún mod no se pudo descargar, el launcher lo indica; vuelve a instalar el modpack para reintentar.
- **Sin conexión:** la lista de versiones no carga; pulsa *Nuevo* para reintentar cuando vuelva la conexión.
