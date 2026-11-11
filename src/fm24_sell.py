"""List players to sell: outside every lineup and older than ``max_age``.

The ACA and APA three squads come from ``fm24_lineup``. A player is a sell
candidate when both are true:

    the player is in none of the ACA/APA first, second, and third squads
    the player is older than max_age (no growth left)

The list is sorted by ACA, highest first. ``max_age`` comes from
``src/config.json``, the same value used for CA growth.

Run:

    python src/fm24_sell.py

It runs once and prints the sell list to the console. The game must be running
with a save loaded.
"""

from __future__ import annotations

from fm24_config import GrowthSettings, load_config, load_growth_settings
from fm24_lineup import build_lineups, format_lineups, prepare_players
from fm24_memory import Memory
from fm24_players import Player, all_players
from fm24_transfers import with_transfers


def sell_candidates(
    players: list[Player],
    lineups: list[tuple[str, list[tuple[str, Player]]]],
    max_age: int,
) -> list[tuple[str, Player]]:
    """Return players outside every lineup who are older than ``max_age``."""
    selected = {player["address"] for _, lineup in lineups for _, player in lineup}
    candidates = [
        player
        for player in players
        if player["address"] not in selected
        and player["age"] is not None
        and player["age"] > max_age
    ]
    candidates.sort(key=lambda player: (-player["aca"], str(player["name"])))
    return [("-", player) for player in candidates]


def sell_label(max_age: int) -> str:
    """Return the section label for the sell list."""
    return f"Sell (not in ACA/APA lineups, age > {max_age})"


def find_sell(
    players: list[Player], settings: GrowthSettings
) -> tuple[str, list[tuple[str, Player]]]:
    """Build the ACA/APA lineups and return the players to sell."""
    prepared = prepare_players(players, settings)
    lineups = build_lineups(prepared, settings)
    return sell_label(settings.max_age), sell_candidates(
        prepared, lineups, settings.max_age
    )


def main() -> int:
    """Print the sell list once."""
    config = load_config()
    settings = load_growth_settings()
    try:
        with Memory.open(config) as memory:
            players = with_transfers(memory, all_players(memory))
        print(format_lineups([find_sell(players, settings)]))
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
