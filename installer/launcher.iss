; ── MC Launcher — Inno Setup Script ────────────────────────────────────────
; Inno Setup 6.x  (https://jrsoftware.org/isinfo.php)
; Este archivo es compilado por iscc.exe durante la pipeline de GitHub Actions.
; La variable {#AppVersion} se pasa desde la línea de comandos:
;   iscc /DAppVersion=3.0.2 installer\launcher.iss

#define AppName      "MC Launcher"
#define AppPublisher "mtzlopezrafael-oss"
#define AppURL       "https://github.com/mtzlopezrafael-oss/Mc_Launcher-"
#define AppExeName   "MC_Launcher.exe"
#define AppDataDir   ".ctk-mc-launcher"

[Setup]
; Identificador único — NO cambiar entre versiones (permite actualización silenciosa)
AppId={{A4B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases

; Directorio de instalación por defecto
DefaultDirName={autopf}\{#AppPublisher}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes

; Desinstala la versión anterior automáticamente antes de instalar
CloseApplications=yes
RestartIfNeededByRun=no

; Archivo de salida
OutputDir=dist_installer
OutputBaseFilename=MC_Launcher_v{#AppVersion}_Windows_x64_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}

; Compresión (más lento pero MSI mucho más pequeño)
Compression=lzma2/max
SolidCompression=yes

; Solo 64-bit
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; Requiere Windows 10 o superior
MinVersion=10.0

; El instalador NO requiere privilegios de administrador (instala en AppData si no los tiene)
PrivilegesRequiredOverridesAllowed=dialog

WizardStyle=modern
WizardResizable=no

; Página de licencia
LicenseFile=installer\license.rtf

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
; Checkbox "Crear acceso directo en el Escritorio" (marcado por defecto)
Name: "desktopicon"; Description: "Crear acceso directo en el &Escritorio"; \
  GroupDescription: "Accesos directos adicionales:"; Flags: checkedonce

[Files]
; ── Todos los archivos del ejecutable empaquetado por PyInstaller ────────────
Source: "dist\MC_Launcher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Menú Inicio
Name: "{group}\{#AppName}";          Filename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

; Escritorio (solo si el usuario marcó la opción)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; \
  Tasks: desktopicon

[Run]
; Ofrece lanzar el launcher al terminar la instalación
Filename: "{app}\{#AppExeName}"; \
  Description: "Iniciar {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpia los datos de usuario al desinstalar (opcional — comentar para conservarlos)
; Type: filesandordirs; Name: "{userappdata}\{#AppDataDir}"
