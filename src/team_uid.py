"""Print the UID of the team controlled by the human manager.

    manager_address(memory)       -> human manager record
    manager + person_off          -> person sub-object
    person + contract_off         -> contract
    contract + team_off           -> managed team
    team + uid_off                -> team UID (u32)

Usage:

    python src/team_uid.py        # prints one UID line; no arguments

The game must be running with a save loaded.
"""

from __future__ import annotations

from fm24_config import Config, load_config
from fm24_memory import Memory, manager_address


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


def team_uid(memory: Memory) -> int:
    """Return the UID of the team controlled by the human manager."""
    team = user_team(memory)
    uid = memory.read_u32(team + memory.config["team"]["uid_off"])
    if not uid:
        raise RuntimeError("Failed to read the team UID")
    return uid


def read_team_uid(config: Config | None = None) -> int:
    """Open the game process and read the managed team UID."""
    if config is None:
        config = load_config()
    with Memory.open(config) as memory:
        return team_uid(memory)


def main() -> int:
    """Command-line entry point: print the managed team UID."""
    try:
        print(read_team_uid())
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
