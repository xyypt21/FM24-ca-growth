"""Unit tests for reading players from a team UID (no game process needed)."""

from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_players import (  # noqa: E402
    all_players,
    calc_age,
    game_date,
    parse_game_date,
    players_in_team,
    read_string,
)

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
OTHER_RECORD = 0xA0000000
CURRENT_ENTRY = 0xC0000000
OWNER_ENTRY = 0xD0000000
CURRENT_CLUB = 0xE0000000
OWNER_CLUB = 0xF0000000
PLAYER_CONTRACT = 0x110000000
SHORT_STRING = 0xB0000000
FIRST_STRING = 0xB0001000
LAST_STRING = 0xB0002000
TEAM_UID = 920
YOUTH_UID = 2000069496
PLAYER_TAG = 0x45A4E958
PLAYER_STAFF_TAG = 0x45C7E798
RECORD_READ = 0x3D8
LAYOUTS = {PLAYER_TAG: 0x278, PLAYER_STAFF_TAG: 0x368}
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
    "club": {
        "teams_begin": 0x18,
        "linked_teams_begin": 0x30,
        "uid_off": 0x0C,
        "entry_struct": 0x30,
    },
    "player": {
        "ca": 0x200,
        "pa": 0x202,
        "record_read": RECORD_READ,
        "layouts": LAYOUTS,
        "contract_layouts": {PLAYER_TAG: 0x340, PLAYER_STAFF_TAG: 0x430},
        "current_club": 0x130,
        "contract_club": 0x10,
        "positions": {"GK": 0x208, "ST": 0x214},
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
    """Minimal memory stand-in that returns bytes and pointers by address."""

    def __init__(
        self,
        blobs: dict[int, bytes] | None = None,
        u32: dict[int, int] | None = None,
        vectors: dict[int, list[int]] | None = None,
    ):
        self.base = BASE
        self.config = CONFIG
        self.blobs = blobs or {}
        self.u32 = u32 or {}
        self.vectors = vectors or {}

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


def game_string(text: str) -> bytes:
    """Return a [u32 length][utf-8] buffer padded to the configured name size."""
    raw = text.encode("utf-8")
    return len(raw).to_bytes(4, "little") + raw + b"\x00" * 200


def make_record(
    ca: int,
    pa: int,
    tag: int = PLAYER_TAG,
    year: int = 2001,
    day_of_year: int = 91,
    short: int = 0,
    first: int = 0,
    last: int = 0,
) -> bytes:
    """Build a player record with CA/PA, birth date, and name pointers."""
    record = bytearray(RECORD_READ)
    record[0:4] = tag.to_bytes(4, "little")
    record[0x200:0x202] = ca.to_bytes(2, "little")
    record[0x202:0x204] = pa.to_bytes(2, "little")
    person = LAYOUTS[tag]
    record[person + 0x44 : person + 0x46] = day_of_year.to_bytes(2, "little")
    record[person + 0x46 : person + 0x48] = year.to_bytes(2, "little")
    record[person + 0x58 : person + 0x60] = first.to_bytes(8, "little")
    record[person + 0x60 : person + 0x68] = last.to_bytes(8, "little")
    record[person + 0x68 : person + 0x70] = short.to_bytes(8, "little")
    return bytes(record)


def team_memory(
    own_teams: list[int],
    u32: dict[int, int] | None = None,
    vectors: dict[int, list[int]] | None = None,
    blobs: dict[int, bytes] | None = None,
) -> FakeMemory:
    """Return a FakeMemory with the full manager -> club -> team chain."""
    pointers = {
        BASE + 0x1000: CONTAINER,
        CONTAINER + 0x18: BEGIN,
        BEGIN: MANAGER,
        PERSON + 0xC8: CONTRACT,
        CONTRACT + 0x10: TEAM,
        TEAM + 0x30: CLUB,
    }
    vectors = vectors or {}
    vectors.setdefault(CLUB + 0x18, own_teams)
    vectors.setdefault(CLUB + 0x30, [])
    u32 = u32 or {}
    u32.setdefault(TEAM + 0x0C, TEAM_UID)
    u32.setdefault(YOUTH_TEAM + 0x0C, YOUTH_UID)
    u32.update(pointers)
    blobs = blobs or {}
    blobs.setdefault(BASE + 0x2000, TODAY_VALUE.to_bytes(4, "little"))
    return FakeMemory(blobs, u32, vectors)


def loan_memory(current_uid: int, owner_uid: int) -> FakeMemory:
    """Return a memory with one player's current and owner clubs wired up."""
    record = bytearray(make_record(100, 150))
    record[0x130:0x138] = CURRENT_ENTRY.to_bytes(8, "little")
    record[0x340:0x348] = PLAYER_CONTRACT.to_bytes(8, "little")
    return team_memory(
        [TEAM],
        u32={
            PLAYER_CONTRACT + 0x10: OWNER_ENTRY,
            CURRENT_ENTRY + 0x30: CURRENT_CLUB,
            OWNER_ENTRY + 0x30: OWNER_CLUB,
            CURRENT_CLUB + 0x0C: current_uid,
            OWNER_CLUB + 0x0C: owner_uid,
        },
        vectors={TEAM + 0x38: [PLAYER]},
        blobs={PLAYER: bytes(record)},
    )


class PlayerReadTest(unittest.TestCase):
    def test_reads_name_ca_pa_and_age(self) -> None:
        memory = team_memory(
            [TEAM],
            vectors={TEAM + 0x38: [PLAYER, OTHER_RECORD]},
            blobs={
                PLAYER: make_record(136, 150, year=2001, day_of_year=91),
                OTHER_RECORD: b"\x00" * RECORD_READ,
            },
        )
        players = players_in_team(memory, TEAM)
        self.assertEqual(len(players), 1)
        self.assertEqual(
            players[0],
            {
                "address": PLAYER,
                "team_uid": TEAM_UID,
                "name": "(unknown)",
                "ca": 136,
                "pa": 150,
                "age": 24.0,
                "positions": [],
                "loan": "",
            },
        )

    def test_prefers_short_name(self) -> None:
        memory = team_memory(
            [TEAM],
            vectors={TEAM + 0x38: [PLAYER]},
            blobs={
                PLAYER: make_record(
                    100,
                    120,
                    short=SHORT_STRING,
                    first=FIRST_STRING,
                    last=LAST_STRING,
                ),
                SHORT_STRING: game_string("Leo Greiml"),
                FIRST_STRING: game_string("Leo"),
                LAST_STRING: game_string("Greiml"),
            },
        )
        self.assertEqual(players_in_team(memory, TEAM)[0]["name"], "Leo Greiml")

    def test_falls_back_to_first_and_last_name(self) -> None:
        memory = team_memory(
            [TEAM],
            vectors={TEAM + 0x38: [PLAYER]},
            blobs={
                PLAYER: make_record(
                    100,
                    120,
                    first=FIRST_STRING,
                    last=LAST_STRING,
                ),
                FIRST_STRING: game_string("Assan Ouédraogo"),
                LAST_STRING: game_string("Ouédraogo"),
            },
        )
        self.assertEqual(players_in_team(memory, TEAM)[0]["name"], "Assan Ouédraogo")

    def test_staff_tag_uses_its_own_person_offset(self) -> None:
        memory = team_memory(
            [TEAM],
            vectors={TEAM + 0x38: [PLAYER]},
            blobs={
                PLAYER: make_record(90, 110, tag=PLAYER_STAFF_TAG, year=1990),
            },
        )
        players = players_in_team(memory, TEAM)
        self.assertEqual(players[0]["ca"], 90)
        self.assertEqual(players[0]["pa"], 110)

    def test_reads_positions_from_the_record(self) -> None:
        record = bytearray(make_record(136, 150))
        record[0x208] = 20
        record[0x214] = 14
        memory = team_memory(
            [TEAM],
            vectors={TEAM + 0x38: [PLAYER]},
            blobs={PLAYER: bytes(record)},
        )
        players = players_in_team(memory, TEAM)
        self.assertEqual(players[0]["positions"], ["GK"])

    def test_detects_loaned_in_player(self) -> None:
        memory = loan_memory(TEAM_UID, 999)
        players = players_in_team(memory, TEAM, our_uids={TEAM_UID})
        self.assertEqual(players[0]["loan"], "loaned in")

    def test_detects_loaned_out_player(self) -> None:
        memory = loan_memory(999, TEAM_UID)
        players = players_in_team(memory, TEAM, our_uids={TEAM_UID})
        self.assertEqual(players[0]["loan"], "loaned out")

    def test_owned_player_is_not_on_loan(self) -> None:
        memory = loan_memory(TEAM_UID, TEAM_UID)
        players = players_in_team(memory, TEAM, our_uids={TEAM_UID})
        self.assertEqual(players[0]["loan"], "")

    def test_groups_players_by_controlled_team_uid(self) -> None:
        memory = team_memory(
            [TEAM, YOUTH_TEAM],
            vectors={
                TEAM + 0x38: [PLAYER],
                YOUTH_TEAM + 0x38: [OTHER_RECORD],
            },
            blobs={
                PLAYER: make_record(136, 150),
                OTHER_RECORD: make_record(90, 110),
            },
        )
        players = all_players(memory)
        self.assertEqual(
            [player["team_uid"] for player in players], [TEAM_UID, YOUTH_UID]
        )
        self.assertEqual([player["ca"] for player in players], [136, 90])


class DateTest(unittest.TestCase):
    def test_parse_game_date(self) -> None:
        self.assertEqual(parse_game_date(TODAY_VALUE), datetime.date(2025, 4, 1))

    def test_parse_invalid_date_returns_none(self) -> None:
        self.assertIsNone(parse_game_date(0))

    def test_game_date_reads_from_the_exe_rva(self) -> None:
        memory = team_memory([TEAM])
        self.assertEqual(game_date(memory), datetime.date(2025, 4, 1))

    def test_age_truncates_to_one_decimal(self) -> None:
        today = datetime.date(2025, 4, 1)
        self.assertEqual(calc_age(2006, 275, today), 18.4)
        self.assertEqual(calc_age(2001, 91, today), 24.0)

    def test_invalid_birth_returns_none(self) -> None:
        self.assertIsNone(calc_age(0, 0, datetime.date(2025, 4, 1)))


class StringTest(unittest.TestCase):
    def test_missing_string_returns_none(self) -> None:
        memory = team_memory([TEAM])
        self.assertIsNone(read_string(memory, 0))
        self.assertIsNone(read_string(memory, SHORT_STRING))

    def test_rejects_implausible_length(self) -> None:
        memory = team_memory([TEAM], blobs={SHORT_STRING: b"\xff\xff\xff\xff"})
        self.assertIsNone(read_string(memory, SHORT_STRING))


if __name__ == "__main__":
    unittest.main()
