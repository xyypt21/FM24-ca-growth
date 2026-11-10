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

## Read every controlled team's players

```powershell
python src/fm24_players.py
```

Each controlled team is printed with its UID, then its players (tab-separated):

```text
Team 920
Name	CA	PA	Age
Leo Greiml	136	136	23.7
Assan Ouédraogo	158	180	18.8
Keke Topp	136	150	21.0

Team 2000379849
Name	CA	PA	Age
...
```

Names prefer the short name and fall back to first name + last name. Age is
calculated from the in-game date, not from the system clock. Roster records that
are not player records are skipped.

### Record magic

"Record magic" is the 4-byte type tag at the very start of each roster record.
It is not a pointer and not part of the person data; it only says which record
layout this is, and therefore where the person sub-object starts:

| Magic | Meaning | Person offset |
|---|---|---|
| `0x45A4E958` | Normal player | `+0x278` |
| `0x45C7E798` | Player who is also staff | `+0x368` |

Any other tag is not a player record (for example `0x45C7D028` appears in the
roster without a person/name) and is skipped.

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

      team + roster_begin     -> player record pointers
      record + 0              -> record type tag (magic; selects the layout)
      record + ca / pa        -> current / potential ability (u16)
      record + layout offset  -> person sub-object
      person + short_name / first_name / last_name -> name string
      person + birth_doy / birth_year -> birth date
      exe + game_date.rva     -> in-game date for age
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
| `src/fm24_players.py` | Player names, CA, PA, and ages for all controlled teams |
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
