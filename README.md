# FM24 CA Growth Final

FM24 memory tooling. Currently reads the human manager UID and the UIDs of every
team they control, including reserves, youth teams, and linked B teams.

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
python src/fm24_manager.py
```

The script prints one UID line:

```text
2002076260
```

If the game runs as administrator, run this tool as administrator too.

## Read all controlled team UIDs

```powershell
python src/fm24_team.py
```

Example output, one UID per line:

```text
920
2000379849
2000069496
2000379860
3609393
```

The first team can share the club UID; youth teams have their own UID. Linked
B teams are included as well.

## Pointer chain

```text
exe + manager.container_rva   -> manager container
      container + vector_off  -> array begin
      begin                   -> human manager record (you)
      manager + person_off    -> person sub-object
      person + uid_off        -> manager UID (u32)

      person + contract_off   -> contract
      contract + team_off     -> managed team
      team + club_off         -> club
      club + teams_begin      -> owned teams (first team, reserves, youth)
      club + linked_teams_begin -> linked teams (B team)
      each team + uid_off     -> team UID (u32)
```

All offsets live in `src/offsets.toml`. Update only that file when the game
version changes.

See [docs/pointer-chain-example.md](docs/pointer-chain-example.md) for a
concrete walkthrough with real addresses and values.

## Project layout

| File | Responsibility |
|---|---|
| `src/fm24_manager.py` | Manager lookup, manager UID chain, and command-line entry point |
| `src/fm24_team.py` | All controlled team UIDs and command-line entry point |
| `src/fm24_memory.py` | Process access, low-level reads, and pointer vectors |
| `src/fm24_config.py` | Load and validate `offsets.toml` |
| `src/offsets.toml` | FM24 memory offsets |
| `tests/` | Unit tests (no game process required) |

## Development checks

```powershell
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check .
```
