#define AppName "Loqta"
#define AppVersion "1.0.0"
#define SourceDir "dist\Loqta"

[Setup]
AppId={{D9886EE3-3C45-44AE-BFEF-EF4A382306F8}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Loqta
DefaultGroupName=Loqta
OutputDir=release
OutputBaseFilename=Loqta-Setup-1.0.0
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
WizardStyle=modern
UninstallDisplayName=Loqta | YouTube Local

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Loqta"; Filename: "{app}\Loqta.exe"
Name: "{autodesktop}\Loqta"; Filename: "{app}\Loqta.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "إنشاء اختصار على سطح المكتب"; GroupDescription: "اختصارات إضافية:"

[Run]
Filename: "{app}\Loqta.exe"; Description: "تشغيل لقطة"; Flags: nowait postinstall skipifsilent
