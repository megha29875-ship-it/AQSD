
"""
AQSD Professional
Module: Windows Launcher Installer
Version: 1.0

Creates:
- AQSD_Launcher.bat inside the AQSD project
- A desktop shortcut named "AQSD Professional"
- An optional Start Menu shortcut

Run:
    python install_launcher.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent

LAUNCHER_SCRIPT = SCRIPTS_DIR / "aqsd_launcher.py"
BATCH_FILE = BASE_DIR / "AQSD_Launcher.bat"

USER_HOME = Path.home()
DESKTOP = USER_HOME / "Desktop"
START_MENU = (
    USER_HOME
    / "AppData"
    / "Roaming"
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
)

DESKTOP_SHORTCUT = DESKTOP / "AQSD Professional.lnk"
START_MENU_SHORTCUT = START_MENU / "AQSD Professional.lnk"


# ============================================================
# HELPERS
# ============================================================

def find_pythonw() -> Path:
    """
    Return pythonw.exe when available.
    Falls back to python.exe.
    """

    python_exe = Path(sys.executable)
    pythonw = python_exe.with_name("pythonw.exe")

    if pythonw.exists():
        return pythonw

    return python_exe


def create_batch_file() -> None:
    if not LAUNCHER_SCRIPT.exists():
        raise FileNotFoundError(
            f"AQSD launcher not found:\n{LAUNCHER_SCRIPT}"
        )

    pythonw = find_pythonw()

    batch_content = (
        "@echo off\n"
        f'cd /d "{SCRIPTS_DIR}"\n'
        f'start "" "{pythonw}" "{LAUNCHER_SCRIPT}"\n'
        "exit\n"
    )

    BATCH_FILE.write_text(
        batch_content,
        encoding="utf-8",
    )


def create_shortcut(
    shortcut_path: Path,
    target_path: Path,
    working_directory: Path,
    description: str,
) -> None:
    """
    Create a Windows .lnk shortcut using PowerShell.
    """

    shortcut_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    escaped_shortcut = str(shortcut_path).replace("'", "''")
    escaped_target = str(target_path).replace("'", "''")
    escaped_working = str(working_directory).replace("'", "''")
    escaped_description = description.replace("'", "''")

    powershell = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$shortcut = $shell.CreateShortcut('{escaped_shortcut}'); "
        f"$shortcut.TargetPath = '{escaped_target}'; "
        f"$shortcut.WorkingDirectory = '{escaped_working}'; "
        f"$shortcut.Description = '{escaped_description}'; "
        "$shortcut.WindowStyle = 1; "
        "$shortcut.Save();"
    )

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            powershell,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "Could not create shortcut.\n"
            + completed.stderr.strip()
        )


def verify_installation() -> None:
    required = [
        BATCH_FILE,
        DESKTOP_SHORTCUT,
    ]

    missing = [
        path
        for path in required
        if not path.exists()
    ]

    if missing:
        raise RuntimeError(
            "Installation verification failed:\n"
            + "\n".join(str(path) for path in missing)
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    if os.name != "nt":
        raise RuntimeError(
            "This installer is intended for Windows."
        )

    print("\nAQSD WINDOWS LAUNCHER INSTALLER")
    print("=" * 68)

    create_batch_file()

    create_shortcut(
        DESKTOP_SHORTCUT,
        BATCH_FILE,
        BASE_DIR,
        "Open AQSD Professional Trading Workstation",
    )

    create_shortcut(
        START_MENU_SHORTCUT,
        BATCH_FILE,
        BASE_DIR,
        "Open AQSD Professional Trading Workstation",
    )

    verify_installation()

    print("Installation completed successfully.")
    print(f"Batch file: {BATCH_FILE}")
    print(f"Desktop shortcut: {DESKTOP_SHORTCUT}")
    print(f"Start Menu shortcut: {START_MENU_SHORTCUT}")
    print("=" * 68)
    print("You can now double-click 'AQSD Professional' on your desktop.")


if __name__ == "__main__":
    main()
