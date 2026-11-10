"""Monthly CA growth for every player in the controlled teams.

Each in-game month change adds ``monthly_gain`` CA to every unique player in
every team controlled by the human manager who is at most ``max_age`` years old.
CA never grows above PA, so players already at their potential are skipped.

This script watches the in-game date; it does not use the system clock. It
re-reads the rosters on every settlement, so CA, PA, age, and record addresses
are always current. It detects save reloads by watching the club address, which
changes when the game loads a save. Growth only happens when the month actually
changes; starting on the 1st does not trigger an immediate settlement.

Usage:

    python src/fm24_ca_growth.py            # run until Ctrl+C
    python src/fm24_ca_growth.py --preview  # show the plan; write nothing

Settings live in ``config.json``: monthly gain, max age, and age-based PA caps.
The game must be running with a save loaded. This script WRITES to game memory,
unlike the reader commands. Run it at the same privilege level as the game.
"""

from __future__ import annotations

import argparse
import datetime
import time
from collections.abc import Iterable
from dataclasses import dataclass

from fm24_config import (
    CapRule,
    Config,
    GrowthSettings,
    load_config,
    load_growth_settings,
)
from fm24_memory import Memory
from fm24_players import game_date, team_players
from fm24_team import user_club

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
    cap: int
    age: float | None = None


def month_key(date: datetime.date) -> int:
    """Compress a date into a month number for ordering."""
    return date.year * 12 + date.month


def growth_cap(age: float, pa: int, caps: tuple[CapRule, ...]) -> int:
    """Return the CA ceiling for this age, capped by PA.

    The first rule whose below_age is greater than age wins; with no matching
    rule the ceiling is PA itself.
    """
    for rule in caps:
        if age < rule.below_age:
            # Add a tiny epsilon so 180 * 0.7 -> 126.0, not 125.999... -> 125.
            return min(pa, int(pa * rule.pa_ratio + 1e-9))
    return pa


def growth_target(ca: int, pa: int, age: float, settings: GrowthSettings) -> int | None:
    """Return CA + monthly_gain when it stays within the age cap; else None."""
    if not (1 <= ca <= 200 and 1 <= pa <= 200) or ca > pa:
        return None
    cap = growth_cap(age, pa, settings.caps)
    new_ca = ca + settings.monthly_gain
    return new_ca if new_ca <= cap else None


def controlled_players(memory: Memory) -> list[Player]:
    """Return every player record in every controlled team."""
    return [player for _, players in team_players(memory) for player in players]


def growth_plan(players: Iterable[Player], settings: GrowthSettings) -> list[Change]:
    """Return the planned CA changes, deduplicated by player record address.

    Only players younger than ``settings.max_age`` are eligible. With max_age
    22, a 21.9-year-old grows while a 22.0-year-old does not.
    """
    changes: list[Change] = []
    seen: set[int] = set()
    for player in players:
        address = player["address"]
        if address in seen:
            continue
        seen.add(address)

        age = player["age"]
        if age is None or age >= settings.max_age:
            continue

        ca = player["ca"]
        pa = player["pa"]
        new_ca = growth_target(ca, pa, age, settings)
        if new_ca is None:
            continue
        changes.append(
            Change(
                name=str(player["name"]),
                address=address,
                ca=ca,
                new_ca=new_ca,
                pa=pa,
                cap=growth_cap(age, pa, settings.caps),
                age=age,
            )
        )
    return changes


def settle_month(memory: Memory, settings: GrowthSettings) -> list[Change]:
    """Write the planned CA changes and return the ones that were verified."""
    players = controlled_players(memory)
    if not players:
        raise RuntimeError("No players found: save not loaded or wrong offsets")

    ca_off = memory.config["player"]["ca"]
    written: list[Change] = []
    for change in growth_plan(players, settings):
        if not memory.write_u16(change.address + ca_off, change.new_ca):
            print(f"Write failed: {change.name} (0x{change.address:X})")
            continue
        written.append(change)
    return written


def print_plan(
    today: datetime.date, changes: list[Change], settings: GrowthSettings
) -> None:
    """Print the planned changes sorted by age, youngest first."""
    print(f"Planned CA changes for {today} (+{settings.monthly_gain} CA):")
    ordered = sorted(
        changes, key=lambda change: (change.age is None, change.age or 0.0)
    )
    for change in ordered:
        age = "-" if change.age is None else f"{change.age:.1f}"
        print(
            f"  {change.name:<26} age {age:>4}  CA {change.ca:>3} -> "
            f"{change.new_ca:>3}  PA {change.pa:>3}  cap {change.cap:>3}"
        )
    print(f"  {len(changes)} players.")


def show_plan(memory: Memory, today: datetime.date, settings: GrowthSettings) -> bool:
    """Print the next settlement plan without writing; return False if unreadable."""
    try:
        players = controlled_players(memory)
    except RuntimeError as error:
        print(f"Cannot read players for preview ({error}).")
        return False
    if not players:
        print("No players readable for preview.")
        return False
    print_plan(today, growth_plan(players, settings), settings)
    return True


def preview(memory: Memory, settings: GrowthSettings) -> int:
    """Show the current plan without writing to game memory."""
    today = game_date(memory)
    if today is None:
        raise RuntimeError("Cannot read the in-game date")
    if not show_plan(memory, today, settings):
        raise RuntimeError("No players found: save not loaded or wrong offsets")
    return 0


def watch(memory: Memory, settings: GrowthSettings) -> int:
    """Settle once per new in-game month until interrupted.

    Growth only happens when the in-game month actually changes. Starting on
    the 1st does not trigger an immediate settlement.

    Save reload detection: reloading a save changes every address in memory,
    including the club. The watcher compares the club address on each loop
    iteration. When it changes, the state resets to the current month without
    settling and the next plan is previewed. Every settlement re-reads all
    rosters, so no address is cached.
    """
    today = game_date(memory)
    if today is None:
        raise RuntimeError("Cannot read the in-game date")

    last_club = user_club(memory)
    last_month = month_key(today)
    print(f"Game date {today}; waiting for the next month.")
    show_plan(memory, today, settings)

    while True:
        time.sleep(POLL_SECONDS)
        now = game_date(memory)
        if now is None:
            continue

        try:
            current_club = user_club(memory)
        except RuntimeError:
            # The save is still loading; try again on the next poll.
            continue

        if current_club != last_club:
            print(
                f"Save reloaded at {now}; club address changed "
                f"0x{last_club:X} -> 0x{current_club:X}. "
                f"Resetting state; waiting for next month."
            )
            last_club = current_club
            last_month = month_key(now)
            show_plan(memory, now, settings)
            continue

        key = month_key(now)
        if key == last_month:
            continue

        try:
            written = settle_month(memory, settings)
        except RuntimeError as error:
            print(f"Cannot read players ({error}); retrying.")
            continue

        last_month = key
        for change in written:
            print(
                f"{now}  {change.name:<26} CA {change.ca:>3} -> "
                f"{change.new_ca:>3}  PA {change.pa:>3}  cap {change.cap:>3}"
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
        settings = load_growth_settings()
        with Memory.open(config) as memory:
            if args.preview:
                return preview(memory, settings)
            return watch(memory, settings)
    except KeyboardInterrupt:
        print("Stopped.")
        return 0
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
