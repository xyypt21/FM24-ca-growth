"""Unit tests for the scipy CA/PA lineup selector."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_lineup import SLOTS, build_lineups  # noqa: E402


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


class BuildLineupsTest(unittest.TestCase):
    def test_builds_ca_and_pa_squads(self) -> None:
        lineups = build_lineups(two_candidates((200, 100), (200, 100)))

        self.assertEqual(len(lineups), 4)
        self.assertEqual([len(lineup) for _, lineup in lineups], [11] * 4)
        for start in (0, 2):
            addresses = [
                player["address"]
                for _, lineup in lineups[start : start + 2]
                for _, player in lineup
            ]
            self.assertEqual(len(addresses), len(set(addresses)))

    def test_ca_metric_puts_best_ca_in_first_xi(self) -> None:
        lineups = build_lineups(two_candidates((200, 100), (200, 100)))

        self.assertTrue(all(player["ca"] == 200 for _, player in lineups[0][1]))
        self.assertTrue(all(player["ca"] == 100 for _, player in lineups[1][1]))

    def test_pa_metric_puts_best_pa_in_first_xi(self) -> None:
        lineups = build_lineups(two_candidates((200, 100), (100, 200)))

        self.assertTrue(all(player["pa"] == 200 for _, player in lineups[2][1]))
        self.assertTrue(all(player["pa"] == 100 for _, player in lineups[3][1]))

    def test_raises_when_positions_cannot_be_filled(self) -> None:
        players = [player(index, 100, 120, ["MC"]) for index in range(1, 23)]
        with self.assertRaisesRegex(RuntimeError, "No eligible"):
            build_lineups(players)

    def test_raises_when_there_are_too_few_players(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "at least"):
            build_lineups(two_candidates((200, 100), (200, 100))[:21])


if __name__ == "__main__":
    unittest.main()
