"""Print the UID of the team controlled by the human manager.

Usage:

    python src/team_uid.py       # prints one UID line; no arguments

The game must be running with a save loaded.
"""

from __future__ import annotations

from fm24_game import read_team_uid


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
