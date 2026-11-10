"""Build the Windows GUI exe and package it with the config files.

Usage:

    python scripts/build_exe.py

Requires PyInstaller 6.22 or newer, which can bundle Tcl/Tk 9 data from
python.org Windows builds of Python 3.15.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

EXCLUDES = (
    "unittest",
    "doctest",
    "pydoc",
    "pydoc_data",
    "test",
    "ensurepip",
    "pip",
    "setuptools",
    "pkg_resources",
    "email",
    "http",
    "urllib",
    "xml",
    "multiprocessing",
    "concurrent",
    "asyncio",
    "sqlite3",
    "decimal",
    "ssl",
    "_ssl",
    "hashlib",
    "_hashlib",
    "secrets",
    "bz2",
    "lzma",
    "_bz2",
    "_lzma",
)


def build(name: str) -> None:
    """Run PyInstaller, copy the config files, and create the release zip."""
    arguments = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--collect-submodules",
        "pymem",
    ]
    for module in EXCLUDES:
        arguments += ["--exclude-module", module]

    arguments += [
        "--name",
        name,
        str(ROOT / "src" / "fm24_ca_growth_gui.pyw"),
    ]
    subprocess.run(arguments, cwd=ROOT, check=True)

    for config_file in ("offsets.toml", "config.json"):
        shutil.copy2(ROOT / "src" / config_file, DIST / config_file)

    archive = DIST / f"{name}-windows.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as file:
        for entry in (
            DIST / f"{name}.exe",
            DIST / "offsets.toml",
            DIST / "config.json",
        ):
            file.write(entry, entry.name)

    print(f"Built {DIST / (name + '.exe')} and {archive}")


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Build the Windows GUI exe.")
    parser.add_argument("--name", default="FM24CAGrowth", help="exe and zip name")
    args = parser.parse_args(argv)
    build(args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
