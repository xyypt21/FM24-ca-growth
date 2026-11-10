"""Unit tests for the scipy CA/APA lineup selector."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_config import CapRule, GrowthSettings  # noqa: E402
from fm24_lineup import (  # noqa: E402
    SLOTS,
    build_lineups,
    predict_aca,
    predict_apa,
)

SETTINGS = GrowthSettings(2, 23, CapRule(18, 0.7, 22, 0.9))


def player(
    address: int,
    ca: int,
    pa: int,
    positions: list[str],
    age: float = 20.0,
    loan: str = "",
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
        "loan": loan,
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


def aca_candidates():
    """ACA favours the younger player: 150 + 12 = 162, older CA is 160."""
    players = []
    address = 1
    for slot in SLOTS:
        players.append(player(address, 150, 200, [slot], age=21.5))
        address += 1
        players.append(player(address, 160, 200, [slot], age=23.0))
        address += 1
    return players


class BuildLineupsTest(unittest.TestCase):
    def test_builds_ca_aca_and_apa_squads(self) -> None:
        lineups = build_lineups(two_candidates((200, 100), (200, 100)), SETTINGS)

        self.assertEqual(len(lineups), 6)
        self.assertEqual([len(lineup) for _, lineup in lineups], [11] * 6)
        for start in (0, 2, 4):
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

        self.assertTrue(all(player["ca"] == 150 for _, player in lineups[4][1]))
        self.assertTrue(all(player["ca"] == 199 for _, player in lineups[5][1]))

    def test_aca_metric_uses_six_month_growth(self) -> None:
        lineups = build_lineups(aca_candidates(), SETTINGS)

        self.assertTrue(all(player["ca"] == 150 for _, player in lineups[2][1]))
        self.assertTrue(all(player["ca"] == 160 for _, player in lineups[3][1]))

    def test_raises_when_positions_cannot_be_filled(self) -> None:
        players = [player(index, 100, 120, ["MC"]) for index in range(1, 23)]
        with self.assertRaisesRegex(RuntimeError, "No eligible"):
            build_lineups(players, SETTINGS)

    def test_skips_loaned_players(self) -> None:
        players = two_candidates((200, 100), (200, 100))
        players[0]["loan"] = "loaned in"
        players.append(player(999, 50, 60, ["GK"]))

        lineups = build_lineups(players, SETTINGS)
        addresses = {player["address"] for _, lineup in lineups for _, player in lineup}
        self.assertNotIn(1, addresses)

    def test_raises_when_there_are_too_few_players(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "at least"):
            build_lineups(two_candidates((200, 100), (200, 100))[:21], SETTINGS)


class PredictApaTest(unittest.TestCase):
    def test_projection_is_capped_by_pa(self) -> None:
        self.assertEqual(
            predict_apa(player(1, 100, 150, ["ST"], age=16.0), SETTINGS), 150
        )

    def test_projection_is_rounded_to_an_integer(self) -> None:
        self.assertEqual(
            predict_apa(player(1, 127, 200, ["ST"], age=21.3), SETTINGS), 168
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


class PredictAcaTest(unittest.TestCase):
    def test_adds_six_months_of_growth(self) -> None:
        self.assertEqual(
            predict_aca(player(1, 100, 200, ["ST"], age=16.0), SETTINGS), 112
        )

    def test_never_drops_below_ca(self) -> None:
        self.assertEqual(
            predict_aca(player(1, 180, 200, ["ST"], age=17.0), SETTINGS), 180
        )

    def test_capped_by_apa(self) -> None:
        self.assertEqual(
            predict_aca(player(1, 100, 110, ["ST"], age=22.0), SETTINGS), 110
        )

    def test_max_age_and_older_use_current_ca(self) -> None:
        self.assertEqual(
            predict_aca(player(1, 100, 120, ["ST"], age=23.0), SETTINGS), 100
        )


if __name__ == "__main__":
    unittest.main()
