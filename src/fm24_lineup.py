"""Pick a 4-3-3 starting XI from the controlled teams, using CA and PA.

The best current ability wins; PA is used as the tie-break. Positions come from
the player record, so a player is only placed in a slot they can play unless
that slot has no eligible player left. In that case the best remaining player
is used and marked with ``*``.

Run once:

    python src/fm24_lineup.py --once

Keep refreshing every 30 seconds until Ctrl+C (default):

    python src/fm24_lineup.py

The lineup is printed and written to ``output/lineup.csv``. The game must be
running with a save loaded.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

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
POSITION_MIN = 15
OUTPUT = Path(__file__).resolve().parents[1] / "output" / "lineup.csv"


def read_positions(memory: Memory, address: int) -> list[str]:
    """Return the positions this player can play (rating 15 or above)."""
    offsets: dict[str, int] = memory.config["player"].get("positions", {})
    if not offsets:
        return []

    record = memory.read_bytes(address, max(offsets.values()) + 1)
    if not record:
        return []
    return [
        position
        for position, offset in offsets.items()
        if offset < len(record) and record[offset] >= POSITION_MIN
    ]


def load_players(memory: Memory) -> list[Player]:
    """Read every unique player from the controlled teams, with positions."""
    return [
        {**player, "positions": read_positions(memory, player["address"])}
        for player in all_players(memory)
    ]


def score(player: Player) -> tuple[int, int]:
    """Rank by current ability first, then potential ability."""
    return player["ca"], player["pa"]


def select_lineup(
    players: list[Player], slots: tuple[str, ...] = SLOTS
) -> list[tuple[str, Player, bool]]:
    """Return (slot, player, exact_position) for a full lineup.

    The most constrained slot is filled first. If no remaining player can play
    a slot, the best remaining player fills it and is marked as out of position.
    """
    remaining = list(players)
    pending = list(slots)
    lineup: list[tuple[str, Player, bool]] = []

    while pending:
        slot = min(
            pending,
            key=lambda name: sum(
                1 for player in remaining if name in player["positions"]
            ),
        )
        candidates = [player for player in remaining if slot in player["positions"]]
        if candidates:
            picked = max(candidates, key=score)
            exact = True
        else:
            if not remaining:
                raise RuntimeError(f"Not enough players to fill {slot}")
            picked = max(remaining, key=score)
            exact = False

        remaining.remove(picked)
        pending.remove(slot)
        lineup.append((slot, picked, exact))

    return sorted(lineup, key=lambda item: slots.index(item[0]))


def format_lineup(lineup: list[tuple[str, Player, bool]]) -> str:
    """Format the lineup as a plain-text table."""
    lines = [f"{'Slot':<5}{'Name':<28}{'Age':>5}{'CA':>4}{'PA':>4}  Positions"]
    for slot, player, exact in lineup:
        age = player["age"]
        age_text = "-" if age is None else f"{age:.1f}"
        marker = "" if exact else "*"
        positions = "/".join(player["positions"]) or "-"
        lines.append(
            f"{slot + marker:<5}{str(player['name']):<28}{age_text:>5}"
            f"{player['ca']:>4}{player['pa']:>4}  {positions}"
        )
    return "\n".join(lines)


def write_lineup(lineup: list[tuple[str, Player, bool]], path: Path = OUTPUT) -> None:
    """Write the lineup to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Slot", "Name", "Age", "CA", "PA", "Positions", "Exact"])
        for slot, player, exact in lineup:
            age = player["age"]
            writer.writerow(
                [
                    slot,
                    player["name"],
                    "" if age is None else f"{age:.1f}",
                    player["ca"],
                    player["pa"],
                    "/".join(player["positions"]),
                    "yes" if exact else "no",
                ]
            )


def run_once(config: Config) -> Path:
    """Read the squads, pick a lineup, print it, and write the CSV."""
    with Memory.open(config) as memory:
        players = load_players(memory)
    if len(players) < len(SLOTS):
        raise RuntimeError(
            f"Only {len(players)} players found; need at least {len(SLOTS)}"
        )

    lineup = select_lineup(players)
    print(format_lineup(lineup))
    write_lineup(lineup)
    print(f"\nWrote {OUTPUT}")
    return OUTPUT


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Pick a 4-3-3 lineup from the controlled teams."
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
