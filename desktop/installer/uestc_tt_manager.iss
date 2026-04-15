#define MyAppName "UESTC TT Manager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "nesettle"
#define MyAppExeName "UESTC_TT_Manager.exe"

[Setup]
AppId={{A90F3660-C74B-4D23-8EFB-7CEFEF6E61EE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
OutputDir={#RepoRoot}\release
OutputBaseFilename=UESTC_TT_Manager_Setup

[Languages]
Name: "chinesesimp"; MessagesFile: "{#RepoRoot}\desktop\installer\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务"; Flags: unchecked

[Files]
Source: "{#DistRoot}\UESTC_TT_Manager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
