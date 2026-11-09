"""
PRISM - Standalone Executable Builder (PyInstaller)
Author: an1zy (https://github.com/an1zy)
"""

import sys
import os
from pathlib import Path
import PyInstaller.__main__

BASE_DIR = Path(__file__).resolve().parent

def build():
    print("[*] Starting PRISM Windows x64 build...")
    
    # Separator for --add-data (';' on Windows, ':' on Unix)
    sep = ";" if sys.platform == "win32" else ":"
    templates_arg = f"templates{sep}templates"

    args = [
        str(BASE_DIR / "prism.py"),
        "--onefile",
        "--name", "prism_windows_x64",
        "--clean",
        "--add-data", str(BASE_DIR / templates_arg),
        "--hidden-import", "rich",
        "--hidden-import", "requests",
        "--hidden-import", "discord",
        "--hidden-import", "aiohttp",
        "--hidden-import", "core",
        "--hidden-import", "core.bot_engines",
        "--hidden-import", "core.bot_runner",
        "--hidden-import", "core.embed",
        "--hidden-import", "core.storage",
        "--hidden-import", "core.i18n",
        "--hidden-import", "core.themes",
        "--hidden-import", "core.tray",
        "--hidden-import", "pystray",
        "--hidden-import", "PIL",
        "--hidden-import", "ui.terminal",
    ]

    PyInstaller.__main__.run(args)
    print("\n[OK] Build finished successfully! Binary is located in dist/prism_windows_x64.exe")

if __name__ == "__main__":
    build()
