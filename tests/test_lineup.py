"""Unit tests for the scipy ACA/APA lineup selector."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fm24_config import CapRule, GrowthSettings  # noqa: E402
from fm24_lineup import (  # noqa: E402
    DEPTH,
    METRICS,
    SLOTS,
    build_lineups,
    predict_aca,
    predict_apa,
    prepare_players,
    select_lineup,
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


class BuildLineupsTest(unittest.TestCase):
    def test_builds_three_squads_per_metric(self) -> None:
        lineups = build_lineups(deep_squad(), SETTINGS)

        self.assertEqual(len(lineups), len(METRICS) * 3)
        self.assertEqual([len(lineup) for _, lineup in lineups[:2]], [11, 11])
        self.assertTrue(lineups[2][1])
        self.assertFalse(any(label.startswith("ACA Reserves") for label, _ in lineups))

    def test_aca_metric_puts_best_aca_in_first_xi(self) -> None:
        lineups = build_lineups(deep_squad(), SETTINGS)

        self.assertTrue(all(player["aca"] == 200 for _, player in lineups[0][1]))
        self.assertTrue(all(player["aca"] == 199 for _, player in lineups[1][1]))

    def test_third_squad_reaches_depth(self) -> None:
        lineups = build_lineups(deep_squad(), SETTINGS)
        selected = lineups[0][1] + lineups[1][1] + lineups[2][1]

        covered = {slot: 0 for slot in DEPTH}
        for _, player in selected:
            for position in player["positions"]:
                if position in covered:
                    covered[position] += 1
        self.assertTrue(all(covered[slot] >= DEPTH[slot] for slot in DEPTH))

    def test_select_lineup_uses_the_metric_field(self) -> None:
        players = []
        address = 1
        for slot in SLOTS:
            first = player(address, 200, 200, [slot])
            first.update(aca=100, apa=300)
            second = player(address + 1, 100, 150, [slot])
            second.update(aca=200, apa=100)
            players += [first, second]
            address += 2

        self.assertTrue(
            all(player["ca"] == 200 for _, player in select_lineup(players, "ca"))
        )
        self.assertTrue(
            all(player["aca"] == 200 for _, player in select_lineup(players, "aca"))
        )
        self.assertTrue(
            all(player["apa"] == 300 for _, player in select_lineup(players, "apa"))
        )

    def test_raises_when_positions_cannot_be_filled(self) -> None:
        players = [player(index, 100, 120, ["MC"]) for index in range(1, 23)]
        with self.assertRaisesRegex(RuntimeError, "No eligible"):
            build_lineups(players, SETTINGS)

    def test_skips_loaned_players(self) -> None:
        players = deep_squad()
        players[0]["loan"] = "loaned in"
        players.append(player(9999, 50, 60, ["GK"]))

        lineups = build_lineups(players, SETTINGS)
        addresses = {player["address"] for _, lineup in lineups for _, player in lineup}
        self.assertNotIn(1, addresses)

    def test_raises_when_there_are_too_few_players(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "at least"):
            build_lineups(deep_squad()[:10], SETTINGS)


def mixed_squad() -> list[dict[str, object]]:
    """Return two available players and one loaned player."""
    loaned = player(3, 100, 120, ["ST"])
    loaned["loan"] = "loaned out"
    return [player(1, 100, 120, ["ST"]), player(2, 110, 130, ["ST"]), loaned]


class PreparePlayersTest(unittest.TestCase):
    def test_adds_metrics_and_drops_loaned_players(self) -> None:
        prepared = prepare_players(mixed_squad(), SETTINGS)

        self.assertEqual([p["address"] for p in prepared], [1, 2])
        self.assertEqual(prepared[0]["aca"], predict_aca(prepared[0], SETTINGS))
        self.assertEqual(prepared[0]["apa"], predict_apa(prepared[0], SETTINGS))


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
