"""Print the human manager's UID.

    manager_address(memory)       -> human manager record
    manager + person_off          -> person sub-object
    person + uid_off              -> UID (u32)

Usage:

    python src/manager_uid.py     # prints one UID line; no arguments

The game must be running with a save loaded.
"""

from __future__ import annotations

from fm24_config import Config, load_config
from fm24_memory import Memory, manager_address


def manager_uid(memory: Memory) -> int:
    """Return the human manager's UID."""
    manager = manager_address(memory)
    person = manager + memory.config["manager"]["person_off"]
    uid = memory.read_u32(person + memory.config["person"]["uid_off"])
    if not uid:
        raise RuntimeError("Failed to read the manager UID")
    return uid


def read_manager_uid(config: Config | None = None) -> int:
    """Open the game process and read the manager UID."""
    if config is None:
        config = load_config()
    with Memory.open(config) as memory:
        return manager_uid(memory)


def main() -> int:
    """Command-line entry point: print the manager UID."""
    try:
        print(read_manager_uid())
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
