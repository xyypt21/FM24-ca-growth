"""Load and validate offsets.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).with_name("offsets.toml")

Config = dict[str, Any]

# Sections used by the current step. Add names here as features grow.
REQUIRED_SECTIONS = (
    "manager",
    "person",
    "contract",
    "team",
    "club",
    "player",
    "game_date",
    "read",
)


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Load offsets.toml, check the top-level keys, and return a nested dict."""
    try:
        with path.open("rb") as file:
            config = tomllib.load(file)
    except OSError as error:
        raise RuntimeError(f"Cannot read offsets file {path}: {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise RuntimeError(f"Offsets file is not valid TOML: {error}") from error

    missing = [
        name for name in ("process_name", *REQUIRED_SECTIONS) if name not in config
    ]
    if missing:
        raise RuntimeError(f"Offsets file {path} is missing: {', '.join(missing)}")

    # TOML keys are strings, but record magics are numbers in the code.
    layouts = config["player"].get("layouts", {})
    try:
        config["player"]["layouts"] = {
            int(tag, 0): offset for tag, offset in layouts.items()
        }
    except ValueError as error:
        raise RuntimeError(
            f"Offsets file {path} has an invalid [player.layouts] key: {error}"
        ) from error
    return config
