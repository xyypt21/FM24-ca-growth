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
    """One age band cap: below_age -> CA may not exceed pa_ratio * PA."""

    below_age: float
    pa_ratio: float


@dataclass(frozen=True, slots=True)
class GrowthSettings:
    """Validated values from config.json."""

    monthly_gain: int
    max_age: int
    caps: tuple[CapRule, ...]


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

    max_age = settings.get("max_age", 22)
    if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age < 0:
        raise RuntimeError("config.json max_age must be a non-negative integer")

    raw_caps = settings.get("cap", [])
    if not isinstance(raw_caps, list):
        raise RuntimeError("config.json cap must be an array")
    caps: list[CapRule] = []
    for item in raw_caps:
        if not isinstance(item, dict):
            raise RuntimeError("config.json cap entries must be objects")
        below_age = item.get("below_age")
        pa_ratio = item.get("pa_ratio")
        if (
            not isinstance(below_age, (int, float))
            or isinstance(below_age, bool)
            or below_age <= 0
        ):
            raise RuntimeError("config.json cap below_age must be a positive number")
        if (
            not isinstance(pa_ratio, (int, float))
            or isinstance(pa_ratio, bool)
            or not 0 < pa_ratio <= 1
        ):
            raise RuntimeError("config.json cap pa_ratio must be in (0, 1]")
        caps.append(CapRule(float(below_age), float(pa_ratio)))

    caps.sort(key=lambda rule: rule.below_age)
    return GrowthSettings(gain, max_age, tuple(caps))
