"""Pick a first and second 4-3-3 lineup with scipy's assignment solver.

Modelled on ``best_eleven.py``: every player is matched to a slot they can
play, and the solver maximises the total score. CA is the primary score; PA is
the tie-break. The first 11 slots are the first XI and the next 11 are the
second XI, so one call fills both without starving the second team.

Usage:

    python src/fm24_best_eleven.py

The result is printed and written to ``output/best_eleven.csv``. The game must
be running with a save loaded.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from scipy.optimize import linear_sum_assignment

from fm24_config import Config, load_config
from fm24_lineup import SLOTS
from fm24_memory import Memory
from fm24_players import Player, all_players

OUTPUT = Path(__file__).resolve().parents[1] / "output" / "best_eleven.csv"
SQUADS = ("First XI", "Second XI")
FORBIDDEN = 10**9


def rating(player: Player) -> int:
    """Rank by CA, using PA only as the tie-break."""
    return player["ca"] * 1000 + player["pa"]


def select_two_lineups(
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


def format_squads(squads: list[list[tuple[str, Player]]]) -> str:
    """Format both lineups as plain text."""
    lines: list[str] = []
    for name, lineup in zip(SQUADS, squads, strict=True):
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


def write_squads(squads: list[list[tuple[str, Player]]], path: Path = OUTPUT) -> None:
    """Write both lineups to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Squad", "Slot", "Name", "Age", "CA", "PA", "Positions"])
        for name, lineup in zip(SQUADS, squads, strict=True):
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
    """Read the players, pick two lineups, print them, and write the CSV."""
    with Memory.open(config) as memory:
        players = all_players(memory)
    squads = select_two_lineups(players)
    print(format_squads(squads))
    write_squads(squads)
    print(f"\nWrote {OUTPUT}")
    return OUTPUT


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Pick first and second 4-3-3 lineups by CA/PA."
    )
    parser.parse_args(argv)

    try:
        run_once(load_config())
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
