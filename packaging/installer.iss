; Inno Setup script: builds dist\Mise-Setup.exe
#define AppVersion "1.0.0"

[Setup]
AppId={{6C4B7E1A-3F8D-4C6B-9B2E-5A1D0F7C9E21}
AppName=Mise
AppVersion={#AppVersion}
AppPublisher=Charlie Pheasey
DefaultDirName={autopf}\Mise
DefaultGroupName=Mise
OutputDir=..\dist
OutputBaseFilename=Mise-Setup
SetupIconFile=..\studio_hub\assets\icon.ico
UninstallDisplayIcon={app}\Mise.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "startup"; Description: "Start Mise when I sign in to Windows"; Flags: unchecked
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Mise\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Mise"; Filename: "{app}\Mise.exe"
Name: "{autodesktop}\Mise"; Filename: "{app}\Mise.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Mise"; ValueData: """{app}\Mise.exe"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Mise.exe"; Description: "Open Mise"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/im Mise.exe /f"; Flags: runhidden; RunOnceId: "StopMise"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    if MsgBox('Also remove your Mise library (favourites, categories and plugin pictures)?',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\StudioHub'), True, True, True);
end;
