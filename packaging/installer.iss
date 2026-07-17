; Installer Inno Setup - BrioFEview
; Prerequisito: build PyInstaller già eseguita (dist\BrioFEview)
; Compilazione: iscc packaging\installer.iss   (dalla root dev\)

#define AppName "BrioFEview"
#define AppVersion "0.1-beta"
#define AppPublisher "Giovanni Genna"
#define AppExe "BrioFEview.exe"
#define ProgId "BrioFEview.Fattura"
#define AppURL "https://github.com/denvermotel/BrioFEview"

[Setup]
AppId={{B7E1C2D4-8A55-4E1B-9C33-0FA77A0AF001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputBaseFilename=BrioFEview_Setup_{#AppVersion}
OutputDir=..\dist\installer
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un'icona sul desktop"; Flags: unchecked
Name: "openwith_xml"; Description: "Mostra in «Apri con» per i file .xml"
Name: "openwith_p7m"; Description: "Mostra in «Apri con» per i file .p7m"
Name: "default_xml"; Description: "Imposta come app predefinita per i file .xml"; Flags: unchecked
Name: "default_p7m"; Description: "Imposta come app predefinita per i file .p7m"; Flags: unchecked

[Files]
Source: "..\dist\BrioFEview\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; ProgID (HKA = HKLM se admin, HKCU se utente)
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueData: "Fattura elettronica XML - BrioFEview"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueData: """{app}\{#AppExe}"",0"
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""
; Apri con
Root: HKA; Subkey: "Software\Classes\.xml\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Tasks: openwith_xml; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.p7m\OpenWithProgids"; ValueType: none; ValueName: "{#ProgId}"; Tasks: openwith_p7m; Flags: uninsdeletevalue
; Predefinita
Root: HKA; Subkey: "Software\Classes\.xml"; ValueType: string; ValueData: "{#ProgId}"; Tasks: default_xml
Root: HKA; Subkey: "Software\Classes\.p7m"; ValueType: string; ValueData: "{#ProgId}"; Tasks: default_p7m

[Run]
Filename: "{app}\{#AppExe}"; Description: "Avvia {#AppName}"; Flags: nowait postinstall skipifsilent
