"""Unit tests for the sell list."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_config import CapRule, GrowthSettings  # noqa: E402
from fm24_lineup import DEPTH, SLOTS  # noqa: E402
from fm24_sell import find_sell, sell_candidates, sell_label  # noqa: E402

SETTINGS = GrowthSettings(2, 23, CapRule(18, 0.7, 22, 0.9))


def player(
    address: int,
    ca: int,
    pa: int,
    positions: list[str],
    age: float | None = 20.0,
    loans: str = "",
) -> dict[str, object]:
    """Return a player dict with the fields the sell filter reads."""
    return {
        "address": address,
        "team_uid": 1,
        "name": f"Player {address}",
        "ca": ca,
        "pa": pa,
        "age": age,
        "positions": positions,
        "loan": loans,
        "aca": ca,
        "apa": pa,
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


class SellCandidatesTest(unittest.TestCase):
    def test_keeps_players_outside_the_lineups_older_than_max_age(self) -> None:
        players = [
            player(1, 150, 160, ["ST"], age=30.0),
            player(2, 140, 150, ["ST"], age=23.0),
            player(3, 130, 140, ["ST"], age=31.0),
            player(4, 120, 130, ["ST"], age=None),
        ]
        lineups = [("ACA First XI", [("ST", players[2])])]

        candidates = sell_candidates(players, lineups, 23)

        self.assertEqual([p["address"] for _, p in candidates], [1])

    def test_sorts_by_aca_highest_first(self) -> None:
        players = [
            player(1, 100, 120, ["ST"], age=30.0),
            player(2, 140, 150, ["ST"], age=30.0),
            player(3, 120, 130, ["ST"], age=30.0),
        ]

        candidates = sell_candidates(players, [], 23)

        self.assertEqual([p["address"] for _, p in candidates], [2, 3, 1])

    def test_slots_are_blank(self) -> None:
        candidates = sell_candidates([player(1, 100, 120, ["ST"], age=30.0)], [], 23)

        self.assertEqual(candidates[0][0], "-")

    def test_label_contains_the_age_limit(self) -> None:
        self.assertEqual(sell_label(23), "Sell (not in ACA/APA lineups, age > 23)")


class FindSellTest(unittest.TestCase):
    def test_excludes_every_selected_player(self) -> None:
        players = deep_squad()
        players.append(player(100, 50, 60, ["ST"], age=30.0))

        label, candidates = find_sell(players, SETTINGS)

        self.assertEqual(label, sell_label(23))
        self.assertEqual([p["address"] for _, p in candidates], [100])

    def test_returns_nothing_when_everyone_is_young(self) -> None:
        _, candidates = find_sell(deep_squad(), SETTINGS)

        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
