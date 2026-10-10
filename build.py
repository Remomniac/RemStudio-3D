"""Baut RemStudio 3D.

Ergebnis im Hauptordner:
  RemStudio3D.exe (+ Ordner RemStudio3D_files)  – Programm direkt starten
  RemStudio3D-Setup.exe                         – Installer (benötigt Inno Setup 6.7+)

Zwischendateien landen im Temp-Ordner, nicht im Projekt.
Aufruf:  build.bat   (oder:  .venv\\Scripts\\python.exe build.py)
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "RemStudio3D"


def is_running() -> bool:
    raw = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {NAME}.exe"], capture_output=True).stdout or b""
    return f"{NAME}.exe".lower() in raw.decode("ascii", "replace").lower()


def find_iscc():
    cands = [shutil.which("ISCC")]
    for base in (os.environ.get("LOCALAPPDATA", "") + r"\Programs", os.environ.get("ProgramFiles(x86)", ""),
                 os.environ.get("ProgramFiles", "")):
        cands += glob.glob(os.path.join(base, "Inno Setup *", "ISCC.exe"))
    return next((c for c in cands if c and os.path.isfile(c)), None)


def write_version_info(version: str):
    v = tuple(int(x) for x in (version.split(".") + ["0", "0", "0"])[:4])
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v}, prodvers={v}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
                    date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'RemStudio'),
      StringStruct('FileDescription', 'RemStudio 3D'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{NAME}'),
      StringStruct('OriginalFilename', '{NAME}.exe'),
      StringStruct('ProductName', 'RemStudio 3D'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    with open(os.path.join(ROOT, "version_info.txt"), "w", encoding="utf-8") as f:
        f.write(text)


def main() -> int:
    sys.path.insert(0, ROOT)
    from remstudio import __version__
    if is_running():
        print(f"\n!! {NAME}.exe läuft noch – bitte RemStudio 3D schließen und erneut bauen.\n")
        return 1
    tmp = os.path.join(tempfile.gettempdir(), f"{NAME}-build")
    work, dist = os.path.join(tmp, "work"), os.path.join(tmp, "dist")
    write_version_info(__version__)

    print(f"== 1/3  Programm bauen (Version {__version__}) ...")
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--workpath", work,
                           "--distpath", dist, f"{NAME}.spec"], cwd=ROOT)
    app_dir = os.path.join(dist, NAME)

    print("== 2/3  Programm in den Hauptordner kopieren ...")
    target_files = os.path.join(ROOT, f"{NAME}_files")
    if os.path.isdir(target_files):
        shutil.rmtree(target_files)
    shutil.copytree(os.path.join(app_dir, f"{NAME}_files"), target_files)
    shutil.copy2(os.path.join(app_dir, f"{NAME}.exe"), os.path.join(ROOT, f"{NAME}.exe"))

    print("== 3/3  Installer bauen ...")
    iscc = find_iscc()
    if not iscc:
        print("   Inno Setup 6.7+ nicht gefunden – Installer übersprungen (https://jrsoftware.org/isinfo.php).")
    else:
        subprocess.check_call([iscc, "/Q", f"/DSourceDir={app_dir}", f"/DAppVersion={__version__}",
                               os.path.join(ROOT, "installer", f"{NAME}.iss")])
    print(f"\nFertig:\n  {os.path.join(ROOT, NAME + '.exe')}")
    if iscc:
        print(f"  {os.path.join(ROOT, NAME + '-Setup.exe')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
