# FM24 CA Growth Final

FM24 memory tooling. The first step, reading the human manager's UID, is done.

## Requirements

- Windows
- Football Manager 2024 running with a save loaded
- Python 3.11 or newer

## Install

```powershell
python -m pip install pymem psutil
```

## Read the manager UID

```powershell
python manager_uid.py
```

The script prints one UID line:

```text
2002076260
```

If the game runs as administrator, run this tool as administrator too.

## Pointer chain

```text
exe + manager.container_rva   -> manager container
      container + vector_off  -> array begin
      begin                   -> human manager record (you)
      manager + person_off    -> person sub-object
      person + uid_off        -> UID (u32)
```

All offsets live in `offsets.toml`. Update only that file when the game version
changes.

## Project layout

| File | Responsibility |
|---|---|
| `manager_uid.py` | Command-line entry point and pointer chain for the manager UID |
| `fm24_memory.py` | Open the process, read bytes, pointers, and u32 values |
| `fm24_config.py` | Load and validate `offsets.toml` |
| `offsets.toml` | FM24 memory offsets |
| `tests/` | Unit tests (no game process required) |

## Development checks

```powershell
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check .
```
