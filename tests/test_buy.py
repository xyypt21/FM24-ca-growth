"""Unit tests for the buy list."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_buy import (  # noqa: E402
    apa_baseline,
    buy_label,
    find_buy,
    format_buy,
    position_scores,
)
from fm24_config import CapRule, GrowthSettings  # noqa: E402
from fm24_lineup import DEPTH, SLOTS  # noqa: E402

SETTINGS = GrowthSettings(2, 23, CapRule(18, 0.7, 22, 0.9))


def entry(apa: int) -> tuple[str, dict[str, object]]:
    """Return a lineup entry with only the APA field the buy list reads."""
    return ("ST", {"apa": apa})


def player(
    address: int,
    ca: int,
    pa: int,
    positions: list[str],
    age: float | None = 20.0,
    loans: str = "",
) -> dict[str, object]:
    """Return a player dict with the fields the lineup builder reads."""
    return {
        "address": address,
        "team_uid": 1,
        "name": f"Player {address}",
        "ca": ca,
        "pa": pa,
        "age": age,
        "positions": positions,
        "loan": loans,
    }


def deep_squad() -> list[dict[str, object]]:
    """Enough players for two XIs plus a third squad at every depth target."""
    players = []
    address = 1
    for slot in SLOTS:
        for rank in range(DEPTH[slot]):
            ca = 200 - rank
            players.append(player(address, ca, ca + 10, [slot]))
            address += 1
    return players


class ApaBaselineTest(unittest.TestCase):
    def test_uses_the_bottom_twenty_percent(self) -> None:
        squads = [[entry(apa) for apa in (100, 110, 120, 130, 140)]]

        # 5 players -> index int(5 * 0.2) = 1 -> 110.
        self.assertEqual(apa_baseline(squads), 110)

    def test_empty_squads_have_no_baseline(self) -> None:
        self.assertIsNone(apa_baseline([]))
        self.assertIsNone(apa_baseline([[]]))


class PositionScoresTest(unittest.TestCase):
    def test_scores_weak_players_by_squad_and_gap(self) -> None:
        squads = [
            [("ST", {"apa": 100}), ("GK", {"apa": 130})],
            [("ST", {"apa": 120}), ("DC", {"apa": 110})],
            [("ST", {"apa": 140})],
        ]

        rows = position_scores(squads, 120)

        # ST: 3 * (120 - 100) = 60, one player. The second ST is equal to the
        # baseline and is not weak. DC: 2 * (120 - 110) = 20, one player.
        self.assertEqual(rows, [("ST", 1, 60), ("DC", 1, 20)])

    def test_players_equal_to_the_baseline_are_not_weak(self) -> None:
        rows = position_scores([[("ST", {"apa": 120})]], 120)

        self.assertEqual(rows, [])

    def test_returns_nothing_without_a_baseline(self) -> None:
        self.assertEqual(position_scores([[("ST", {"apa": 100})]], None), [])

    def test_returns_nothing_when_everyone_is_above_the_baseline(self) -> None:
        self.assertEqual(position_scores([[("ST", {"apa": 130})]], 120), [])


class FormatBuyTest(unittest.TestCase):
    def test_label_shows_the_baseline(self) -> None:
        self.assertEqual(buy_label(120), "Buy (APA bottom 20% = 120)")
        self.assertEqual(buy_label(None), "Buy (APA bottom 20% = -)")

    def test_rows_show_slot_score_and_weak_count(self) -> None:
        lines = format_buy("Buy", [("ST", 2, 65), ("DC", 1, 22)]).splitlines()

        self.assertEqual(lines[1], "Slot  Score  Weak")
        self.assertEqual(lines[2], "ST       65     2")
        self.assertEqual(lines[3], "DC       22     1")

    def test_empty_rows_say_so(self) -> None:
        self.assertTrue(format_buy("Buy", []).endswith("(no weak positions)"))


class FindBuyTest(unittest.TestCase):
    def test_returns_scored_positions_from_the_apa_squads(self) -> None:
        label, rows = find_buy(deep_squad(), SETTINGS)

        self.assertTrue(label.startswith("Buy (APA bottom 20% = "))
        self.assertTrue(rows)
        self.assertEqual(
            [row[2] for row in rows], sorted((row[2] for row in rows), reverse=True)
        )
        for slot, count, score in rows:
            self.assertIn(slot, SLOTS)
            self.assertGreater(count, 0)
            self.assertGreater(score, 0)


if __name__ == "__main__":
    unittest.main()
