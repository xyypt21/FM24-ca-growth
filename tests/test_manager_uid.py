"""Unit tests for the manager UID pointer chain (no game process needed)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_memory import manager_address, manager_uid, team_uid  # noqa: E402

BASE = 0x140000000
CONTAINER = 0x20000000
BEGIN = 0x30000000
MANAGER = 0x40000000
PERSON = MANAGER + 0x450
CONTRACT = 0x50000000
TEAM = 0x60000000
UID = 2002076260
TEAM_UID = 920

CONFIG = {
    "manager": {
        "container_rva": 0x1000,
        "vector_off": 0x18,
        "person_off": 0x450,
    },
    "person": {"uid_off": 0x0C, "contract_off": 0xC8},
    "contract": {"team_off": 0x10},
    "team": {"uid_off": 0x0C},
    "read": {"min_ptr": 0x10000, "max_ptr": 0x7FF000000000},
}


class FakeMemory:
    """Minimal memory stand-in that returns values by address."""

    def __init__(self, values: dict[int, int], u32: dict[int, int] | None = None):
        self.base = BASE
        self.config = CONFIG
        self.values = values
        self.u32 = u32 or {}

    def read_ptr(self, address: int) -> int | None:
        return self.values.get(address)

    def read_u32(self, address: int) -> int | None:
        return self.u32.get(address)

    def is_valid_ptr(self, address: int) -> bool:
        limits = self.config["read"]
        return limits["min_ptr"] <= address < limits["max_ptr"]


class ManagerAddressTest(unittest.TestCase):
    def test_follows_the_pointer_chain(self) -> None:
        memory = FakeMemory(
            {
                BASE + 0x1000: CONTAINER,
                CONTAINER + 0x18: BEGIN,
                BEGIN: MANAGER,
            }
        )
        self.assertEqual(manager_address(memory), MANAGER)

    def test_missing_container_raises(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "manager container"):
            manager_address(FakeMemory({}))

    def test_missing_vector_raises(self) -> None:
        memory = FakeMemory({BASE + 0x1000: CONTAINER})
        with self.assertRaisesRegex(RuntimeError, "manager array"):
            manager_address(memory)

    def test_invalid_manager_pointer_raises(self) -> None:
        memory = FakeMemory(
            {
                BASE + 0x1000: CONTAINER,
                CONTAINER + 0x18: BEGIN,
                BEGIN: 0x10,
            }
        )
        with self.assertRaisesRegex(RuntimeError, "pointer is invalid"):
            manager_address(memory)


class ManagerUidTest(unittest.TestCase):
    def test_reads_uid_from_person(self) -> None:
        memory = FakeMemory(
            {
                BASE + 0x1000: CONTAINER,
                CONTAINER + 0x18: BEGIN,
                BEGIN: MANAGER,
            },
            {PERSON + 0x0C: UID},
        )
        self.assertEqual(manager_uid(memory), UID)

    def test_zero_uid_raises(self) -> None:
        memory = FakeMemory(
            {
                BASE + 0x1000: CONTAINER,
                CONTAINER + 0x18: BEGIN,
                BEGIN: MANAGER,
            },
            {PERSON + 0x0C: 0},
        )
        with self.assertRaisesRegex(RuntimeError, "manager UID"):
            manager_uid(memory)


def manager_memory(
    values: dict[int, int] | None = None,
    u32: dict[int, int] | None = None,
) -> FakeMemory:
    """Return a FakeMemory with the manager chain already in place."""
    pointers = {
        BASE + 0x1000: CONTAINER,
        CONTAINER + 0x18: BEGIN,
        BEGIN: MANAGER,
    }
    pointers.update(values or {})
    return FakeMemory(pointers, u32)


class TeamUidTest(unittest.TestCase):
    def test_follows_the_contract_chain(self) -> None:
        memory = manager_memory(
            {
                PERSON + 0xC8: CONTRACT,
                CONTRACT + 0x10: TEAM,
            },
            {TEAM + 0x0C: TEAM_UID},
        )
        self.assertEqual(team_uid(memory), TEAM_UID)

    def test_missing_contract_raises(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "No team belongs"):
            team_uid(manager_memory())

    def test_invalid_contract_raises(self) -> None:
        memory = manager_memory({PERSON + 0xC8: 0x10})
        with self.assertRaisesRegex(RuntimeError, "No team belongs"):
            team_uid(memory)

    def test_missing_team_raises(self) -> None:
        memory = manager_memory({PERSON + 0xC8: CONTRACT})
        with self.assertRaisesRegex(RuntimeError, "No team belongs"):
            team_uid(memory)

    def test_zero_team_uid_raises(self) -> None:
        memory = manager_memory(
            {
                PERSON + 0xC8: CONTRACT,
                CONTRACT + 0x10: TEAM,
            },
            {TEAM + 0x0C: 0},
        )
        with self.assertRaisesRegex(RuntimeError, "team UID"):
            team_uid(memory)


if __name__ == "__main__":
    unittest.main()
