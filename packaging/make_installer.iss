#ifndef AppVersion
#define AppVersion "1.0.0"
#endif

#ifndef SourceDir
#define SourceDir "..\dist\CVDS_Package_Flow_Detector"
#endif

#ifndef OutputDir
#define OutputDir "..\dist_installer"
#endif

[Setup]
AppId={{0A8F0EF8-4C4B-4B19-9AA0-1F0E5A100000}
AppName=CVDS包裹流量检测工具
AppVersion={#AppVersion}
AppPublisher=CVDS
DefaultDirName={autopf}\CVDS\CVDS包裹流量检测工具
DefaultGroupName=CVDS
OutputDir={#OutputDir}
OutputBaseFilename=CVDS_Package_Flow_Detector_Setup_{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
UninstallDisplayIcon={app}\CVDS_Cpp_Detector.exe
WizardStyle=modern

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: unchecked

[Files]
; runtime\cvds_detector_worker.exe is included from SourceDir recursively.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CVDS包裹流量检测工具"; Filename: "{app}\CVDS_Cpp_Detector.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\CVDS包裹流量检测工具"; Filename: "{app}\CVDS_Cpp_Detector.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\CVDS_Cpp_Detector.exe"; Description: "启动 CVDS包裹流量检测工具"; Flags: nowait postinstall skipifsilent

[Code]
function IsVCRuntimeInstalled(): Boolean;
begin
  Result :=
    RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') or
    FileExists(ExpandConstant('{sys}\vcruntime140.dll'));
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsVCRuntimeInstalled() then
    MsgBox('未检测到 VC++ 运行库。安装包已包含常见运行 DLL；如果程序无法启动，请安装 Microsoft Visual C++ Redistributable 2015-2022 x64。', mbInformation, MB_OK);
end;
