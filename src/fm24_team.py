"""Print the UIDs of all teams controlled by the human manager.

    manager_address(memory)       -> human manager record
    manager + person_off          -> person sub-object
    person + contract_off         -> contract
    contract + team_off           -> managed team
    team + club_off               -> club
    club + teams_begin            -> owned teams (first team, reserves, youth)
    club + linked_teams_begin     -> linked teams (B team)
    each team + uid_off           -> team UID (u32)

Usage:

    python src/fm24_team.py       # prints one UID per line; no arguments

The game must be running with a save loaded.
"""

from __future__ import annotations

from fm24_config import Config, load_config
from fm24_manager import manager_address
from fm24_memory import Memory


def user_team(memory: Memory) -> int:
    """Follow the contract chain and return the human manager's team address."""
    manager = manager_address(memory)
    person = manager + memory.config["manager"]["person_off"]
    contract = memory.read_ptr(person + memory.config["person"]["contract_off"])
    if not contract or not memory.is_valid_ptr(contract):
        raise RuntimeError("No team belongs to the human manager (are you unemployed?)")

    team = memory.read_ptr(contract + memory.config["contract"]["team_off"])
    if not team or not memory.is_valid_ptr(team):
        raise RuntimeError("No team belongs to the human manager (are you unemployed?)")
    return team


def user_club(memory: Memory) -> int:
    """Return the club of the team controlled by the human manager."""
    team = user_team(memory)
    club = memory.read_ptr(team + memory.config["team"]["club_off"])
    if not club or not memory.is_valid_ptr(club):
        raise RuntimeError("The managed team has no club pointer")
    return club


def club_teams(memory: Memory) -> list[int]:
    """Return all teams owned or linked by the manager's club."""
    club = user_club(memory)
    club_cfg = memory.config["club"]
    own = memory.read_ptr_vector(club + club_cfg["teams_begin"], "club teams")
    linked = memory.read_ptr_vector(
        club + club_cfg["linked_teams_begin"], "linked teams"
    )
    teams = [team for team in own + linked if memory.is_valid_ptr(team)]
    if not teams:
        raise RuntimeError("The club has no teams")
    return teams


def team_uids(memory: Memory) -> list[int]:
    """Return the UIDs of every team controlled by the human manager."""
    uid_off = memory.config["team"]["uid_off"]
    uids: list[int] = []
    seen: set[int] = set()
    for team in club_teams(memory):
        uid = memory.read_u32(team + uid_off)
        if uid and uid not in seen:
            seen.add(uid)
            uids.append(uid)

    if not uids:
        raise RuntimeError("Failed to read the team UIDs")
    return uids


def read_team_uids(config: Config | None = None) -> list[int]:
    """Open the game process and read all controlled team UIDs."""
    if config is None:
        config = load_config()
    with Memory.open(config) as memory:
        return team_uids(memory)


def main() -> int:
    """Command-line entry point: print every controlled team UID."""
    try:
        for uid in read_team_uids():
            print(uid)
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
