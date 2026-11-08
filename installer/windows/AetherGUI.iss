; Aether GUI — Windows installer (Inno Setup 6)
;
; Build:
;   iscc /DMyAppVersion=2.1.0 /DAppDir=<repo> installer\windows\AetherGUI.iss
;
; The engine (aether.exe) is installed next to AetherGUI.exe on purpose: the GUI
; looks for it in its own directory first, so the pair must stay together.

#ifndef MyAppVersion
  #define MyAppVersion "2.1.0"
#endif
#ifndef AppDir
  #define AppDir "..\.."
#endif

#define MyAppName "Aether GUI"
#define MyAppShortName "AetherGUI"
#define MyAppPublisher "Nikan Developer"
#define MyAppURL "https://github.com/NikanDeveloper36/Aether-Gui"
#define MyAppExeName "AetherGUI.exe"

[Setup]
AppId={{8E4C1B42-7A3D-4F16-9C2E-1A2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile={#AppDir}\LICENSE
OutputDir={#AppDir}\installer\output
OutputBaseFilename=AetherGUI-{#MyAppVersion}-Windows-x64-Setup
SetupIconFile={#AppDir}\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Let the user choose: install for everyone (UAC) or just for themselves.
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#AppDir}\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#AppDir}\aether.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#AppDir}\assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#AppDir}\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "{#AppDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
