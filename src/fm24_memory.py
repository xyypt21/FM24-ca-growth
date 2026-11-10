"""Read-only access to FM24 process memory.

This module only opens the process and reads bytes, pointers, and u32 values.
Manager and team pointer chains live in their own modules.

Usage:

    with Memory.open(config) as memory:
        manager = manager_address(memory)
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

import pymem

Config = dict[str, Any]


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

        try:
            process = pymem.Pymem(process_name, exact_match=True)
        except pymem.exception.ProcessNotFound as error:
            raise RuntimeError(
                f"Cannot find {process_name}: start the game and load a save"
            ) from error
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

    def read_ptr_vector(self, address: int, label: str) -> list[int]:
        """Read a begin/end pointer vector; return [] when it does not exist."""
        begin = self.read_ptr(address)
        end = self.read_ptr(address + 8)
        if not begin or not end or end <= begin:
            return []

        if (end - begin) % 8:
            raise RuntimeError(
                f"{label} range is invalid (save not loaded or wrong offsets)"
            )

        raw = self.read_bytes(begin, end - begin)
        if not raw:
            raise RuntimeError(f"Failed to read {label}")
        return [int.from_bytes(raw[i : i + 8], "little") for i in range(0, len(raw), 8)]

    def is_valid_ptr(self, address: int) -> bool:
        """Return whether address falls inside the configured pointer range."""
        limits = self.config["read"]
        return limits["min_ptr"] <= address < limits["max_ptr"]
