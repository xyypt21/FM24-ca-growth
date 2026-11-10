"""Print the human manager's UID.

Usage:

    python src/manager_uid.py    # prints one UID line; no arguments

The game must be running with a save loaded.
"""

from __future__ import annotations

from fm24_memory import read_manager_uid


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
