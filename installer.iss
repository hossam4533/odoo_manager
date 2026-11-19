; Odoo Manager installer — compile with Inno Setup 6:  ISCC.exe installer.iss
; tools\release.py passes the version:  ISCC.exe /DAppVersion=1.2.0 installer.iss
#define AppName "Odoo Manager"
#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif
#define AppPublisher "Hossam Ramadan"

[Setup]
AppId={{6C1E2F4A-8B3D-4E7A-9F21-0D5B7C9A1E33}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\OdooManager
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\OdooManager.exe
OutputDir=dist
OutputBaseFilename=OdooManager-Setup-{#AppVersion}
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
; an update installs over the running app: close it first, reuse the previous folder and choices
CloseApplications=force
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
UsePreviousPrivileges=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\OdooManager.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\OdooManager.exe"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\OdooManager.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\OdooManager.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; after a silent in-app update, reopen the new version
Filename: "{app}\OdooManager.exe"; Flags: nowait; Check: IsAppUpdate

[Code]
function IsAppUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;
