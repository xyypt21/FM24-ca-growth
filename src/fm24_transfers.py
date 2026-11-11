"""Apply agreed future transfers to a player list.

The global transfer manager keeps an array of future transfer records. Only one
status counts: 19 (agreed, not yet active). Other statuses are bids, listings, or
interest, and 20 is a transfer that already happened.

    exe + future_transfer.manager_rva -> transfer manager
    manager + vector_begin / vector_end -> future transfer array
    record + person / dest_team / src_team / date / status

    dest is one of our teams, src is not -> incoming
    src is one of our teams, dest is not -> outgoing
    both or neither belong to us       -> ignored (reserves/youth movement)

An outgoing player is still in the roster, so the records are matched by person
address. An incoming player is not in the roster yet: the transfer only stores
the person address, so the record start is ``person - person_layouts[tag]``.

Usage:

    from fm24_transfers import with_transfers

    players = with_transfers(memory, all_players(memory))

The game must be running with a save loaded.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from fm24_memory import Memory
from fm24_players import (
    POSITION_MIN,
    Player,
    calc_age,
    game_date,
    parse_game_date,
    read_name,
    read_u16,
)
from fm24_team import club_teams

# Status byte: 19 = agreed, not yet active. 20 = already active (history).
AGREED_TRANSFER_STATUS = 19


@dataclass(frozen=True, slots=True)
class Transfer:
    """One agreed future transfer, seen from our club."""

    direction: str  # "in" or "out"
    team: int  # destination team for "in", source team for "out"


def future_transfers(
    memory: Memory,
    teams: set[int],
    today: datetime.date | None = None,
) -> dict[int, Transfer]:
    """Map person address -> agreed future transfer, relative to our teams."""
    cfg = memory.config["future_transfer"]
    person_layouts: dict[int, int] = memory.config["player"]["person_layouts"]

    manager = memory.read_ptr(memory.base + cfg["manager_rva"])
    if not manager or not memory.is_valid_ptr(manager):
        return {}

    begin = memory.read_ptr(manager + cfg["vector_begin"])
    end = memory.read_ptr(manager + cfg["vector_end"])
    if not begin or not end or begin >= end:
        return {}
    if not memory.is_valid_ptr(begin) or not memory.is_valid_ptr(end):
        return {}

    transfers: dict[int, Transfer] = {}
    for index in range((end - begin) // 8):
        address = memory.read_ptr(begin + index * 8)
        if not address or not memory.is_valid_ptr(address):
            continue

        record = memory.read_bytes(address, cfg["status"] + 1)
        if not record or record[cfg["status"]] != AGREED_TRANSFER_STATUS:
            continue

        when = parse_game_date(
            int.from_bytes(record[cfg["date"] : cfg["date"] + 4], "little")
        )
        if when is None or (today is not None and when <= today):
            continue

        person = int.from_bytes(record[cfg["person"] : cfg["person"] + 8], "little")
        tag = memory.read_bytes(person, 4)
        if not tag or int.from_bytes(tag, "little") not in person_layouts:
            continue

        dest = int.from_bytes(record[cfg["dest_team"] : cfg["dest_team"] + 8], "little")
        src = int.from_bytes(record[cfg["src_team"] : cfg["src_team"] + 8], "little")
        if dest in teams and src not in teams:
            transfers[person] = Transfer("in", dest)
        elif src in teams and dest not in teams:
            transfers.setdefault(person, Transfer("out", src))
    return transfers


def read_incoming(
    memory: Memory,
    person: int,
    team: int,
    today: datetime.date | None,
) -> Player | None:
    """Read an incoming player who is not in the roster yet.

    The person vtable tag selects the record layout, so the record start is
    ``person - offset``. The contract still belongs to the old club, so no loan
    or contract data is read.
    """
    player_cfg = memory.config["player"]
    person_cfg = memory.config["person"]
    person_layouts: dict[int, int] = player_cfg["person_layouts"]
    layouts: dict[int, int] = player_cfg["layouts"]
    positions_cfg: dict[str, int] = player_cfg.get("positions", {})
    record_size = player_cfg["record_read"]

    tag = memory.read_bytes(person, 4)
    if not tag:
        return None
    offset = person_layouts.get(int.from_bytes(tag, "little"))
    if offset is None:
        return None

    address = person - offset
    record = memory.read_bytes(address, record_size)
    if not record or len(record) < record_size:
        return None
    person_offset = layouts.get(int.from_bytes(record[:4], "little"))
    if person_offset is None:
        return None
    data = record[person_offset:]

    return {
        "address": address,
        "person": person,
        "team_uid": memory.read_u32(team + memory.config["team"]["uid_off"]) or 0,
        "name": read_name(memory, data) or "(unknown)",
        "ca": read_u16(record, player_cfg["ca"]),
        "pa": read_u16(record, player_cfg["pa"]),
        "age": calc_age(
            read_u16(data, person_cfg["birth_year"]),
            read_u16(data, person_cfg["birth_doy"]),
            today,
        ),
        "positions": [
            code
            for code, position_offset in positions_cfg.items()
            if position_offset < len(record) and record[position_offset] >= POSITION_MIN
        ],
        "loan": "",
    }


def with_transfers(
    memory: Memory,
    players: list[Player],
    teams: set[int] | None = None,
    today: datetime.date | None = None,
) -> list[Player]:
    """Drop outgoing players and append incoming players not in the roster.

    ``teams`` defaults to every controlled team; ``today`` defaults to the
    in-game date. Passing them explicitly avoids reading the same values twice.
    """
    if teams is None:
        teams = set(club_teams(memory))
    if today is None:
        today = game_date(memory)

    transfers = future_transfers(memory, teams, today)
    outgoing = {
        person for person, transfer in transfers.items() if transfer.direction == "out"
    }
    known = {player.get("person") for player in players}

    result = [player for player in players if player.get("person") not in outgoing]
    for person, transfer in transfers.items():
        if transfer.direction != "in" or person in known:
            continue
        incoming = read_incoming(memory, person, transfer.team, today)
        if incoming is not None:
            result.append(incoming)
    return result
