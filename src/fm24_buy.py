"""List the positions to buy, based on the weakest APA squad players.

The APA first, second, and third squads come from ``fm24_lineup``. The baseline
is the bottom 20% of APA across those squads: sort every squad player's APA and
take ``values[int(len(values) * 0.2)]``. A player below the baseline is weak.

Each weak player adds to the slot they were picked for:

    score += squad_weight * (baseline - player APA)

The first squad weighs 3, the second 2, and the third 1. A lower APA gives a
larger gap, so a weak starter costs more than a weak third-squad player. The
positions are sorted by score, highest first; positions with no weak player are
left out.

Run:

    python src/fm24_buy.py

It runs once and prints the buy list to the console. The game must be running
with a save loaded.
"""

from __future__ import annotations

from fm24_config import GrowthSettings, load_config, load_growth_settings
from fm24_lineup import SLOTS, build_lineups, prepare_players
from fm24_memory import Memory
from fm24_players import Player, all_players
from fm24_transfers import with_transfers

BUY_PERCENTILE = 0.2
SQUAD_WEIGHTS = (3, 2, 1)


def apa_squads(
    lineups: list[tuple[str, list[tuple[str, Player]]]],
) -> list[list[tuple[str, Player]]]:
    """Return the APA first, second, and third squads, in that order."""
    return [lineup for label, lineup in lineups if label.startswith("APA ")]


def apa_baseline(squads: list[list[tuple[str, Player]]]) -> int | None:
    """Return the bottom-20% APA value across the APA squads."""
    values = sorted(player["apa"] for lineup in squads for _, player in lineup)
    if not values:
        return None
    return values[int(len(values) * BUY_PERCENTILE)]


def position_scores(
    squads: list[list[tuple[str, Player]]], baseline: int | None
) -> list[tuple[str, int, int]]:
    """Return ``(slot, weak count, score)`` for positions below the baseline.

    Only players with APA below the baseline are weak. Only slots with a
    positive score are returned, sorted by score highest first and then by the
    formation slot order.
    """
    if baseline is None:
        return []

    counts = {slot: 0 for slot in SLOTS}
    scores = {slot: 0 for slot in SLOTS}
    for index, lineup in enumerate(squads):
        weight = SQUAD_WEIGHTS[index] if index < len(SQUAD_WEIGHTS) else 0
        for slot, player in lineup:
            if player["apa"] >= baseline:
                continue
            counts[slot] += 1
            scores[slot] += weight * (baseline - player["apa"])

    order = {slot: index for index, slot in enumerate(dict.fromkeys(SLOTS))}
    return sorted(
        (
            (slot, counts[slot], scores[slot])
            for slot in dict.fromkeys(SLOTS)
            if scores[slot] > 0
        ),
        key=lambda row: (-row[2], order[row[0]]),
    )


def buy_label(baseline: int | None) -> str:
    """Return the section label with the APA baseline."""
    value = "-" if baseline is None else str(baseline)
    return f"Buy (APA bottom 20% = {value})"


def find_buy(
    players: list[Player], settings: GrowthSettings
) -> tuple[str, list[tuple[str, int, int]]]:
    """Build the APA squads and return the positions that need a purchase."""
    prepared = prepare_players(players, settings)
    lineups = build_lineups(prepared, settings)
    squads = apa_squads(lineups)
    baseline = apa_baseline(squads)
    return buy_label(baseline), position_scores(squads, baseline)


def format_buy(label: str, rows: list[tuple[str, int, int]]) -> str:
    """Format the buy list as plain text."""
    lines = [label, f"{'Slot':<5}{'Score':>6}{'Weak':>6}"]
    if rows:
        lines.extend(f"{slot:<5}{score:>6}{count:>6}" for slot, count, score in rows)
    else:
        lines.append("(no weak positions)")
    return "\n".join(lines)


def main() -> int:
    """Print the buy list once."""
    config = load_config()
    settings = load_growth_settings()
    try:
        with Memory.open(config) as memory:
            players = with_transfers(memory, all_players(memory))
        print(format_buy(*find_buy(players, settings)))
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
