"""Load and validate offsets.toml and config.json."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).with_name("offsets.toml")
SETTINGS_PATH = Path(__file__).with_name("config.json")

Config = dict[str, Any]


@dataclass(frozen=True, slots=True)
class CapRule:
    """Linear age cap: ratio goes from start_ratio to end_ratio with age."""

    start_age: float
    start_ratio: float
    end_age: float
    end_ratio: float


@dataclass(frozen=True, slots=True)
class GrowthSettings:
    """Validated values from config.json."""

    monthly_gain: int
    cap: CapRule


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


def load_growth_settings(path: Path = SETTINGS_PATH) -> GrowthSettings:
    """Load and validate the growth settings in config.json."""
    settings = load_settings(path)

    gain = settings.get("monthly_gain")
    if not isinstance(gain, int) or isinstance(gain, bool) or gain <= 0:
        raise RuntimeError("config.json must contain a positive integer monthly_gain")

    raw_cap = settings.get("cap", {})
    if not isinstance(raw_cap, dict):
        raise RuntimeError("config.json cap must be an object")
    start_age = raw_cap.get("start_age", 18)
    start_ratio = raw_cap.get("start_ratio", 0.7)
    end_age = raw_cap.get("end_age", 22)
    end_ratio = raw_cap.get("end_ratio", 0.9)
    for name, value in (
        ("start_age", start_age),
        ("end_age", end_age),
        ("start_ratio", start_ratio),
        ("end_ratio", end_ratio),
    ):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RuntimeError(f"config.json cap {name} must be a number")
    if start_age < 0 or end_age <= start_age:
        raise RuntimeError("config.json cap must have 0 <= start_age < end_age")
    for name, ratio in (("start_ratio", start_ratio), ("end_ratio", end_ratio)):
        if not 0 < ratio <= 1:
            raise RuntimeError(f"config.json cap {name} must be in (0, 1]")

    cap = CapRule(
        float(start_age), float(start_ratio), float(end_age), float(end_ratio)
    )
    return GrowthSettings(gain, cap)
