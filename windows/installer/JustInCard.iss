#ifndef AppVersion
  #define AppVersion "1.3.6"
#endif
#ifndef SourceDir
  #define SourceDir "..\release\JustInCard-Windows-Portable-" + AppVersion
#endif
#ifndef OutputDir
  #define OutputDir "..\release"
#endif

#define AppName "Just InCard"
#define AppPublisher "leenation"
#define AppExeName "JustInCard.exe"

[Setup]
AppId={{DDF9014B-6D5D-4A9F-9AE1-38C8BDE285D2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\JustInCard
DefaultGroupName=Just InCard
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=JustInCard-Windows-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\app_icon.ico
UninstallDisplayIcon={app}\JustInCard.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "portable.flag"

[Icons]
Name: "{autoprograms}\Just InCard"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Just InCard"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzliche Verknüpfungen:"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Just InCard starten"; Flags: nowait postinstall skipifsilent
