"""Pick CA and PA first/second 4-3-3 lineups with scipy's assignment solver.

For each metric (CA and PA), scipy assigns players to the 11 formation slots.
The best XI is selected first, then the same solver picks the second XI from the
remaining players.

Run:

    python src/fm24_lineup.py

It refreshes every ``INTERVAL`` seconds; Ctrl+C stops it. The lineups are
printed to the console. The game must be running with a save loaded.
"""

from __future__ import annotations

import time

from scipy.optimize import linear_sum_assignment

from fm24_config import load_config
from fm24_memory import Memory
from fm24_players import Player, all_players

# Seconds between refreshes while the script is running.
INTERVAL = 30

# 4-3-3: one goalkeeper, four defenders, three midfielders, three forwards.
SLOTS = (
    "GK",
    "DL",
    "DC",
    "DC",
    "DR",
    "DM",
    "DM",
    "AML",
    "AMC",
    "AMR",
    "ST",
)
METRICS = ("ca", "pa")
FORBIDDEN = 10**9


def select_lineup(
    players: list[Player], metric: str, slots: tuple[str, ...] = SLOTS
) -> list[tuple[str, Player]]:
    """Return the best XI for one metric (``ca`` or ``pa``)."""
    if len(players) < len(slots):
        raise RuntimeError(
            f"Only {len(players)} players found; need at least {len(slots)}"
        )

    costs = [
        [
            -player[metric] if slot in player["positions"] else FORBIDDEN
            for slot in slots
        ]
        for player in players
    ]
    player_rows, slot_columns = linear_sum_assignment(costs)

    lineup: list[tuple[str, Player]] = []
    for player_row, slot_column in zip(player_rows, slot_columns, strict=True):
        if costs[player_row][slot_column] >= FORBIDDEN:
            raise RuntimeError(f"No eligible player left for {slots[slot_column]}")
        lineup.append((slots[slot_column], players[player_row]))
    return sorted(lineup, key=lambda entry: slots.index(entry[0]))


def build_lineups(players: list[Player]) -> list[tuple[str, list[tuple[str, Player]]]]:
    """Return CA first/second and PA first/second, in display order."""
    lineups: list[tuple[str, list[tuple[str, Player]]]] = []
    for metric in METRICS:
        first = select_lineup(players, metric)
        used = {id(player) for _, player in first}
        remaining = [player for player in players if id(player) not in used]
        try:
            second = select_lineup(remaining, metric)
        except RuntimeError as error:
            raise RuntimeError(f"{metric.upper()} Second XI: {error}") from error

        lineups.append((f"{metric.upper()} First XI", first))
        lineups.append((f"{metric.upper()} Second XI", second))
    return lineups


def format_lineups(
    lineups: list[tuple[str, list[tuple[str, Player]]]],
) -> str:
    """Format every lineup as plain text."""
    lines: list[str] = []
    for label, lineup in lineups:
        lines.append(label)
        lines.append(f"{'Slot':<5}{'Name':<28}{'Age':>5}{'CA':>4}{'PA':>4}  Positions")
        for slot, player in lineup:
            age = player["age"]
            age_text = "-" if age is None else f"{age:.1f}"
            positions = "/".join(player["positions"]) or "-"
            lines.append(
                f"{slot:<5}{str(player['name']):<28}{age_text:>5}"
                f"{player['ca']:>4}{player['pa']:>4}  {positions}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> int:
    """Refresh the lineups until interrupted."""
    config = load_config()
    try:
        while True:
            try:
                with Memory.open(config) as memory:
                    players = all_players(memory)
                print(format_lineups(build_lineups(players)))
            except RuntimeError as error:
                print(f"Error: {error}")
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("Stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
