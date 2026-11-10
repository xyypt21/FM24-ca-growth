"""Unit tests for the scipy CA/APA lineup selector."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_config import CapRule, GrowthSettings  # noqa: E402
from fm24_lineup import SLOTS, build_lineups, predict_apa  # noqa: E402

SETTINGS = GrowthSettings(2, 23, CapRule(18, 0.7, 22, 0.9))


def player(
    address: int,
    ca: int,
    pa: int,
    positions: list[str],
    age: float = 20.0,
) -> dict[str, object]:
    """Return a player dict with the fields used by the selector."""
    return {
        "address": address,
        "team_uid": 1,
        "name": f"Player {address}",
        "ca": ca,
        "pa": pa,
        "age": age,
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


def apa_candidates():
    """CA and APA disagree: young CA 150 has APA 200, older CA 199 has APA 199."""
    players = []
    address = 1
    for slot in SLOTS:
        players.append(player(address, 150, 200, [slot], age=16.0))
        address += 1
        players.append(player(address, 199, 199, [slot], age=23.0))
        address += 1
    return players


class BuildLineupsTest(unittest.TestCase):
    def test_builds_ca_and_apa_squads(self) -> None:
        lineups = build_lineups(two_candidates((200, 100), (200, 100)), SETTINGS)

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
        lineups = build_lineups(two_candidates((200, 100), (200, 100)), SETTINGS)

        self.assertTrue(all(player["ca"] == 200 for _, player in lineups[0][1]))
        self.assertTrue(all(player["ca"] == 100 for _, player in lineups[1][1]))

    def test_apa_metric_uses_projected_ca(self) -> None:
        lineups = build_lineups(apa_candidates(), SETTINGS)

        self.assertTrue(all(player["ca"] == 150 for _, player in lineups[2][1]))
        self.assertTrue(all(player["ca"] == 199 for _, player in lineups[3][1]))

    def test_raises_when_positions_cannot_be_filled(self) -> None:
        players = [player(index, 100, 120, ["MC"]) for index in range(1, 23)]
        with self.assertRaisesRegex(RuntimeError, "No eligible"):
            build_lineups(players, SETTINGS)

    def test_raises_when_there_are_too_few_players(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "at least"):
            build_lineups(two_candidates((200, 100), (200, 100))[:21], SETTINGS)


class PredictApaTest(unittest.TestCase):
    def test_projection_is_capped_by_pa(self) -> None:
        self.assertEqual(
            predict_apa(player(1, 100, 150, ["ST"], age=16.0), SETTINGS), 150
        )

    def test_projection_below_pa_is_not_capped(self) -> None:
        self.assertEqual(
            predict_apa(player(1, 100, 200, ["ST"], age=22.0), SETTINGS), 124
        )

    def test_max_age_and_older_use_current_ca(self) -> None:
        self.assertEqual(
            predict_apa(player(1, 100, 120, ["ST"], age=23.0), SETTINGS), 100
        )
        self.assertEqual(
            predict_apa(player(1, 100, 120, ["ST"], age=24.0), SETTINGS), 100
        )

    def test_unknown_age_uses_current_ca(self) -> None:
        self.assertEqual(
            predict_apa(player(1, 100, 120, ["ST"], age=None), SETTINGS), 100
        )


if __name__ == "__main__":
    unittest.main()
