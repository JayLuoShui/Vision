#define MyAppName "DWSBatchModelValidator"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "CVDS"
#define MyRoot ".."

[Setup]
AppId={{A8809209-1F8E-4C12-B5F0-D79C8BD8BD58}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CVDS\DWSBatchModelValidator
DefaultGroupName=CVDS\DWSBatchModelValidator
OutputDir=..\dist_installer
OutputBaseFilename=DWSBatchModelValidator_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Files]
Source: "..\dist\DWSBatchModelValidator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\DWS 批量模型检测验证工具"; Filename: "{app}\DWSBatchModelValidator.exe"
Name: "{autodesktop}\DWS 批量模型检测验证工具"; Filename: "{app}\DWSBatchModelValidator.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："

[Run]
Filename: "{app}\DWSBatchModelValidator.exe"; Description: "启动 DWS 批量模型检测验证工具"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
