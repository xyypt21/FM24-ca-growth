"""Load and validate offsets.toml."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).with_name("offsets.toml")
SETTINGS_PATH = Path(__file__).with_name("config.json")

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

    # TOML keys are strings, but record type tags are numbers in the code.
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


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    """Load config.json for settings that are not game offsets."""
    try:
        with path.open(encoding="utf-8") as file:
            settings = json.load(file)
    except OSError as error:
        raise RuntimeError(f"Cannot read settings file {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Settings file is not valid JSON: {error}") from error

    if not isinstance(settings, dict):
        raise RuntimeError(f"Settings file {path} must contain a JSON object")
    return settings
