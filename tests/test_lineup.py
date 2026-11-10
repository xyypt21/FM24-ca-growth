"""Unit tests for the scipy CA/PA lineup selector."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_lineup import SLOTS, select_two_lineups  # noqa: E402


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


def two_candidates(ca_values: tuple[int, int], pa_values: tuple[int, int]):
    """Return two candidates for every slot occurrence."""
    players = []
    address = 1
    for slot in SLOTS:
        for ca, pa in zip(ca_values, pa_values, strict=True):
            players.append(player(address, ca, pa, [slot]))
            address += 1
    return players


class SelectTwoLineupsTest(unittest.TestCase):
    def test_builds_two_full_squads(self) -> None:
        lineups = select_two_lineups(two_candidates((200, 100), (200, 100)), "ca")

        self.assertEqual([len(lineup) for lineup in lineups], [11, 11])
        addresses = [player["address"] for lineup in lineups for _, player in lineup]
        self.assertEqual(len(addresses), len(set(addresses)))

    def test_ca_metric_puts_best_ca_in_first_xi(self) -> None:
        lineups = select_two_lineups(two_candidates((200, 100), (200, 100)), "ca")

        self.assertTrue(all(player["ca"] == 200 for _, player in lineups[0]))
        self.assertTrue(all(player["ca"] == 100 for _, player in lineups[1]))

    def test_pa_metric_puts_best_pa_in_first_xi(self) -> None:
        players = two_candidates((200, 100), (100, 200))
        lineups = select_two_lineups(players, "pa")

        self.assertTrue(all(player["pa"] == 200 for _, player in lineups[0]))
        self.assertTrue(all(player["pa"] == 100 for _, player in lineups[1]))

    def test_raises_when_positions_cannot_be_filled(self) -> None:
        players = [player(index, 100, 120, ["MC"]) for index in range(1, 23)]
        with self.assertRaisesRegex(RuntimeError, "No eligible"):
            select_two_lineups(players, "ca")

    def test_raises_when_there_are_too_few_players(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "at least"):
            select_two_lineups(two_candidates((200, 100), (200, 100))[:21], "ca")


if __name__ == "__main__":
    unittest.main()
