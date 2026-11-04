; Inno Setup script: builds dist\Ordel-Setup.exe
#define AppVersion "1.0.0"

[Setup]
AppId={{6C4B7E1A-3F8D-4C6B-9B2E-5A1D0F7C9E21}
AppName=Ordel
AppVersion={#AppVersion}
AppPublisher=Charlie Pheasey
DefaultDirName={autopf}\Ordel
DefaultGroupName=Ordel
OutputDir=..\dist
OutputBaseFilename=Ordel-Setup
SetupIconFile=..\studio_hub\assets\icon.ico
UninstallDisplayIcon={app}\Ordel.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "startup"; Description: "Start Ordel when I sign in to Windows"; Flags: unchecked
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Ordel\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Ordel"; Filename: "{app}\Ordel.exe"
Name: "{autodesktop}\Ordel"; Filename: "{app}\Ordel.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Ordel"; ValueData: """{app}\Ordel.exe"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Ordel.exe"; Description: "Open Ordel"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/im Ordel.exe /f"; Flags: runhidden; RunOnceId: "StopOrdel"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { Ordel's script inside REAPER; REAPER's start-up line skips it once it's gone. }
    DelTree(ExpandConstant('{userappdata}\REAPER\Scripts\StudioHub'), True, True, True);
    if MsgBox('Also remove your Ordel library (favourites, categories and plugin pictures)?',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\StudioHub'), True, True, True);
  end;
end;
