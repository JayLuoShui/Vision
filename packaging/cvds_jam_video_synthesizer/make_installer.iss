#define MyAppName "CVDS Jam Video Synthesizer"
#define MyAppChineseName "CVDS 包裹堵塞视频合成工具"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "CVDS"
#define MyAppExeName "CVDS_Jam_Video_Synthesizer.exe"

[Setup]
AppId={{8F82F76A-C6EF-49CE-89E8-36B9062C06D4}
AppName={#MyAppChineseName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CVDS\CVDS Jam Video Synthesizer
DefaultGroupName=CVDS\CVDS Jam Video Synthesizer
DisableProgramGroupPage=yes
OutputDir=..\..\dist_installer
OutputBaseFilename=CVDS_Jam_Video_Synthesizer_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："

[Files]
Source: "..\..\dist\CVDS_Jam_Video_Synthesizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppChineseName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppChineseName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppChineseName}"; Flags: nowait postinstall skipifsilent
