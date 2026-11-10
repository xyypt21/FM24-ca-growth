"""Unit tests for monthly CA growth (no game process needed)."""

from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_ca_growth import (  # noqa: E402
    Change,
    growth_plan,
    growth_target,
    max_age,
    month_key,
    monthly_gain,
    settle_month,
)

GAIN = 2
MAX_AGE = 22

BASE = 0x140000000
CONTAINER = 0x20000000
BEGIN = 0x30000000
MANAGER = 0x40000000
PERSON = MANAGER + 0x450
CONTRACT = 0x50000000
TEAM = 0x60000000
CLUB = 0x70000000
YOUTH_TEAM = 0x80000000
PLAYER = 0x90000000
PLAYER_AT_PA = 0xA0000000
TEAM_UID = 920
YOUTH_UID = 2000069496
RECORD_READ = 0x3D8
PLAYER_TAG = 0x45A4E958
TODAY_VALUE = (2025 << 16) | 91  # 2025-04-01

CONFIG = {
    "manager": {
        "container_rva": 0x1000,
        "vector_off": 0x18,
        "person_off": 0x450,
    },
    "person": {
        "uid_off": 0x0C,
        "contract_off": 0xC8,
        "birth_doy": 0x44,
        "birth_year": 0x46,
        "first_name": 0x58,
        "last_name": 0x60,
        "short_name": 0x68,
    },
    "contract": {"team_off": 0x10},
    "team": {"uid_off": 0x0C, "club_off": 0x30, "roster_begin": 0x38},
    "club": {"teams_begin": 0x18, "linked_teams_begin": 0x30},
    "player": {
        "ca": 0x200,
        "pa": 0x202,
        "record_read": RECORD_READ,
        "layouts": {PLAYER_TAG: 0x278},
    },
    "game_date": {"rva": 0x2000},
    "read": {
        "min_ptr": 0x10000,
        "max_ptr": 0x7FF000000000,
        "name_buf": 132,
        "name_max": 120,
    },
}


class FakeMemory:
    """Minimal memory stand-in with a write log."""

    def __init__(
        self,
        blobs: dict[int, bytes],
        u32: dict[int, int],
        vectors: dict[int, list[int]],
    ):
        self.base = BASE
        self.config = CONFIG
        self.blobs = blobs
        self.u32 = u32
        self.vectors = vectors
        self.written: dict[int, int] = {}

    def read_bytes(self, address: int, size: int) -> bytes | None:
        raw = self.blobs.get(address)
        if raw is None or len(raw) < size:
            return None
        return raw[:size]

    def read_ptr(self, address: int) -> int | None:
        return self.u32.get(address)

    def read_u32(self, address: int) -> int | None:
        return self.u32.get(address)

    def read_ptr_vector(self, address: int, label: str) -> list[int]:
        return self.vectors.get(address, [])

    def is_valid_ptr(self, address: int) -> bool:
        limits = self.config["read"]
        return limits["min_ptr"] <= address < limits["max_ptr"]

    def write_u16(self, address: int, value: int) -> bool:
        self.written[address] = value
        return True


def record(ca: int, pa: int, year: int = 2003, day_of_year: int = 200) -> bytes:
    """Build a minimal player record with a type tag, CA/PA, and birth date.

    Default birth date (2003-07-19) makes the player 21.x years old on
    2025-04-01, which is at or below the default max_age of 22.
    """
    raw = bytearray(RECORD_READ)
    raw[0:4] = PLAYER_TAG.to_bytes(4, "little")
    raw[0x200:0x202] = ca.to_bytes(2, "little")
    raw[0x202:0x204] = pa.to_bytes(2, "little")
    person = 0x278
    raw[person + 0x44 : person + 0x46] = day_of_year.to_bytes(2, "little")
    raw[person + 0x46 : person + 0x48] = year.to_bytes(2, "little")
    return bytes(raw)


def memory_with_players(
    rosters: list[tuple[int, list[int]]],
) -> FakeMemory:
    """Build the manager -> club -> teams chain and the given rosters."""
    pointers = {
        BASE + 0x1000: CONTAINER,
        CONTAINER + 0x18: BEGIN,
        BEGIN: MANAGER,
        PERSON + 0xC8: CONTRACT,
        CONTRACT + 0x10: TEAM,
        TEAM + 0x30: CLUB,
    }
    u32 = dict(pointers)
    u32[TEAM + 0x0C] = TEAM_UID
    u32[YOUTH_TEAM + 0x0C] = YOUTH_UID

    vectors: dict[int, list[int]] = {}
    blobs: dict[int, bytes] = {
        BASE + 0x2000: TODAY_VALUE.to_bytes(4, "little"),
    }
    teams: list[int] = []
    for team, players in rosters:
        teams.append(team)
        vectors[team + 0x38] = players
        for address in players:
            if address not in blobs:
                blobs[address] = record(100, 150)

    vectors[CLUB + 0x18] = teams
    vectors[CLUB + 0x30] = []
    return FakeMemory(blobs, u32, vectors)


def player(
    address: int, ca: int, pa: int, name: str = "Player", age: float = 20.0
) -> dict:
    """Return a player dict in the shape used by fm24_players."""
    return {"address": address, "name": name, "ca": ca, "pa": pa, "age": age}


class GrowthTargetTest(unittest.TestCase):
    def test_adds_monthly_gain(self) -> None:
        self.assertEqual(growth_target(100, 150, GAIN), 100 + GAIN)

    def test_stops_at_pa(self) -> None:
        self.assertIsNone(growth_target(100, 101, GAIN))
        self.assertIsNone(growth_target(100, 100, GAIN))

    def test_invalid_values_are_skipped(self) -> None:
        self.assertIsNone(growth_target(0, 150, GAIN))
        self.assertIsNone(growth_target(150, 0, GAIN))
        self.assertIsNone(growth_target(150, 100, GAIN))
        self.assertIsNone(growth_target(201, 210, GAIN))

    def test_month_key_orders_months(self) -> None:
        self.assertLess(
            month_key(datetime.date(2024, 12, 31)),
            month_key(datetime.date(2025, 1, 1)),
        )

    def test_monthly_gain_comes_from_settings(self) -> None:
        self.assertEqual(monthly_gain({"monthly_gain": 2}), 2)

    def test_max_age_comes_from_settings(self) -> None:
        self.assertEqual(max_age({"max_age": 22}), 22)

    def test_max_age_defaults_to_22(self) -> None:
        self.assertEqual(max_age({}), 22)

    def test_invalid_max_age_raises(self) -> None:
        for settings in ({"max_age": -1}, {"max_age": True}, {"max_age": "22"}):
            with self.assertRaisesRegex(RuntimeError, "max_age"):
                max_age(settings)


class GrowthPlanTest(unittest.TestCase):
    def test_plans_only_players_below_pa(self) -> None:
        changes = growth_plan(
            [
                player(1, 100, 150, "Grows", 20.0),
                player(2, 100, 100, "At PA", 20.0),
                player(3, 100, 101, "Would exceed", 20.0),
                player(4, 0, 150, "Invalid", 20.0),
            ],
            GAIN,
            MAX_AGE,
        )
        self.assertEqual(
            changes,
            [Change("Grows", 1, 100, 100 + GAIN, 150)],
        )

    def test_skips_players_above_max_age(self) -> None:
        changes = growth_plan(
            [
                player(1, 100, 150, "Young", 22.0),
                player(2, 100, 150, "Older", 23.0),
                player(3, 100, 150, "Unknown", None),
            ],
            GAIN,
            MAX_AGE,
        )
        self.assertEqual(
            changes,
            [Change("Young", 1, 100, 100 + GAIN, 150)],
        )

    def test_deduplicates_the_same_record(self) -> None:
        changes = growth_plan(
            [
                player(1, 100, 150, "Same", 20.0),
                player(1, 100, 150, "Same", 20.0),
            ],
            GAIN,
            MAX_AGE,
        )
        self.assertEqual(len(changes), 1)


class SettleMonthTest(unittest.TestCase):
    def test_writes_growth_once_per_record(self) -> None:
        memory = memory_with_players(
            [
                (TEAM, [PLAYER, PLAYER_AT_PA]),
                (YOUTH_TEAM, [PLAYER]),
            ]
        )
        memory.blobs[PLAYER] = record(100, 150)
        memory.blobs[PLAYER_AT_PA] = record(150, 150)

        written = settle_month(memory, GAIN, MAX_AGE)

        self.assertEqual(len(written), 1)
        self.assertEqual(
            memory.written,
            {PLAYER + CONFIG["player"]["ca"]: 100 + GAIN},
        )

    def test_no_players_raises(self) -> None:
        memory = memory_with_players([(TEAM, [])])
        with self.assertRaisesRegex(RuntimeError, "No players"):
            settle_month(memory, GAIN, MAX_AGE)


if __name__ == "__main__":
    unittest.main()
