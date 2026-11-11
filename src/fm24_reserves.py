"""List ACA reserves outside the three ACA lineups.

The three ACA squads come from ``fm24_lineup``. Their ACA values define a
cutoff, and every remaining player at or above it is listed:

    cutoff = 0.9 * P20(ACA of the ACA first, second, and third squads)

Players already selected into an ACA squad are excluded; APA squad players can
still appear. The list is sorted by ACA, highest first.

Run:

    python src/fm24_reserves.py

It runs once and prints the reserve list to the console. The game must be
running with a save loaded.
"""

from __future__ import annotations

import math

from fm24_config import GrowthSettings, load_config, load_growth_settings
from fm24_lineup import build_lineups, format_lineups, prepare_players
from fm24_memory import Memory
from fm24_players import Player, all_players
from fm24_transfers import with_transfers

# ACA reserve cutoff: 90% of the 20th percentile ACA of the three ACA squads.
RESERVE_PERCENTILE = 0.20
RESERVE_RATIO = 0.90


def percentile(values: list[int], fraction: float) -> float:
    """Return the linearly interpolated percentile of the given values."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def aca_reserves(
    players: list[Player],
    lineups: list[tuple[str, list[tuple[str, Player]]]],
) -> tuple[str, list[tuple[str, Player]]] | None:
    """Return players outside the ACA squads whose ACA meets the reserve cutoff.

    The cutoff is ``RESERVE_RATIO`` times the ACA at ``RESERVE_PERCENTILE`` of
    the players selected into the ACA first, second, and third squads.
    """
    aca_squads = [
        lineup
        for label, lineup in lineups
        if label.startswith("ACA ") and "Reserves" not in label
    ]
    values = [player["aca"] for lineup in aca_squads for _, player in lineup]
    if not values:
        return None

    cutoff = percentile(values, RESERVE_PERCENTILE) * RESERVE_RATIO
    selected = {player["address"] for lineup in aca_squads for _, player in lineup}
    reserves = [
        player
        for player in players
        if player["address"] not in selected and player["aca"] >= cutoff
    ]
    reserves.sort(key=lambda player: (-player["aca"], str(player["name"])))
    label = (
        f"ACA Reserves (>= {RESERVE_RATIO:.0%} of "
        f"{RESERVE_PERCENTILE:.0%} percentile = {cutoff:.1f})"
    )
    return label, [("-", player) for player in reserves]


def find_reserves(
    players: list[Player], settings: GrowthSettings
) -> tuple[str, list[tuple[str, Player]]] | None:
    """Build the ACA lineups and return the reserve list for the same players."""
    enriched = prepare_players(players, settings)
    lineups = build_lineups(enriched, settings)
    return aca_reserves(enriched, lineups)


def main() -> int:
    """Print the ACA reserves once."""
    config = load_config()
    settings = load_growth_settings()
    try:
        with Memory.open(config) as memory:
            players = with_transfers(memory, all_players(memory))
        reserves = find_reserves(players, settings)
        if reserves is not None:
            print(format_lineups([reserves]))
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
