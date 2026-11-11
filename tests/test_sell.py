"""Unit tests for the sell list."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_config import CapRule, GrowthSettings  # noqa: E402
from fm24_lineup import DEPTH, SLOTS, build_lineups, prepare_players  # noqa: E402
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

        # age == max_age is now listed too; unknown age is still skipped.
        self.assertEqual([p["address"] for _, p in candidates], [1, 2])

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

    def test_keeps_young_players_with_high_aca_and_low_apa(self) -> None:
        squad_aca = player(10, 120, 160, ["ST"], age=20.0)
        squad_apa = player(11, 100, 141, ["ST"], age=20.0)
        squad_aca["aca"] = 120
        squad_aca["apa"] = 160
        squad_apa["aca"] = 100
        squad_apa["apa"] = 141
        players = [
            player(1, 121, 130, ["ST"], age=20.0),  # high ACA, low APA
            player(2, 120, 130, ["ST"], age=20.0),  # ACA equal to the floor
            player(3, 121, 141, ["ST"], age=20.0),  # APA equal to the floor
            player(4, 121, 130, ["ST"], age=23.0),  # age equal to max_age
        ]
        for entry in players:
            entry["aca"] = entry["ca"]
            entry["apa"] = entry["pa"]
        lineups = [
            ("ACA First XI", [("ST", squad_aca)]),
            ("APA First XI", [("ST", squad_apa)]),
        ]

        candidates = sell_candidates(players, lineups, 23)

        # ACA floor 120, APA floor 141; both bounds are inclusive.
        self.assertEqual([p["address"] for _, p in candidates], [1, 3, 4, 2])

    def test_label_contains_the_limits(self) -> None:
        self.assertEqual(
            sell_label(23, 120, 141),
            "Sell (outside ACA/APA lineups; age >= 23 or ACA >= 120 and APA <= 141)",
        )
        self.assertEqual(sell_label(23), "Sell (outside ACA/APA lineups; age >= 23)")


class FindSellTest(unittest.TestCase):
    def test_excludes_every_selected_player(self) -> None:
        players = deep_squad()
        players.append(player(100, 50, 60, ["ST"], age=30.0))

        label, candidates = find_sell(players, SETTINGS)

        self.assertTrue(label.startswith("Sell (outside ACA/APA lineups; age >= 23"))
        self.assertIn(100, [p["address"] for _, p in candidates])

    def test_never_lists_a_selected_player(self) -> None:
        players = deep_squad()

        lineups = build_lineups(prepare_players(players, SETTINGS), SETTINGS)
        selected = {p["address"] for _, lineup in lineups for _, p in lineup}
        _, candidates = find_sell(players, SETTINGS)

        self.assertTrue(candidates)
        self.assertFalse(selected & {p["address"] for _, p in candidates})


if __name__ == "__main__":
    unittest.main()
