"""Bygg en selvstendig programfil på Linux eller Windows."""

import subprocess
import sys
import shutil
import tarfile
from importlib.metadata import distribution
from pathlib import Path


def copy_licenses(target):
    target.mkdir(exist_ok=True)
    for name in ("reportlab", "pypdf", "pillow", "charset-normalizer", "pyinstaller"):
        package = distribution(name)
        for file in package.files or []:
            if file.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                source = Path(package.locate_file(file))
                if source.is_file():
                    shutil.copyfile(source, target / f"{name}-{file.name}")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copyfile(python_license, target / "Python-LICENSE.txt")
    if sys.platform == "linux":
        for package in ("python3.12", "libpython3.12-stdlib", "libtcl8.6", "libtk8.6"):
            source = Path("/usr/share/doc") / package / "copyright"
            if source.exists():
                shutil.copyfile(source, target / f"{package}-copyright.txt")
    for source in (Path(sys.base_prefix) / "tcl").rglob("license.terms"):
        shutil.copyfile(source, target / f"TclTk-{source.parent.name}-license.txt")


def package_files(folder, platform):
    output = folder / "dist" / platform
    copy_licenses(output / "licenses")
    shutil.copyfile(folder / "README.md", output / "README.md")
    shortcut = "Lag-snarvei.bat" if platform == "windows" else "Lag-snarvei.sh"
    shutil.copyfile(folder / shortcut, output / shortcut)
    if platform == "linux":
        (output / shortcut).chmod(0o755)
    instructions = (
        "GÅRDSFAKTURA – KOM I GANG\n\n"
        "Pakk ut hele pakken til en fast mappe på PC-en. Python trengs ikke.\n"
        "Behold licenses-mappen sammen med programmet.\n\n"
    )
    if platform == "windows":
        instructions += (
            "Windows 10 eller nyere, 64-bit:\n"
            "Dobbeltklikk Gardsfaktura.exe for å starte.\n"
            "Dobbeltklikk Lag-snarvei.bat for å lage snarvei på skrivebordet.\n"
        )
    else:
        instructions += (
            "Zorin OS 18, 64-bit (Ubuntu 24.04-basert Linux):\n"
            "Start Gardsfaktura. Hvis nødvendig, tillat kjøring under\n"
            "filens Egenskaper / Rettigheter.\n"
            "For snarvei: åpne en terminal i mappen og kjør ./Lag-snarvei.sh.\n"
            "Hvis skrivebordet spør, høyreklikk snarveien og velg Tillat kjøring.\n"
        )
    instructions += (
        "\nLegg programmet i den faste mappen før du lager snarveien.\n"
        "Flytter du programmappen senere, kjør snarveifilen på nytt.\n"
        "Kunder, priser og fakturaer lagres separat i brukerens datamappe.\n"
        "Bruk Sikkerhetskopi før du flytter data til en annen PC.\n"
        "Fyll inn gårdens opplysninger i Innstillinger før første faktura.\n"
        "Se README.md for bruk, datamapper og kjente begrensninger.\n"
    )
    (output / "KOM-I-GANG.txt").write_text(instructions, encoding="utf-8-sig")
    if platform == "windows":
        archive = shutil.make_archive(str(folder / "dist" / "Gardsfaktura-Windows-x64"),
                                      "zip", root_dir=output.parent, base_dir=platform)
    else:
        archive = folder / "dist" / "Gardsfaktura-Linux-x86_64.tar.gz"
        with tarfile.open(archive, "w:gz") as package:
            package.add(output, arcname="Gardsfaktura")
    print(f"Ferdig pakke: {archive}")


def main():
    folder = Path(__file__).resolve().parent
    platform = "windows" if sys.platform == "win32" else "linux"
    if sys.platform not in ("win32", "linux"):
        raise SystemExit("Bygging støttes på Linux og Windows.")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile",
        "--windowed", "--name", "Gardsfaktura",
        "--distpath", str(folder / "dist" / platform),
        "--workpath", str(folder / "build" / platform),
        "--specpath", str(folder / "build" / platform),
        str(folder / "app.py"),
    ], cwd=folder, check=True)
    package_files(folder, platform)


if __name__ == "__main__":
    main()
