"""Build the Windows GUI exe and package it with the config files.

Usage:

    python scripts/build_exe.py

Works with normal CPython and with Python builds that ship Tcl 9 inside zip
files (for example Python 3.14+), where PyInstaller needs the Tcl/Tk data
added explicitly.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import tkinter
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


def tcl_zip_data(temp_dir: Path) -> list[str]:
    """Return --add-data arguments for Python builds using Tcl 9 zip files."""
    tcl_library = tkinter.Tcl().eval("info library")
    if not tcl_library.startswith("//zipfs:"):
        return []

    tcl_root = Path(sys.executable).resolve().parent / "tcl"
    zip_tcl = next(iter(tcl_root.glob("libtcl*.zip")), None)
    zip_tk = next(iter(tcl_root.glob("libtk*.zip")), None)
    if zip_tcl is None or zip_tk is None:
        raise RuntimeError(f"Cannot find libtcl*.zip or libtk*.zip in {tcl_root}")

    for archive in (zip_tcl, zip_tk):
        with zipfile.ZipFile(archive) as file:
            file.extractall(temp_dir)

    return [
        f"{temp_dir / 'tcl_library'};_tcl_data",
        f"{temp_dir / 'tk_library'};_tk_data",
    ]


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

    with tempfile.TemporaryDirectory() as directory:
        for entry in tcl_zip_data(Path(directory)):
            arguments += ["--add-data", entry]
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
