"""Pick first and second 4-3-3 lineups with scipy's assignment solver.

Every player is matched to a slot they can play, and the solver maximises the
total score. CA is the primary score; PA is the tie-break. The first 11 slots
are the first XI and the next 11 are the second XI, so one call fills both
without starving the second team.

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
SQUADS = ("First XI", "Second XI")
FORBIDDEN = 10**9
OUTPUT = Path(__file__).resolve().parents[1] / "output" / "lineup.csv"


def rating(player: Player) -> int:
    """Rank by CA, using PA only as the tie-break."""
    return player["ca"] * 1000 + player["pa"]


def select_lineups(
    players: list[Player], slots: tuple[str, ...] = SLOTS
) -> list[list[tuple[str, Player]]]:
    """Return first and second XI as [(slot, player), ...]."""
    width = len(slots)
    if len(players) < 2 * width:
        raise RuntimeError(
            f"Only {len(players)} players found; need at least {2 * width}"
        )

    costs: list[list[int]] = []
    for player in players:
        positions = player["positions"]
        row = [-rating(player) if slot in positions else FORBIDDEN for slot in slots]
        costs.append(row + row)

    player_rows, slot_columns = linear_sum_assignment(costs)
    by_slot: dict[str, list[Player]] = {}
    for player_row, slot_column in zip(player_rows, slot_columns, strict=True):
        if costs[player_row][slot_column] >= FORBIDDEN:
            slot = slots[slot_column % width]
            raise RuntimeError(f"No eligible player left for {slot}")
        slot = slots[slot_column % width]
        by_slot.setdefault(slot, []).append(players[player_row])

    lineups: list[list[tuple[str, Player] | None]] = [[None] * width for _ in range(2)]
    for slot, group in by_slot.items():
        group.sort(key=rating, reverse=True)
        indices = [index for index, name in enumerate(slots) if name == slot]
        for offset, index in enumerate(indices):
            lineups[0][index] = (slot, group[offset])
            lineups[1][index] = (slot, group[len(indices) + offset])

    return [[entry for entry in lineup if entry is not None] for lineup in lineups]


def format_lineups(lineups: list[list[tuple[str, Player]]]) -> str:
    """Format both lineups as plain text."""
    lines: list[str] = []
    for name, lineup in zip(SQUADS, lineups, strict=True):
        lines.append(name)
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


def write_lineups(lineups: list[list[tuple[str, Player]]], path: Path = OUTPUT) -> None:
    """Write both lineups to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Squad", "Slot", "Name", "Age", "CA", "PA", "Positions"])
        for name, lineup in zip(SQUADS, lineups, strict=True):
            for slot, player in lineup:
                age = player["age"]
                writer.writerow(
                    [
                        name,
                        slot,
                        player["name"],
                        "" if age is None else f"{age:.1f}",
                        player["ca"],
                        player["pa"],
                        "/".join(player["positions"]),
                    ]
                )


def run_once(config: Config) -> Path:
    """Read the squads, pick two lineups, print them, and write the CSV."""
    with Memory.open(config) as memory:
        players = all_players(memory)
    lineups = select_lineups(players)
    print(format_lineups(lineups))
    write_lineups(lineups)
    print(f"\nWrote {OUTPUT}")
    return OUTPUT


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Pick first and second 4-3-3 lineups by CA/PA."
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
