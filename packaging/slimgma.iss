#ifndef AppVersion
  #error AppVersion manquant : compilez avec ISCC /DAppVersion=<version>
#endif

#ifndef PayloadDir
  #define PayloadDir "..\dist\Slimgma"
#endif

#define AppName "Slimgma"
#define AppPublisher "TenGoKu13"
#define AppUrl "https://github.com/TenGoKu13/SlimGMA"
#define AppExe "Slimgma.exe"

[Setup]
AppId={{E34C3884-9533-4C98-919D-206338ADDDD8}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExe}
LicenseFile=LICENSE.txt
OutputDir=..\dist
OutputBaseFilename=Slimgma-Setup-{#AppVersion}
SetupIconFile=..\assets\slimgma.ico
WizardStyle=modern
WizardSizePercent=110
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
DisableWelcomePage=no
CloseApplications=yes
RestartApplications=no
MinVersion=6.3

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
fr.LaunchAfter=Lancer {#AppName}
en.LaunchAfter=Launch {#AppName}
fr.DesktopIcon=Créer un raccourci sur le Bureau
en.DesktopIcon=Create a Desktop shortcut
fr.DropSettings=Supprimer aussi vos réglages ?%n%nVos préférences (langue, thème, derniers dossiers utilisés) sont conservées dans :%n%1%n%nRépondez Non si vous comptez réinstaller {#AppName} plus tard.
en.DropSettings=Also delete your settings?%n%nYour preferences (language, theme, recent folders) are stored in:%n%1%n%nAnswer No if you plan to reinstall {#AppName} later.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Vos addons Garry's Mod, en plus léger"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchAfter}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: dirifempty; Name: "{app}"

[Code]
function SettingsDir(): String;
begin
  Result := ExpandConstant('{userappdata}\Slimgma');
end;

procedure CurUninstallStepChanged(CurStep: TUninstallStep);
var
  Folder: String;
begin
  if CurStep <> usPostUninstall then
    Exit;
  Folder := SettingsDir();
  if not DirExists(Folder) then
    Exit;
  if SuppressibleMsgBox(FmtMessage(CustomMessage('DropSettings'), [Folder]),
                        mbConfirmation, MB_YESNO, IDNO) = IDYES then
    DelTree(Folder, True, True, True);
end;
