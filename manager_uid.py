"""Print the human manager's UID by reading FM24 memory.

Pointer chain (each step is one pointer read):

    exe + manager.container_rva   -> manager container
          container + vector_off  -> array begin
          begin                   -> human manager record (you)
          manager + person_off    -> person sub-object
          person + uid_off        -> UID (u32)

Usage:

    pip install pymem psutil
    python manager_uid.py        # prints one UID line; no arguments

The game must be running with a save loaded, otherwise the script reports
"Cannot find fm.exe".
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
