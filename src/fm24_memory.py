"""Read-only access to the FM24 process memory and entity pointer chains.

Object pointer chains (manager and managed team) live here because both
commands share them.

Usage:

    config = load_config()
    with Memory.open(config) as memory:
        uid = manager_uid(memory)
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

import pymem

from fm24_config import Config, load_config


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

    def is_valid_ptr(self, address: int) -> bool:
        """Return whether address falls inside the configured pointer range."""
        limits = self.config["read"]
        return limits["min_ptr"] <= address < limits["max_ptr"]


def manager_address(memory: Memory) -> int:
    """Follow the pointer chain and return the human manager record address."""
    manager_cfg = memory.config["manager"]

    container = memory.read_ptr(memory.base + manager_cfg["container_rva"])
    if not container:
        raise RuntimeError(
            "Failed to read the manager container: save not loaded or wrong offsets"
        )

    # container + vector_off is the array begin; begin[0] is the manager
    # (the array contains only the human manager).
    begin = memory.read_ptr(container + manager_cfg["vector_off"])
    if not begin:
        raise RuntimeError("Failed to read the human manager array")

    manager = memory.read_ptr(begin)
    if manager is None or not memory.is_valid_ptr(manager):
        raise RuntimeError("The human manager pointer is invalid")
    return manager


def manager_uid(memory: Memory) -> int:
    """Return the human manager's UID."""
    manager = manager_address(memory)
    person = manager + memory.config["manager"]["person_off"]
    uid = memory.read_u32(person + memory.config["person"]["uid_off"])
    if not uid:
        raise RuntimeError("Failed to read the manager UID")
    return uid


def user_team(memory: Memory) -> int:
    """Follow the contract chain and return the human manager's team address."""
    manager = manager_address(memory)
    person = manager + memory.config["manager"]["person_off"]
    contract = memory.read_ptr(person + memory.config["person"]["contract_off"])
    if not contract or not memory.is_valid_ptr(contract):
        raise RuntimeError("No team belongs to the human manager (are you unemployed?)")

    team = memory.read_ptr(contract + memory.config["contract"]["team_off"])
    if not team or not memory.is_valid_ptr(team):
        raise RuntimeError("No team belongs to the human manager (are you unemployed?)")
    return team


def team_uid(memory: Memory) -> int:
    """Return the UID of the team controlled by the human manager."""
    team = user_team(memory)
    uid = memory.read_u32(team + memory.config["team"]["uid_off"])
    if not uid:
        raise RuntimeError("Failed to read the team UID")
    return uid


def read_manager_uid(config: Config | None = None) -> int:
    """Open the game process and read the manager UID."""
    if config is None:
        config = load_config()
    with Memory.open(config) as memory:
        return manager_uid(memory)


def read_team_uid(config: Config | None = None) -> int:
    """Open the game process and read the managed team UID."""
    if config is None:
        config = load_config()
    with Memory.open(config) as memory:
        return team_uid(memory)
