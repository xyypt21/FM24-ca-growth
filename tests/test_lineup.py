"""Unit tests for lineup selection (no game process needed)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_lineup import SLOTS, read_positions, select_lineup  # noqa: E402


class FakeMemory:
    """Minimal memory stand-in exposing one record blob."""

    def __init__(self, record: bytes):
        self.record = record
        self.config = {"player": {"positions": {"GK": 0x208, "DL": 0x20A, "ST": 0x214}}}

    def read_bytes(self, address: int, size: int) -> bytes | None:
        if len(self.record) < size:
            return None
        return self.record[:size]


def player(
    address: int,
    ca: int,
    pa: int,
    positions: list[str],
    name: str = "Player",
) -> dict[str, object]:
    """Return a player dict with the fields used by the lineup selector."""
    return {
        "address": address,
        "name": name,
        "ca": ca,
        "pa": pa,
        "age": 20.0,
        "positions": positions,
    }


def full_squad() -> list[dict[str, object]]:
    """Return one player for every slot, all with distinct CA values."""
    squad = []
    for index, slot in enumerate(SLOTS):
        squad.append(player(index + 1, 100 + index, 120 + index, [slot], slot))
    return squad


class SelectLineupTest(unittest.TestCase):
    def test_fills_every_slot_with_an_eligible_player(self) -> None:
        lineup = select_lineup(full_squad())
        self.assertEqual([slot for slot, _, _ in lineup], list(SLOTS))
        self.assertTrue(all(exact for _, _, exact in lineup))

    def test_uses_pa_as_tie_break(self) -> None:
        players = [
            player(1, 150, 160, ["GK"]),
            player(2, 150, 180, ["GK"]),
            *full_squad()[1:],
        ]
        lineup = select_lineup(players)
        self.assertEqual(lineup[0][1]["address"], 2)

    def test_falls_back_to_best_remaining_player(self) -> None:
        players = [player(index + 1, 100 + index, 150, ["MC"]) for index in range(11)]
        lineup = select_lineup(players)
        self.assertEqual(len(lineup), 11)
        self.assertTrue(all(not exact for _, _, exact in lineup))
        self.assertEqual(lineup[0][1]["address"], 11)


class ReadPositionsTest(unittest.TestCase):
    def test_reads_positions_above_threshold(self) -> None:
        record = bytearray(0x215)
        record[0x208] = 20
        record[0x214] = 14
        self.assertEqual(read_positions(FakeMemory(bytes(record)), 0), ["GK"])

    def test_missing_record_returns_empty(self) -> None:
        self.assertEqual(read_positions(FakeMemory(b""), 0), [])


if __name__ == "__main__":
    unittest.main()
