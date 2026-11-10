"""Pick CA and PA first/second 4-3-3 lineups with scipy's assignment solver.

For each metric (CA and PA), scipy assigns players to the 11 formation slots.
The best XI is selected first, then the same solver picks the second XI from the
remaining players.

Run once:

    python src/fm24_lineup.py --once

Keep refreshing every 30 seconds until Ctrl+C (default):

    python src/fm24_lineup.py

The lineups are printed and written to ``output/lineup.csv``. The game must be
running with a save loaded.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from scipy.optimize import linear_sum_assignment

from fm24_config import Config, load_config
from fm24_memory import Memory
from fm24_players import Player, all_players

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
SQUADS = ("First XI", "Second XI")
FORBIDDEN = 10**9
OUTPUT = Path(__file__).resolve().parents[1] / "output" / "lineup.csv"


def select_lineup(
    players: list[Player], metric: str, slots: tuple[str, ...] = SLOTS
) -> list[tuple[str, Player]]:
    """Return the best XI for one metric (``ca`` or ``pa``)."""
    if len(players) < len(slots):
        raise RuntimeError(
            f"Only {len(players)} players found; need at least {len(slots)}"
        )

    costs: list[list[int]] = []
    for player in players:
        positions = player["positions"]
        costs.append(
            [-player[metric] if slot in positions else FORBIDDEN for slot in slots]
        )

    player_rows, slot_columns = linear_sum_assignment(costs)
    chosen: dict[int, tuple[str, Player]] = {}
    for player_row, slot_column in zip(player_rows, slot_columns, strict=True):
        if costs[player_row][slot_column] >= FORBIDDEN:
            raise RuntimeError(f"No eligible player left for {slots[slot_column]}")
        chosen[slot_column] = (slots[slot_column], players[player_row])

    missing = [slot for index, slot in enumerate(slots) if index not in chosen]
    if missing:
        raise RuntimeError(f"Could not fill: {', '.join(missing)}")
    return [chosen[index] for index in range(len(slots))]


def select_two_lineups(
    players: list[Player], metric: str, slots: tuple[str, ...] = SLOTS
) -> list[list[tuple[str, Player]]]:
    """Return first and second XI for one metric."""
    first = select_lineup(players, metric, slots)
    used = {id(player) for _, player in first}
    remaining = [player for player in players if id(player) not in used]
    try:
        second = select_lineup(remaining, metric, slots)
    except RuntimeError as error:
        raise RuntimeError(f"Second XI: {error}") from error
    return [first, second]


def build_lineups(players: list[Player]) -> list[tuple[str, list[tuple[str, Player]]]]:
    """Return CA first/second and PA first/second, in display order."""
    lineups: list[tuple[str, list[tuple[str, Player]]]] = []
    for metric in METRICS:
        first, second = select_two_lineups(players, metric)
        lineups.append((f"{metric.upper()} {SQUADS[0]}", first))
        lineups.append((f"{metric.upper()} {SQUADS[1]}", second))
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


def write_lineups(
    lineups: list[tuple[str, list[tuple[str, Player]]]], path: Path = OUTPUT
) -> None:
    """Write every lineup to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Squad", "Slot", "Name", "Age", "CA", "PA", "Positions"])
        for label, lineup in lineups:
            for slot, player in lineup:
                age = player["age"]
                writer.writerow(
                    [
                        label,
                        slot,
                        player["name"],
                        "" if age is None else f"{age:.1f}",
                        player["ca"],
                        player["pa"],
                        "/".join(player["positions"]),
                    ]
                )


def run_once(config: Config) -> Path:
    """Read the squads, build the four lineups, print them, and write the CSV."""
    with Memory.open(config) as memory:
        players = all_players(memory)
    lineups = build_lineups(players)
    print(format_lineups(lineups))
    write_lineups(lineups)
    print(f"\nWrote {OUTPUT}")
    return OUTPUT


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Pick CA and PA first/second 4-3-3 lineups."
    )
    parser.add_argument("--once", action="store_true", help="run once and exit")
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="seconds between refreshes when looping (default 30)",
    )
    args = parser.parse_args(argv)

    config = load_config()
    try:
        while True:
            try:
                run_once(config)
            except RuntimeError as error:
                print(f"Error: {error}")
                if args.once:
                    return 1
            if args.once:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
