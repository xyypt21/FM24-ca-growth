"""Unit tests for the scipy first/second lineup selector."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_lineup import SLOTS, rating, select_lineups  # noqa: E402


def player(
    address: int,
    ca: int,
    pa: int,
    positions: list[str],
) -> dict[str, object]:
    """Return a player dict with the fields used by the selector."""
    return {
        "address": address,
        "team_uid": 1,
        "name": f"Player {address}",
        "ca": ca,
        "pa": pa,
        "age": 20.0,
        "positions": positions,
    }


def full_squad() -> list[dict[str, object]]:
    """Two candidates for every slot occurrence."""
    players = []
    address = 1
    for slot in SLOTS:
        for ca in (200, 100):
            players.append(player(address, ca, ca + 10, [slot]))
            address += 1
    return players


class SelectLineupsTest(unittest.TestCase):
    def test_builds_two_full_squads(self) -> None:
        lineups = select_lineups(full_squad())

        self.assertEqual([len(lineup) for lineup in lineups], [11, 11])
        addresses = [player["address"] for lineup in lineups for _, player in lineup]
        self.assertEqual(len(addresses), len(set(addresses)))

    def test_best_players_go_to_the_first_xi(self) -> None:
        lineups = select_lineups(full_squad())

        self.assertTrue(all(player["ca"] == 200 for _, player in lineups[0]))
        self.assertTrue(all(player["ca"] == 100 for _, player in lineups[1]))

    def test_raises_when_positions_cannot_be_filled(self) -> None:
        players = [player(index, 100, 120, ["MC"]) for index in range(1, 23)]
        with self.assertRaisesRegex(RuntimeError, "No eligible"):
            select_lineups(players)

    def test_raises_when_there_are_too_few_players(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "at least"):
            select_lineups(full_squad()[:21])


class RatingTest(unittest.TestCase):
    def test_pa_breaks_ca_ties(self) -> None:
        self.assertGreater(
            rating(player(1, 150, 180, ["ST"])),
            rating(player(2, 150, 160, ["ST"])),
        )
        self.assertGreater(
            rating(player(1, 151, 151, ["ST"])),
            rating(player(2, 150, 200, ["ST"])),
        )


if __name__ == "__main__":
    unittest.main()
