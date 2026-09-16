; Inno Setup script. Built by packaging\build_installer.ps1
; Output: installer\AeroBooks-Setup.exe

#define MyAppName "AeroBooks"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "AeroBooks"
#define MyAppURL "https://127.0.0.1:8765"
#define MyAppExeName "AeroBooks.exe"

[Setup]
AppId={{8F3C1E6A-9B21-4D47-A7C4-C4B299A8D651}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\installer
OutputBaseFilename=AeroBooks-Setup
SetupIconFile=aerobooks-setup.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
InfoBeforeFile=install_info.txt
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\AeroBooks\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "CFI invoicing"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "CFI invoicing"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Open AeroBooks"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
; User data in %LOCALAPPDATA%\AeroBooks is left in place on purpose.

[Code]
function InitializeUninstall(): Boolean;
begin
  Result := True;
  MsgBox('AeroBooks will be removed from Program Files. Your students, invoices, and backups stay in this Windows user profile (AppData\Local\AeroBooks and Documents\AeroBooks Backups).', mbInformation, MB_OK);
end;
