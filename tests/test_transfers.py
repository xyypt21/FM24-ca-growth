"""Unit tests for agreed future transfers (no game process needed)."""

from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_transfers import (  # noqa: E402
    AGREED_TRANSFER_STATUS,
    Transfer,
    future_transfers,
    read_incoming,
    with_transfers,
)

BASE = 0x140000000
MANAGER = 0x20000000
VECTOR_BEGIN = 0x30000000
TEAM = 0x60000000
OTHER_TEAM = 0x61000000
ROSTER_PLAYER = 0x70000000
PERSON = 0x50000000
RECORD_START = PERSON - 0x278
PLAYER_TAG = 0x45A4E958
PERSON_TAG = 0x45A4EE78
STAFF_PERSON_TAG = 0x45C7ECB8
RECORD_READ = 0x3D8
TODAY = datetime.date(2025, 4, 1)
FUTURE = (2025 << 16) | 200  # 2025-07-19
PAST = (2025 << 16) | 60  # 2025-03-01

CONFIG = {
    "future_transfer": {
        "manager_rva": 0x1000,
        "vector_begin": 0x20,
        "vector_end": 0x28,
        "person": 0x30,
        "dest_team": 0x38,
        "src_team": 0x48,
        "date": 0x74,
        "status": 0x7B,
    },
    "player": {
        "ca": 0x200,
        "pa": 0x202,
        "record_read": RECORD_READ,
        "layouts": {PLAYER_TAG: 0x278},
        "person_layouts": {PERSON_TAG: 0x278, STAFF_PERSON_TAG: 0x368},
        "positions": {"GK": 0x208, "ST": 0x214},
    },
    "person": {
        "birth_doy": 0x44,
        "birth_year": 0x46,
        "first_name": 0x58,
        "last_name": 0x60,
        "short_name": 0x68,
    },
    "team": {"uid_off": 0x0C},
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
    ):
        self.base = BASE
        self.config = CONFIG
        self.blobs = blobs or {}
        self.u32 = u32 or {}

    def read_bytes(self, address: int, size: int) -> bytes | None:
        raw = self.blobs.get(address)
        if raw is None or len(raw) < size:
            return None
        return raw[:size]

    def read_ptr(self, address: int) -> int | None:
        return self.u32.get(address)

    def read_u32(self, address: int) -> int | None:
        return self.u32.get(address)

    def is_valid_ptr(self, address: int) -> bool:
        limits = self.config["read"]
        return limits["min_ptr"] <= address < limits["max_ptr"]


def game_string(text: str) -> bytes:
    """Return a [u32 length][utf-8] buffer padded to the configured name size."""
    raw = text.encode("utf-8")
    return len(raw).to_bytes(4, "little") + raw + b"\x00" * 200


def transfer_record(
    person: int,
    dest: int,
    src: int,
    when: int = FUTURE,
    status: int = AGREED_TRANSFER_STATUS,
) -> bytes:
    """Build one future transfer record."""
    record = bytearray(0x7C)
    record[0x30:0x38] = person.to_bytes(8, "little")
    record[0x38:0x40] = dest.to_bytes(8, "little")
    record[0x48:0x50] = src.to_bytes(8, "little")
    record[0x74:0x78] = when.to_bytes(4, "little")
    record[0x7B] = status
    return bytes(record)


def player_record(
    ca: int = 150,
    pa: int = 180,
    year: int = 2001,
    day_of_year: int = 91,
    short: int = 0,
) -> bytes:
    """Build one player record with a person sub-object at +0x278."""
    record = bytearray(RECORD_READ)
    record[0:4] = PLAYER_TAG.to_bytes(4, "little")
    record[0x200:0x202] = ca.to_bytes(2, "little")
    record[0x202:0x204] = pa.to_bytes(2, "little")
    record[0x208] = 20
    person = 0x278
    record[person + 0x44 : person + 0x46] = day_of_year.to_bytes(2, "little")
    record[person + 0x46 : person + 0x48] = year.to_bytes(2, "little")
    record[person + 0x68 : person + 0x70] = short.to_bytes(8, "little")
    return bytes(record)


def transfer_memory(records: list[bytes], person_tag: int = PERSON_TAG) -> FakeMemory:
    """Return memory holding the transfer manager and one array of records."""
    u32 = {
        BASE + 0x1000: MANAGER,
        MANAGER + 0x20: VECTOR_BEGIN,
        MANAGER + 0x28: VECTOR_BEGIN + 8 * len(records),
        TEAM + 0x0C: 920,
    }
    for index, _ in enumerate(records):
        u32[VECTOR_BEGIN + index * 8] = VECTOR_BEGIN + 0x100 + index * 0x200
    blobs = {
        PERSON: person_tag.to_bytes(4, "little"),
        RECORD_START: player_record(),
    }
    for index, record in enumerate(records):
        blobs[VECTOR_BEGIN + 0x100 + index * 0x200] = record
    return FakeMemory(blobs, u32)


class FutureTransfersTest(unittest.TestCase):
    def test_agreed_incoming_transfer(self) -> None:
        memory = transfer_memory([transfer_record(PERSON, TEAM, OTHER_TEAM)])

        transfers = future_transfers(memory, {TEAM}, TODAY)

        self.assertEqual(transfers, {PERSON: Transfer("in", TEAM)})

    def test_agreed_outgoing_transfer(self) -> None:
        memory = transfer_memory([transfer_record(PERSON, OTHER_TEAM, TEAM)])

        transfers = future_transfers(memory, {TEAM}, TODAY)

        self.assertEqual(transfers, {PERSON: Transfer("out", TEAM)})

    def test_other_statuses_are_ignored(self) -> None:
        for status in (0, 2, 3, 8, 15, 20):
            memory = transfer_memory(
                [transfer_record(PERSON, TEAM, OTHER_TEAM, status=status)]
            )
            with self.subTest(status=status):
                self.assertEqual(future_transfers(memory, {TEAM}, TODAY), {})

    def test_active_or_past_transfers_are_ignored(self) -> None:
        memory = transfer_memory([transfer_record(PERSON, TEAM, OTHER_TEAM, when=PAST)])

        self.assertEqual(future_transfers(memory, {TEAM}, TODAY), {})

    def test_moves_between_our_own_teams_are_ignored(self) -> None:
        memory = transfer_memory([transfer_record(PERSON, TEAM, OTHER_TEAM)])

        self.assertEqual(future_transfers(memory, {TEAM, OTHER_TEAM}, TODAY), {})

    def test_non_player_person_is_ignored(self) -> None:
        memory = transfer_memory(
            [transfer_record(PERSON, TEAM, OTHER_TEAM)],
            person_tag=0x45C7D028,
        )

        self.assertEqual(future_transfers(memory, {TEAM}, TODAY), {})

    def test_unreadable_manager_returns_empty(self) -> None:
        self.assertEqual(future_transfers(FakeMemory(), {TEAM}, TODAY), {})


class ReadIncomingTest(unittest.TestCase):
    def test_reads_the_record_before_the_person(self) -> None:
        memory = transfer_memory([])
        memory.blobs[0x4FFFF000] = game_string("New Signing")
        record = bytearray(player_record(short=0x4FFFF000))
        memory.blobs[RECORD_START] = bytes(record)

        player = read_incoming(memory, PERSON, TEAM, TODAY)

        self.assertIsNotNone(player)
        self.assertEqual(player["address"], RECORD_START)
        self.assertEqual(player["person"], PERSON)
        self.assertEqual(player["team_uid"], 920)
        self.assertEqual(player["name"], "New Signing")
        self.assertEqual(player["ca"], 150)
        self.assertEqual(player["pa"], 180)
        self.assertEqual(player["positions"], ["GK"])
        self.assertEqual(player["loan"], "")

    def test_unknown_person_tag_returns_none(self) -> None:
        memory = transfer_memory([], person_tag=0x12345678)

        self.assertIsNone(read_incoming(memory, PERSON, TEAM, TODAY))


class WithTransfersTest(unittest.TestCase):
    def test_drops_outgoing_and_appends_incoming(self) -> None:
        outgoing = {"address": ROSTER_PLAYER, "person": PERSON}
        staying = {"address": ROSTER_PLAYER + 0x1000, "person": 0x90000000}
        memory = transfer_memory(
            [
                transfer_record(PERSON, OTHER_TEAM, TEAM),  # out
                transfer_record(PERSON + 0x80, TEAM, OTHER_TEAM),  # in
            ]
        )
        memory.blobs[PERSON + 0x80] = PERSON_TAG.to_bytes(4, "little")
        incoming_start = PERSON + 0x80 - 0x278
        memory.blobs[incoming_start] = player_record()
        memory.u32[0x90000000] = 0  # prevent accidental transfer matching

        players = with_transfers(memory, [outgoing, staying], teams={TEAM}, today=TODAY)

        self.assertEqual([player["person"] for player in players][0], 0x90000000)
        self.assertEqual(players[1]["person"], PERSON + 0x80)
        self.assertEqual(players[1]["ca"], 150)

    def test_skips_incoming_players_already_in_the_roster(self) -> None:
        memory = transfer_memory([transfer_record(PERSON, TEAM, OTHER_TEAM)])
        roster = [{"address": RECORD_START, "person": PERSON}]

        players = with_transfers(memory, roster, teams={TEAM}, today=TODAY)

        self.assertEqual(players, roster)


if __name__ == "__main__":
    unittest.main()
