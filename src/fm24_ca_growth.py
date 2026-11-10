"""Monthly CA growth for every player in the controlled teams.

Each in-game month change adds ``monthly_gain`` CA to every unique player in
every team controlled by the human manager. CA never grows above PA, so players
already at their potential are skipped.

This script watches the in-game date; it does not use the system clock. It
re-reads the rosters on every settlement, so CA, PA, and record addresses are
always current. It also detects save reloads: when the human manager address
changes, all previously read addresses are stale and the month cursor resets.

Usage:

    python src/fm24_ca_growth.py            # run until Ctrl+C
    python src/fm24_ca_growth.py --preview  # show the plan; write nothing

The game must be running with a save loaded. This script WRITES to game memory,
unlike the reader commands. Run it at the same privilege level as the game.
"""

from __future__ import annotations

import argparse
import datetime
import time
from collections.abc import Iterable
from dataclasses import dataclass

from fm24_config import Config, load_config, load_settings
from fm24_manager import manager_address
from fm24_memory import Memory
from fm24_players import game_date, team_players

# How often the in-game date is checked.
POLL_SECONDS = 2.0

Player = dict[str, object]


@dataclass(frozen=True, slots=True)
class Change:
    """One planned or written CA change."""

    name: str
    address: int
    ca: int
    new_ca: int
    pa: int


def month_key(date: datetime.date) -> int:
    """Compress a date into a month number for ordering."""
    return date.year * 12 + date.month


def monthly_gain(settings: dict[str, object]) -> int:
    """Return the configured positive monthly CA gain."""
    gain = settings.get("monthly_gain")
    if not isinstance(gain, int) or isinstance(gain, bool) or gain <= 0:
        raise RuntimeError("config.json must contain a positive integer monthly_gain")
    return gain


def growth_target(ca: int, pa: int, gain: int) -> int | None:
    """Return CA + gain when it stays within PA; otherwise None."""
    if not (1 <= ca <= 200 and 1 <= pa <= 200) or ca > pa:
        return None
    new_ca = ca + gain
    return new_ca if new_ca <= pa else None


def controlled_players(memory: Memory) -> list[Player]:
    """Return every player record in every controlled team."""
    return [player for _, players in team_players(memory) for player in players]


def growth_plan(players: Iterable[Player], gain: int) -> list[Change]:
    """Return the planned CA changes, deduplicated by player record address."""
    changes: list[Change] = []
    seen: set[int] = set()
    for player in players:
        address = player["address"]
        if address in seen:
            continue
        seen.add(address)

        ca = player["ca"]
        pa = player["pa"]
        new_ca = growth_target(ca, pa, gain)
        if new_ca is None:
            continue
        changes.append(
            Change(
                name=str(player["name"]),
                address=address,
                ca=ca,
                new_ca=new_ca,
                pa=pa,
            )
        )
    return changes


def settle_month(memory: Memory, gain: int) -> list[Change]:
    """Write the planned CA changes and return the ones that were verified."""
    players = controlled_players(memory)
    if not players:
        raise RuntimeError("No players found: save not loaded or wrong offsets")

    ca_off = memory.config["player"]["ca"]
    written: list[Change] = []
    for change in growth_plan(players, gain):
        if not memory.write_u16(change.address + ca_off, change.new_ca):
            print(f"Write failed: {change.name} (0x{change.address:X})")
            continue
        written.append(change)
    return written


def print_plan(today: datetime.date, changes: list[Change], gain: int) -> None:
    """Print the planned changes before or without writing them."""
    print(f"Planned CA changes for {today} (+{gain} CA):")
    for change in changes:
        print(
            f"  {change.name:<26} CA {change.ca:>3} -> {change.new_ca:>3}  "
            f"PA {change.pa:>3}"
        )
    print(f"  {len(changes)} players.")


def preview(memory: Memory, gain: int) -> int:
    """Show the current plan without writing to game memory."""
    today = game_date(memory)
    if today is None:
        raise RuntimeError("Cannot read the in-game date")
    players = controlled_players(memory)
    if not players:
        raise RuntimeError("No players found: save not loaded or wrong offsets")
    print_plan(today, growth_plan(players, gain), gain)
    return 0


def watch(memory: Memory, gain: int) -> int:
    """Settle once per new in-game month until interrupted.

    Save reload detection: the human manager object address changes every time
    the game (re)loads a save. When it changes, all previously read roster,
    team, and player addresses are stale. The settled month is intentionally
    not reset: reloading on July 4 must not re-settle a month already settled
    on July 1.
    """
    today = game_date(memory)
    if today is None:
        raise RuntimeError("Cannot read the in-game date")

    last_manager = manager_address(memory)
    last_month = month_key(today)
    if today.day == 1:
        # Started on the 1st: this month has not been paid by this run.
        last_month -= 1
        print(f"Game date {today}; starting on the 1st, settling now.")
    else:
        print(f"Game date {today}; waiting for the next month.")

    while True:
        time.sleep(POLL_SECONDS)
        now = game_date(memory)
        if now is None:
            continue

        # Save reload: the manager address changes when a save is (re)loaded.
        # All previously read addresses are stale, but the settled month is kept
        # so a reload does not re-settle the current month.
        current_manager = manager_address(memory)
        if current_manager != last_manager:
            print(
                f"Save reloaded at {now}; manager address changed "
                f"0x{last_manager:X} -> 0x{current_manager:X}. "
                f"Addresses are stale; re-reading roster on next settlement."
            )
            last_manager = current_manager
            continue

        key = month_key(now)
        if key == last_month:
            continue
        if key < last_month:
            # A save reload can move the date backwards; adopt it without paying.
            print(f"In-game date moved back to {now}; resetting the month.")
            last_month = key
            continue

        if now.day != 1:
            print(f"{now}: month changed without seeing the 1st; settling once.")

        try:
            written = settle_month(memory, gain)
        except RuntimeError as error:
            print(f"Cannot read players ({error}); retrying.")
            continue

        last_month = key
        for change in written:
            print(
                f"{now}  {change.name:<26} CA {change.ca:>3} -> "
                f"{change.new_ca:>3}  PA {change.pa:>3}"
            )
        print(f"{now}: wrote {len(written)} players.")


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Add CA to every controlled player once per in-game month."
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="show the planned changes for the current date and exit",
    )
    args = parser.parse_args(argv)

    try:
        config: Config = load_config()
        gain = monthly_gain(load_settings())
        with Memory.open(config) as memory:
            if args.preview:
                return preview(memory, gain)
            return watch(memory, gain)
    except KeyboardInterrupt:
        print("Stopped.")
        return 0
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
