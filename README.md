# CustomTk Minecraft Launcher

Launcher de escritorio en Python con interfaz moderna para descargar y ejecutar Minecraft en modo offline usando `minecraft-launcher-lib`.

## Características
- Tema oscuro estilo gaming en `customtkinter`.
- Login offline con nombre de usuario.
- Selector de versión oficial (release/snapshot).
- Selector rápido de RAM (512 MB a 8 GB).
- Barra de progreso y consola de log embebida.
- Detección automática de Java (muestra advertencia si falta).
- Descarga y lanzamiento en hilo separado para no congelar la UI.

## Requisitos del sistema
- Python 3.10 o superior.
- Java 17+ instalado y en PATH o configurado en `JAVA_HOME`.
- Conexión a internet para descargar versiones de Minecraft.
- SO compatible: Windows, macOS y Linux.

## Instalación
1) Clonar o copiar este directorio `minecraft-launcher`.
2) Crear entorno virtual:
   - Windows (PowerShell): `python -m venv .venv; .\\.venv\\Scripts\\activate`
   - macOS/Linux: `python -m venv .venv && source .venv/bin/activate`
3) Instalar dependencias: `pip install -r requirements.txt`

## Uso
1) Activa el entorno virtual si no lo está.
2) Ejecuta el launcher: `python main.py`
3) En la ventana:
   - Ingresa un nombre de usuario (offline).
   - Elige la versión de Minecraft.
   - Ajusta la RAM.
   - Presiona **PLAY**. La descarga se mostrará en la barra y el log.

## Capturas (descripción)
- **Pantalla principal:** fondo oscuro, campos de Usuario, Versión y RAM en la parte superior, botón PLAY destacado, barra de progreso debajo y consola de log en la parte inferior.
- **Advertencia Java:** mensaje en la esquina derecha si Java no está disponible.

## Troubleshooting
- **Java no encontrado:** Instala JDK 17+ y reinicia. Asegúrate de que `java -version` funcione en la terminal.
- **Descarga lenta o fallida:** verifica la conexión y vuelve a intentar; la librería reanuda descargas parciales.
- **Errores de permisos en macOS/Linux:** ejecuta desde una ruta donde tu usuario tenga permisos de escritura; el directorio de datos es `~/.minecraft`.
- **La ventana se queda congelada:** asegúrate de no cerrar la terminal mientras corre; la descarga y el juego se ejecutan en hilos separados.
