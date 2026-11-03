; Instalador de Inno Setup 6. Lo compila construir_windows.bat pasando:
;   /DMyAppName=<nombre visible> /DMyAppExe=<nombre de archivo> /DMyAppVersion=x.y.z /DMyAppId=<GUID de la marca>
; El AppId (marca*.json, «appid_inno») no debe cambiar nunca: así una versión nueva se instala encima de la anterior.
; Los archivos de datos (.xghc, .lphr) son del usuario y nunca se tocan al instalar ni al desinstalar.
#ifndef MyAppVersion
  #error Compile con construir_windows.bat
#endif

[Setup]
AppId={{{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=LomoXSoft
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany=LomoXSoft
VersionInfoDescription=Instalador de {#MyAppName}
CloseApplications=yes
RestartApplications=no
DefaultDirName={autopf}\{#MyAppExe}
DefaultGroupName={#MyAppName}
DisableDirPage=auto
DisableProgramGroupPage=auto
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputBaseFilename={#MyAppExe}-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExe}.exe

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\{#MyAppExe}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LEEME.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}.exe"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}.exe"; Tasks: escritorio

[Run]
Filename: "{app}\{#MyAppExe}.exe"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
