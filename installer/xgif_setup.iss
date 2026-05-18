; XGif Inno Setup Installer Script
; Build through build_optimized.py so MyAppVersion comes from core/version.py.

#define MyAppName "XGif"
#ifndef MyAppVersion
  #define MyAppVersion GetEnv("XGIF_APP_VERSION")
#endif
#if MyAppVersion == ""
  #error "MyAppVersion is required. Run build_optimized.py --installer or set XGIF_APP_VERSION."
#endif
#ifndef MyAppExeSource
  #define MyAppExeSource GetEnv("XGIF_APP_EXE_SOURCE")
#endif
#if MyAppExeSource == ""
  #error "MyAppExeSource is required. Run build_optimized.py --installer or set XGIF_APP_EXE_SOURCE."
#endif
#define MyAppPublisher "XGif"
#define MyAppExeName "XGif.exe"
#define MyAppURL "https://github.com/bigssu/XGif_v5"

[Setup]
AppId={{B8F3A2E1-7D4C-4E5F-9A1B-2C3D4E5F6A7B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}.0
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; 관리자 권한 불필요
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=XGif_Setup_{#MyAppVersion}
SetupIconFile=..\resources\xgif_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; 최소 Windows 10
MinVersion=10.0

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyAppExeSource}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
