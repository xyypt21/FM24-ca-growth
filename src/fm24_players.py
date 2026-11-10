"""List every player in the controlled teams: name, CA, PA, and age.

    club teams                    -> every team controlled by the human manager
    team + roster_begin           -> player record pointer array
    record + 0                     -> record type tag (selects the layout)
    record + ca / pa              -> current / potential ability (u16)
    record + layout person offset -> person sub-object
    person + short_name / ...     -> name holder pointers -> [u32][utf-8] string
    person + birth_doy / birth_year -> birth date
    exe + game_date.rva           -> in-game date used to calculate age

Usage:

    python src/fm24_players.py    # all controlled teams, grouped by team UID

The game must be running with a save loaded.
"""

from __future__ import annotations

import argparse
import datetime

from fm24_config import Config, load_config
from fm24_memory import Memory
from fm24_team import club_teams

Player = dict[str, object]
POSITION_MIN = 15


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


def read_affiliation_uid(memory: Memory, pointer: int | None) -> int | None:
    """Resolve a club entry (or team) pointer to the club structure's UID."""
    club_cfg = memory.config["club"]
    if not pointer or not memory.is_valid_ptr(pointer):
        return None
    club = memory.read_ptr(pointer + club_cfg["entry_struct"])
    if not club or not memory.is_valid_ptr(club):
        return None
    return memory.read_u32(club + club_cfg["uid_off"])


def read_loan(
    memory: Memory,
    record: bytes,
    contract_offset: int | None,
    our_uids: set[int],
) -> str:
    """Return ``loaned out``, ``loaned in``, or an empty string."""
    player_cfg = memory.config["player"]
    current_offset = player_cfg["current_club"]
    current = int.from_bytes(record[current_offset : current_offset + 8], "little")
    current_uid = read_affiliation_uid(memory, current)

    owner_uid = None
    if contract_offset is not None and contract_offset + 8 <= len(record):
        contract = int.from_bytes(
            record[contract_offset : contract_offset + 8], "little"
        )
        if contract and memory.is_valid_ptr(contract):
            owner = memory.read_ptr(contract + player_cfg["contract_club"])
            owner_uid = read_affiliation_uid(memory, owner)

    if current_uid is None or owner_uid is None:
        return ""
    if current_uid not in our_uids:
        return "loaned out"
    if owner_uid not in our_uids:
        return "loaned in"
    return ""


def controlled_uids(memory: Memory) -> set[int]:
    """Return the UIDs of every controlled team."""
    uid_off = memory.config["team"]["uid_off"]
    return {
        uid for team in club_teams(memory) if (uid := memory.read_u32(team + uid_off))
    }


def players_in_team(
    memory: Memory,
    team: int,
    today: datetime.date | None = None,
    our_uids: set[int] | None = None,
) -> list[Player]:
    """Read every player record in a team; records that are not players are skipped."""
    player_cfg = memory.config["player"]
    person_cfg = memory.config["person"]
    layouts: dict[int, int] = player_cfg["layouts"]
    contract_layouts: dict[int, int] = player_cfg.get("contract_layouts", {})
    positions_cfg: dict[str, int] = player_cfg.get("positions", {})
    record_size = player_cfg["record_read"]
    team_uid = memory.read_u32(team + memory.config["team"]["uid_off"]) or 0
    if our_uids is None:
        our_uids = controlled_uids(memory)

    if today is None:
        today = game_date(memory)

    players: list[Player] = []
    for address in memory.read_ptr_vector(
        team + memory.config["team"]["roster_begin"], "team roster"
    ):
        record = memory.read_bytes(address, record_size)
        if not record or len(record) < record_size:
            continue

        # The first 4 bytes are a record type tag, not a pointer and not part of
        # the person data. It tells us where the person sub-object starts.
        tag = int.from_bytes(record[:4], "little")
        person_offset = layouts.get(tag)
        if person_offset is None:
            continue
        person = record[person_offset:]

        players.append(
            {
                "address": address,
                "team_uid": team_uid,
                "name": read_name(memory, person) or "(unknown)",
                "ca": read_u16(record, player_cfg["ca"]),
                "pa": read_u16(record, player_cfg["pa"]),
                "age": calc_age(
                    read_u16(person, person_cfg["birth_year"]),
                    read_u16(person, person_cfg["birth_doy"]),
                    today,
                ),
                "positions": [
                    code
                    for code, offset in positions_cfg.items()
                    if offset < len(record) and record[offset] >= POSITION_MIN
                ],
                "loan": read_loan(
                    memory,
                    record,
                    contract_layouts.get(tag),
                    our_uids,
                ),
            }
        )
    return players


def all_players(memory: Memory) -> list[Player]:
    """Return every unique player across all controlled teams."""
    players: list[Player] = []
    seen: set[int] = set()
    today = game_date(memory)
    teams = club_teams(memory)
    uid_off = memory.config["team"]["uid_off"]
    our_uids = {uid for team in teams if (uid := memory.read_u32(team + uid_off))}
    for team in teams:
        for player in players_in_team(memory, team, today, our_uids):
            address = player["address"]
            if address in seen:
                continue
            seen.add(address)
            players.append(player)
    return players


def read_players(config: Config | None = None) -> list[Player]:
    """Open the game process and read every player in every controlled team."""
    if config is None:
        config = load_config()
    with Memory.open(config) as memory:
        return all_players(memory)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: print every controlled team's players."""
    parser = argparse.ArgumentParser(description="List players in controlled teams.")
    parser.parse_args(argv)

    try:
        players = read_players()
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1

    groups: dict[int, list[Player]] = {}
    for player in players:
        groups.setdefault(player["team_uid"], []).append(player)

    for index, (uid, roster) in enumerate(groups.items()):
        if index:
            print()
        print(f"Team {uid}")
        print("Name\tCA\tPA\tAge")
        for player in roster:
            age = player["age"]
            age_text = "-" if age is None else f"{age:.1f}"
            print(f"{player['name']}\t{player['ca']}\t{player['pa']}\t{age_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
