; Installer für RemStudio 3D (Inno Setup 6.7+)
; Wird von build.py aufgerufen:  ISCC /DSourceDir=<Programmordner> /DAppVersion=<Version> RemStudio3D.iss

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\RemStudio3D"
#endif
#define AppName "RemStudio 3D"
#define AppExe "RemStudio3D.exe"

[Setup]
AppId={{6F2B7C1E-3A94-4E5D-9B0C-8D1E2F3A4B5C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=RemStudio
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
; Installation ohne Administratorrechte für den aktuellen Benutzer (für alle Benutzer: Setup mit /ALLUSERS starten)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..
OutputBaseFilename=RemStudio3D-Setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
; Modernes, dunkles Erscheinungsbild mit RemStudio-Branding
WizardStyle=modern dark
WizardBackColor=#16171a
WizardImageBackColor=#121316
WizardImageFile=wizard_100.bmp,wizard_125.bmp,wizard_150.bmp,wizard_175.bmp,wizard_200.bmp,wizard_250.bmp
WizardSmallImageFile=wizard_small_100.bmp,wizard_small_125.bmp,wizard_small_150.bmp,wizard_small_175.bmp,wizard_small_200.bmp,wizard_small_250.bmp
; Sprache: Englisch ist vorausgewählt, Deutsch wählbar – das Programm startet dann in derselben Sprache
ShowLanguageDialog=yes
LanguageDetectionMethod=none

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[CustomMessages]
en.LaunchApp=Start RemStudio 3D now
de.LaunchApp=RemStudio 3D jetzt starten
en.DeleteData=Also delete the downloaded AI models and your RemStudio 3D settings?
de.DeleteData=Auch die heruntergeladenen KI-Modelle und deine RemStudio-3D-Einstellungen löschen?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Sprache des Installers als Programmsprache übernehmen (nur beim ersten Mal)
Root: HKCU; Subkey: "Software\RemStudio\RemStudio3D"; ValueType: string; ValueName: "language"; ValueData: "{language}"; Flags: createvalueifdoesntexist

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    if MsgBox(CustomMessage('DeleteData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DelTree(ExpandConstant('{localappdata}\RemStudio'), True, True, True);
      RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\RemStudio');
    end;
end;
