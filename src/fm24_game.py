"""Resolve the human manager and managed team in FM24 memory.

Pointer chains (each step is one pointer read):

    exe + manager.container_rva   -> manager container
          container + vector_off  -> array begin
          begin                   -> human manager record (you)
          manager + person_off    -> person sub-object
          person + uid_off        -> manager UID (u32)

          person + contract_off   -> contract
          contract + team_off     -> managed team
          team + uid_off          -> team UID (u32)
"""

from __future__ import annotations

from fm24_config import Config, load_config
from fm24_memory import Memory


def manager_address(memory: Memory) -> int:
    """Follow the pointer chain and return the human manager record address."""
    manager_cfg = memory.config["manager"]

    container = memory.read_ptr(memory.base + manager_cfg["container_rva"])
    if not container:
        raise RuntimeError(
            "Failed to read the manager container: save not loaded or wrong offsets"
        )

    # container + vector_off is the array begin; begin[0] is the manager
    # (the array contains only the human manager).
    begin = memory.read_ptr(container + manager_cfg["vector_off"])
    if not begin:
        raise RuntimeError("Failed to read the human manager array")

    manager = memory.read_ptr(begin)
    if manager is None or not memory.is_valid_ptr(manager):
        raise RuntimeError("The human manager pointer is invalid")
    return manager


def manager_uid(memory: Memory) -> int:
    """Return the human manager's UID."""
    manager = manager_address(memory)
    person = manager + memory.config["manager"]["person_off"]
    uid = memory.read_u32(person + memory.config["person"]["uid_off"])
    if not uid:
        raise RuntimeError("Failed to read the manager UID")
    return uid


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


def read_manager_uid(config: Config | None = None) -> int:
    """Open the game process and read the manager UID."""
    if config is None:
        config = load_config()
    with Memory.open(config) as memory:
        return manager_uid(memory)


def read_team_uid(config: Config | None = None) -> int:
    """Open the game process and read the managed team UID."""
    if config is None:
        config = load_config()
    with Memory.open(config) as memory:
        return team_uid(memory)
