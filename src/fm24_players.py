"""List every player in a controlled team: name, CA, PA, and age.

    team UID                      -> team address (searched in the club teams)
    team + roster_begin           -> player record pointer array
    record + 0                     -> record magic (selects the layout)
    record + ca / pa              -> current / potential ability (u16)
    record + layout person offset -> person sub-object
    person + short_name / ...     -> name holder pointers -> [u32][utf-8] string
    person + birth_doy / birth_year -> birth date
    exe + game_date.rva           -> in-game date used to calculate age

Usage:

    python src/fm24_players.py <team_uid>

The game must be running with a save loaded. Use `python src/fm24_team.py` to
list the team UIDs controlled by the human manager.
"""

from __future__ import annotations

import argparse
import datetime

from fm24_config import Config, load_config
from fm24_memory import Memory
from fm24_team import club_teams


def parse_game_date(value: int) -> datetime.date | None:
    """Convert the packed in-game date to a date; return None when implausible."""
    year = value >> 16
    day_of_year = (value & 0xFF) + ((value >> 8) & 1) * 256
    try:
        return datetime.date(year, 1, 1) + datetime.timedelta(days=day_of_year - 1)
    except (ValueError, OverflowError):
        return None


def game_date(memory: Memory) -> datetime.date | None:
    """Read the in-game date; return None if it cannot be read."""
    raw = memory.read_bytes(memory.base + memory.config["game_date"]["rva"], 4)
    return parse_game_date(int.from_bytes(raw, "little")) if raw else None


def calc_age(year: int, day_of_year: int, today: datetime.date | None) -> float | None:
    """Return age in years with one decimal, or None for invalid birth data.

    The whole part counts birthdays already passed. The decimal part is the
    days since the last birthday divided by 365.25, truncated to 0.1 so that
    23.97 does not show as 24.0.
    """
    if not today or not 1900 < year < 2100 or not 1 <= day_of_year <= 366:
        return None

    try:
        birth = datetime.date(year, 1, 1) + datetime.timedelta(days=day_of_year - 1)
    except ValueError:
        return None

    whole = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        whole -= 1

    try:
        last_birthday = birth.replace(year=birth.year + whole)
    except ValueError:  # 29 February in a common year: treat it as 28 February
        last_birthday = birth.replace(year=birth.year + whole, day=28)

    tenths = int((whole + (today - last_birthday).days / 365.25) * 10)
    return tenths / 10


def read_string(memory: Memory, pointer: int | None) -> str | None:
    """Read a game string ([u32 length][utf-8]); return None if it is invalid.

    Name fields hold a holder pointer that points at another pointer before the
    string, so follow up to three levels. Length and bytes are validated so
    that garbage is not mistaken for a name.
    """
    limits = memory.config["read"]

    for _ in range(3):
        if not pointer:
            return None

        raw = memory.read_bytes(pointer, limits["name_buf"])
        if not raw:
            return None

        length = int.from_bytes(raw[:4], "little")
        if 0 < length < limits["name_max"]:
            text = raw[4 : 4 + length]
            if all(32 <= byte < 127 or byte > 0x7F for byte in text):
                return text.decode("utf-8", "replace")

        pointer = int.from_bytes(raw[:8], "little")
        if not memory.is_valid_ptr(pointer):
            return None
    return None


def read_name(memory: Memory, person: bytes) -> str | None:
    """Return the person's name: short name first, otherwise first + last name."""
    person_cfg = memory.config["person"]

    def field(offset: int) -> int:
        return int.from_bytes(person[offset : offset + 8], "little")

    short = read_string(memory, field(person_cfg["short_name"]))
    if short:
        return short

    first = read_string(memory, field(person_cfg["first_name"])) or ""
    last = read_string(memory, field(person_cfg["last_name"])) or ""
    parts = (first.split(" ")[0], last.split(" ")[0])
    return " ".join(part for part in parts if part) or None


def read_u16(record: bytes, offset: int) -> int:
    """Slice one little-endian 2-byte integer from a record or person object."""
    return int.from_bytes(record[offset : offset + 2], "little")


def find_team(memory: Memory, uid: int) -> int:
    """Return the address of a controlled team by its UID."""
    uid_off = memory.config["team"]["uid_off"]
    for team in club_teams(memory):
        if memory.read_u32(team + uid_off) == uid:
            return team
    raise RuntimeError(f"Team UID {uid} is not controlled by the human manager")


def players_in_team(
    memory: Memory, team: int, today: datetime.date | None = None
) -> list[dict[str, object]]:
    """Read every player record in a team; records that are not players are skipped."""
    player_cfg = memory.config["player"]
    person_cfg = memory.config["person"]
    layouts: dict[int, int] = player_cfg["layouts"]
    record_size = player_cfg["record_read"]

    if today is None:
        today = game_date(memory)

    players: list[dict[str, object]] = []
    for address in memory.read_ptr_vector(
        team + memory.config["team"]["roster_begin"], "team roster"
    ):
        record = memory.read_bytes(address, record_size)
        if not record or len(record) < record_size:
            continue

        person_offset = layouts.get(int.from_bytes(record[:4], "little"))
        if person_offset is None:
            continue
        person = record[person_offset:]

        players.append(
            {
                "name": read_name(memory, person) or "(unknown)",
                "ca": read_u16(record, player_cfg["ca"]),
                "pa": read_u16(record, player_cfg["pa"]),
                "age": calc_age(
                    read_u16(person, person_cfg["birth_year"]),
                    read_u16(person, person_cfg["birth_doy"]),
                    today,
                ),
            }
        )
    return players


def players_by_team_uid(memory: Memory, uid: int) -> list[dict[str, object]]:
    """Return every player in the controlled team with this UID."""
    return players_in_team(memory, find_team(memory, uid))


def read_players(
    team_uid: int, config: Config | None = None
) -> list[dict[str, object]]:
    """Open the game process and read every player in the team."""
    if config is None:
        config = load_config()
    with Memory.open(config) as memory:
        return players_by_team_uid(memory, team_uid)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: print the players of one controlled team."""
    parser = argparse.ArgumentParser(description="List players in a controlled team.")
    parser.add_argument("team_uid", type=int, help="team UID; see fm24_team.py")
    args = parser.parse_args(argv)

    try:
        players = read_players(args.team_uid)
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1

    print("Name\tCA\tPA\tAge")
    for player in players:
        age = player["age"]
        age_text = "-" if age is None else f"{age:.1f}"
        print(f"{player['name']}\t{player['ca']}\t{player['pa']}\t{age_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
