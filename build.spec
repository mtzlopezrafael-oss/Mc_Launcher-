# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec — MC Launcher

Uso en Windows (desde la raíz del proyecto):
    pyinstaller build.spec --noconfirm

Salida:
    dist/MC_Launcher/MC_Launcher.exe   (+ todas las dependencias)

La carpeta dist/MC_Launcher/ es lo que empaqueta el instalador WiX.
"""

from pathlib import Path
import customtkinter

block_cipher = None

# ── Ruta al paquete customtkinter (necesario para incluir sus temas/assets) ──
CTK_PATH = Path(customtkinter.__file__).parent

a = Analysis(
    ['main.py'],
    pathex=[str(Path('.').resolve())],
    binaries=[],
    datas=[
        (str(CTK_PATH),    'customtkinter'),  # Temas e imágenes de CTk
        ('assets',         'assets'),          # Iconos del launcher
        ('version.json',   '.'),               # Usado por el auto-updater
    ],
    hiddenimports=[
        'customtkinter',
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',
        'minecraft_launcher_lib',
        'minecraft_launcher_lib.install',
        'minecraft_launcher_lib.command',
        'minecraft_launcher_lib.utils',
        'requests',
        'certifi',
        'charset_normalizer',
        'idna',
        'urllib3',
        'packaging',
        'packaging.version',
        'logging.handlers',
        'zipfile',
        'shutil',
        'tempfile',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter.test',
        'unittest',
        'test',
        'xmlrpc',
        'ftplib',
        'imaplib',
        'poplib',
        'smtplib',
        'telnetlib',
        'nntplib',
        'doctest',
        'pdb',
        'pydoc',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MC_Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,            # Sin ventana de consola negra
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\icon.ico',  # Generado en la pipeline (PNG → ICO)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MC_Launcher',
)
