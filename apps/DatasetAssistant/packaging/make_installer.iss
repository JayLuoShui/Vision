#ifndef AppVersion
#define AppVersion "1.0.0"
#endif
#ifndef SourceDir
#define SourceDir "..\dist\DatasetAssistant"
#endif
#ifndef OutputDir
#define OutputDir "..\dist_installer"
#endif

[Setup]
AppId={{4703AC8F-9B5A-48C8-A750-55C650DA1000}
AppName=数据集制作助手 V1.0
AppVersion={#AppVersion}
AppPublisher=CVDS
DefaultDirName={autopf}\CVDS\DatasetAssistant
DefaultGroupName=CVDS
OutputDir={#OutputDir}
OutputBaseFilename=DatasetAssistant_Setup_{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\DatasetAssistant.exe
WizardStyle=modern

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\数据集制作助手 V1.0"; Filename: "{app}\DatasetAssistant.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\数据集制作助手 V1.0"; Filename: "{app}\DatasetAssistant.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\DatasetAssistant.exe"; Description: "启动 数据集制作助手 V1.0"; Flags: nowait postinstall skipifsilent
