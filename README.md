# FM24 CA Growth Final

FM24 memory tooling. Currently reads the human manager UID and the UID of the
team they control.

## Requirements

- Windows
- Football Manager 2024 running with a save loaded
- Python 3.11 or newer

## Install

```powershell
python -m pip install pymem
```

## Read the manager UID

```powershell
python src/manager_uid.py
```

The script prints one UID line:

```text
2002076260
```

If the game runs as administrator, run this tool as administrator too.

## Read the managed team UID

```powershell
python src/team_uid.py
```

Example output:

```text
920
```

The first team can share the club UID; youth teams have their own UID.

## Pointer chain

```text
exe + manager.container_rva   -> manager container
      container + vector_off  -> array begin
      begin                   -> human manager record (you)
      manager + person_off    -> person sub-object
      person + uid_off        -> manager UID (u32)

      person + contract_off   -> contract
      contract + team_off     -> managed team
      team + uid_off          -> team UID (u32)
```

All offsets live in `src/offsets.toml`. Update only that file when the game
version changes.

See [docs/pointer-chain-example.md](docs/pointer-chain-example.md) for a
concrete walkthrough with real addresses and values.

## Project layout

| File | Responsibility |
|---|---|
| `src/manager_uid.py` | Command-line entry point and pointer chain for the manager UID |
| `src/team_uid.py` | Command-line entry point and pointer chain for the team UID |
| `src/fm24_memory.py` | Open the process, read bytes, pointers, and u32 values |
| `src/fm24_config.py` | Load and validate `offsets.toml` |
| `src/offsets.toml` | FM24 memory offsets |
| `tests/` | Unit tests (no game process required) |

## Development checks

```powershell
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check .
```
