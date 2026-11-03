; Inno Setup script: builds dist\StudioHub-Setup.exe
#define AppVersion "1.0.0"

[Setup]
AppId={{6C4B7E1A-3F8D-4C6B-9B2E-5A1D0F7C9E21}
AppName=Studio Hub
AppVersion={#AppVersion}
AppPublisher=Studio Hub
DefaultDirName={autopf}\Studio Hub
DefaultGroupName=Studio Hub
OutputDir=..\dist
OutputBaseFilename=StudioHub-Setup
SetupIconFile=..\studio_hub\assets\icon.ico
UninstallDisplayIcon={app}\StudioHub.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "startup"; Description: "Start Studio Hub when I sign in to Windows"; Flags: unchecked
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\StudioHub\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Studio Hub"; Filename: "{app}\StudioHub.exe"
Name: "{autodesktop}\Studio Hub"; Filename: "{app}\StudioHub.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Studio Hub"; ValueData: """{app}\StudioHub.exe"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\StudioHub.exe"; Description: "Open Studio Hub"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/im StudioHub.exe /f"; Flags: runhidden; RunOnceId: "StopStudioHub"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    if MsgBox('Also remove your Studio Hub library (favourites, categories and plugin pictures)?',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\StudioHub'), True, True, True);
end;
