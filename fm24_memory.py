"""Read-only access to the FM24 process memory.

This layer only opens the process and reads bytes, pointers, and u32 values.
Object pointer chains live in their own modules, for example manager_uid.py.

Usage:

    config = load_config()
    with Memory.open(config) as memory:
        uid = manager_uid(memory)
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

import psutil
import pymem

Config = dict[str, Any]


def find_pid(process_name: str) -> int | None:
    """Return the PID matching process_name (case-insensitive), or None."""
    wanted = process_name.lower()
    for process in psutil.process_iter(["name"]):
        name = process.info["name"]
        if name and name.lower() == wanted:
            return process.pid
    return None


class Memory:
    """A live connection to the FM24 process and the offsets in use."""

    def __init__(self, process: pymem.Pymem, config: Config) -> None:
        self.process = process
        self.config = config
        self.base = self._exe_base()

    @classmethod
    @contextlib.contextmanager
    def open(cls, config: Config) -> Iterator[Memory]:
        """Open the game process; raise RuntimeError if it cannot be opened."""
        process_name = config["process_name"]
        pid = find_pid(process_name)
        if pid is None:
            raise RuntimeError(
                f"Cannot find {process_name}: start the game and load a save"
            )

        try:
            process = pymem.Pymem(pid)
        except Exception as error:
            raise RuntimeError(
                f"Cannot open the process: {error} "
                "(if the game runs as administrator, run this tool as administrator)"
            ) from error

        try:
            yield cls(process, config)
        finally:
            process.close_process()

    def _exe_base(self) -> int:
        """Return the fm.exe base address; every RVA is relative to it."""
        for module in self.process.list_modules():
            if module.name.lower().endswith(".exe"):
                return int(module.lpBaseOfDll)
        raise RuntimeError("Cannot find the fm.exe module")

    def read_bytes(self, address: int, size: int) -> bytes | None:
        """Read memory; return None when the address is invalid or unreadable.

        Only two pymem failures are expected: ReadProcessMemory failing
        (MemoryReadError) and a closed process handle (ProcessError). Any other
        exception is a bug in this code and should not be swallowed.
        """
        try:
            return self.process.read_bytes(address, size)
        except (pymem.exception.MemoryReadError, pymem.exception.ProcessError):
            return None

    def read_ptr(self, address: int) -> int | None:
        """Read one 8-byte pointer (x64 little-endian)."""
        raw = self.read_bytes(address, 8)
        return int.from_bytes(raw, "little") if raw else None

    def read_u32(self, address: int) -> int | None:
        """Read one 4-byte unsigned integer (x64 little-endian)."""
        raw = self.read_bytes(address, 4)
        return int.from_bytes(raw, "little") if raw else None

    def is_valid_ptr(self, address: int) -> bool:
        """Return whether address falls inside the configured pointer range."""
        limits = self.config["read"]
        return limits["min_ptr"] <= address < limits["max_ptr"]
