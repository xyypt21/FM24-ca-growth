"""Unit tests for the ACA reserve filter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_config import CapRule, GrowthSettings  # noqa: E402
from fm24_lineup import DEPTH, SLOTS  # noqa: E402
from fm24_reserves import aca_reserves, find_reserves, percentile  # noqa: E402

SETTINGS = GrowthSettings(2, 23, CapRule(18, 0.7, 22, 0.9))


def player(address: int, aca: int, ca: int = 100) -> dict[str, object]:
    """Return a player dict with the fields the reserve filter reads."""
    return {
        "address": address,
        "team_uid": 1,
        "name": f"Player {address}",
        "ca": ca,
        "pa": 200,
        "age": 20.0,
        "positions": ["ST"],
        "loan": "",
        "aca": aca,
        "apa": ca,
    }


def deep_squad() -> list[dict[str, object]]:
    """Enough players for two XIs plus a third squad at every depth target."""
    players = []
    address = 1
    for slot in SLOTS:
        for rank in range(DEPTH[slot]):
            ca = 200 - rank
            players.append(
                {
                    "address": address,
                    "team_uid": 1,
                    "name": f"Player {address}",
                    "ca": ca,
                    "pa": ca + 10,
                    "age": 20.0,
                    "positions": [slot],
                    "loan": "",
                }
            )
            address += 1
    return players


class PercentileTest(unittest.TestCase):
    def test_percentile_interpolates(self) -> None:
        self.assertEqual(percentile([100, 110], 0.2), 102.0)
        self.assertEqual(percentile([100], 0.2), 100.0)


class AcaReservesTest(unittest.TestCase):
    def test_reserves_use_cutoff_and_skip_every_aca_squad(self) -> None:
        players = [
            player(1, 100),  # in the first squad
            player(2, 110),  # in the second squad
            player(3, 120),  # in the third squad
            player(4, 90),  # below the cutoff
            player(5, 103),  # above the cutoff
            player(6, 200),  # above the cutoff
        ]
        lineups = [
            ("ACA First XI", [("ST", players[0])]),
            ("ACA Second XI", [("ST", players[1])]),
            ("ACA Third XI", [("ST", players[2])]),
        ]

        label, reserves = aca_reserves(players, lineups)

        # P20 of [100, 110, 120] is 104; 90% of it is 93.6.
        self.assertIn("93.6", label)
        self.assertEqual([player["address"] for _, player in reserves], [6, 5])

    def test_squads_are_matched_by_address(self) -> None:
        squad_player = player(1, 100)
        copied = dict(squad_player)
        lineups = [("ACA First XI", [("ST", squad_player)])]

        label, reserves = aca_reserves([copied], lineups)

        self.assertIn("90.0", label)
        self.assertEqual(reserves, [])

    def test_returns_none_without_aca_squads(self) -> None:
        self.assertIsNone(aca_reserves([player(1, 100)], [("APA First XI", [])]))

    def test_reserves_are_sorted_by_aca(self) -> None:
        players = [player(1, 100), player(2, 120), player(3, 110)]
        lineups = [("ACA First XI", [("ST", players[0])])]

        _, reserves = aca_reserves(players, lineups)

        self.assertEqual([p["aca"] for _, p in reserves], [120, 110])

    def test_find_reserves_builds_the_aca_squads(self) -> None:
        reserves = find_reserves(deep_squad(), SETTINGS)

        self.assertIsNotNone(reserves)
        label, lineup = reserves
        self.assertTrue(label.startswith("ACA Reserves"))
        acas = [entry["aca"] for _, entry in lineup]
        self.assertEqual(acas, sorted(acas, reverse=True))


if __name__ == "__main__":
    unittest.main()
