"""List players to sell: outside every lineup, with no room in the squads.

The ACA and APA three squads come from ``fm24_lineup``. A player who is in none
of the six squads is a sell candidate when either is true:

    age >= max_age
        no growth left, whatever the ability
    age < max_age, ACA >= weakest ACA squad player, APA <= weakest APA squad player
        good enough to play now, but no long-term ceiling

The second rule compares a player's ACA with the lowest ACA across the three ACA
squads, and their APA with the lowest APA across the three APA squads.

Players with an unknown age are never listed. The list is sorted by ACA, highest
first. ``max_age`` comes from ``src/config.json``, the same value used for CA
growth.

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


def squad_floor(
    lineups: list[tuple[str, list[tuple[str, Player]]]], metric: str
) -> int | None:
    """Return the lowest metric value in the ACA or APA squads."""
    values = [
        player[metric]
        for label, lineup in lineups
        if label.startswith(f"{metric.upper()} ")
        for _, player in lineup
    ]
    return min(values) if values else None


def sell_candidates(
    players: list[Player],
    lineups: list[tuple[str, list[tuple[str, Player]]]],
    max_age: int,
) -> list[tuple[str, Player]]:
    """Return players outside every lineup who cannot improve the squads."""
    selected = {player["address"] for _, lineup in lineups for _, player in lineup}
    aca_floor = squad_floor(lineups, "aca")
    apa_floor = squad_floor(lineups, "apa")

    candidates = []
    for player in players:
        if player["address"] in selected:
            continue
        age = player["age"]
        if age is None:
            continue
        if age >= max_age or (
            age < max_age
            and aca_floor is not None
            and apa_floor is not None
            and player["aca"] >= aca_floor
            and player["apa"] <= apa_floor
        ):
            candidates.append(player)

    candidates.sort(key=lambda player: (-player["aca"], str(player["name"])))
    return [("-", player) for player in candidates]


def sell_label(
    max_age: int, aca_floor: int | None = None, apa_floor: int | None = None
) -> str:
    """Return the section label for the sell list."""
    label = f"Sell (outside ACA/APA lineups; age >= {max_age}"
    if aca_floor is not None and apa_floor is not None:
        label += f" or ACA >= {aca_floor} and APA <= {apa_floor}"
    return label + ")"


def find_sell(
    players: list[Player], settings: GrowthSettings
) -> tuple[str, list[tuple[str, Player]]]:
    """Build the ACA/APA lineups and return the players to sell."""
    prepared = prepare_players(players, settings)
    lineups = build_lineups(prepared, settings)
    label = sell_label(
        settings.max_age,
        squad_floor(lineups, "aca"),
        squad_floor(lineups, "apa"),
    )
    return label, sell_candidates(prepared, lineups, settings.max_age)


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
