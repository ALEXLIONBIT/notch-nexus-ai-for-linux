; Installer di NEXUS per Windows (Inno Setup 6). La versione arriva da build.py: /DAppVersion=x.y.z
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F2B7C1E-9A51-4E0B-8D2E-4E58C0A1D3E5}
AppName=NEXUS
AppVersion={#AppVersion}
AppVerName=NEXUS {#AppVersion}
AppPublisher=ALEXLIONBIT
AppPublisherURL=https://github.com/ALEXLIONBIT/notch-nexus-ai-for-linux
DefaultDirName={localappdata}\Programs\NEXUS
DefaultGroupName=NEXUS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=NEXUS-Setup-{#AppVersion}
SetupIconFile=nexus.ico
UninstallDisplayIcon={app}\NEXUS.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
MinVersion=10.0.17763

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Icona sul desktop"; GroupDescription: "Collegamenti:"
Name: "autostart"; Description: "Avvia NEXUS quando accendi il PC"; GroupDescription: "Avvio:"

[Files]
Source: "dist\NEXUS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; via le librerie della versione precedente (evita miscugli tra versioni)
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\NEXUS"; Filename: "{app}\NEXUS.exe"
Name: "{group}\Disinstalla NEXUS"; Filename: "{uninstallexe}"
Name: "{autodesktop}\NEXUS"; Filename: "{app}\NEXUS.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "NEXUS"; ValueData: """{app}\NEXUS.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\NEXUS.exe"; Description: "Avvia NEXUS"; Flags: nowait postinstall skipifsilent
; aggiornamento automatico (installer in silenzio): riapre NEXUS da solo
Filename: "{app}\NEXUS.exe"; Flags: nowait; Check: WizardSilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /im NEXUS.exe /f"; Flags: runhidden; RunOnceId: "KillNexus"
