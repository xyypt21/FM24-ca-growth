"""Load and validate offsets.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).with_name("offsets.toml")

Config = dict[str, Any]

# Sections used by the current step. Add names here as features grow.
REQUIRED_SECTIONS = ("manager", "person", "read")


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
    return config
