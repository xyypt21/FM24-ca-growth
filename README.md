# FM24 CA Growth Final

FM24 memory tooling. Reads the human manager UID, the UIDs of every controlled
team, and each team's players (name, CA, PA, age), and can add CA growth every
in-game month.

## Requirements

- Windows
- Football Manager 2024 running with a save loaded
- Python 3.11 or newer

## Install

```powershell
python -m pip install pymem scipy
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

### Record type tag

The record type tag is the 4-byte tag at the very start of each roster record.
It is not a pointer and not part of the person data; it only says which record
layout this is, and therefore where the person sub-object starts:

| Tag | Meaning | Person offset |
|---|---|---|
| `0x45A4E958` | Normal player | `+0x278` |
| `0x45C7E798` | Player who is also staff | `+0x368` |

Any other tag is not a player record (for example `0x45C7D028` appears in the
roster without a person/name) and is skipped.

## Grow CA every in-game month

Run the watcher:

```powershell
python src/fm24_ca_growth.py
```

On every new in-game month it adds the `monthly_gain` value from
`src/config.json` (currently **2**) CA to every unique player in every controlled
team. All growth settings are read together from `config.json`. Rules:

- CA never grows above PA; players already at their potential are skipped.
- Invalid CA/PA values (outside `1..200`, or CA above PA) are skipped.
- Players at or above `max_age` do not grow.
- A player's CA is capped linearly by `cap` from `config.json`. At or below
  `start_age` the cap is `PA × start_ratio`; between `start_age` and `end_age`
  the ratio interpolates linearly towards `end_ratio`; from `end_age` up to
  `max_age` the cap is PA itself. With `(18, 0.7) -> (22, 0.9)`, age 18 uses
  `PA × 0.7`, age 20 uses `PA × 0.8`, and age 22 gains with cap PA.
- Rosters, CA, PA, and record addresses are re-read on every settlement.
- On startup and after a save reload it prints a preview of the players whose
  CA will grow at the next settlement, sorted by age (youngest first); each
  line shows age, current/new CA, PA, and cap. The preview does not write.
- Growth only happens when the in-game month actually changes; starting on the
  1st does not trigger an immediate settlement.
- Stop with Ctrl+C.

Save reload detection

When the game reloads a save, all memory addresses change, including the club
address. The watcher compares the club address on each loop iteration. When it
changes, the state resets to the current month without settling and the next
plan is previewed. Every settlement re-reads all roster, team, and player
addresses, so no address is cached across reloads.

This command **writes to game memory**, unlike the reader commands. Run it at
the same privilege level as the game.

## GUI

The same watcher with buttons, editable settings, and a log window. Double-click
the `.pyw` file, or run:

```powershell
pythonw src/fm24_ca_growth_gui.pyw
```

- **Start** runs the watcher in a background thread.
- **Stop** stops it without closing the window.
- **Preview next settlement** reads the roster and prints the plan; it writes
  nothing.
- The settings panel edits `monthly_gain`, `max_age`, cap start/end age, and cap
  start/end ratio. Changes are validated and saved to `config.json`
  automatically (shortly after typing); Start and Preview also save first.
- **How cap works** opens a window that explains the exact rule:
  - `age <= start_age`: cap is `PA × start_ratio`
  - `start_age < age < end_age`: the ratio rises linearly to `end_ratio`
  - `end_age <= age < max_age`: cap is PA (ratio 1.0)
  - `age >= max_age`: no CA growth
- **Exit** saves the settings, stops the watcher, and closes the window.
- Startup and save reload still print the automatic preview into the log.

## Pick a lineup

Build a 4-3-3 from every controlled team, ranked by CA and then PA:

```powershell
python src/fm24_lineup.py --once   # one lineup, then exit
python src/fm24_lineup.py          # refresh every 30 seconds until Ctrl+C
```

Example:

```text
Slot Name                          Age  CA  PA  Positions
GK   Marius Müller                30.0 126 132  GK
DL   Brandon Soppy                21.3 127 149  DL/DR/MR/WBL/WBR
DC   Timo Baumgartl               27.3 120 132  DC
...
```

- CA is the primary score; PA breaks ties.
- Positions are read from the player record (`>= 15` can play the slot).
- The most constrained slot is filled first.
- If no remaining player can play a slot, the best remaining player fills it
  and is marked with `*` in the console / `Exact = no` in the CSV.
- The lineup is printed and written to `output/lineup.csv`.

## First and second XI

Use scipy's assignment solver to fill both teams at once:

```powershell
python src/fm24_best_eleven.py
```

- CA is the primary score; PA breaks ties.
- The first 11 slots form the first XI, the next 11 the second XI.
- One assignment fills both teams, so the first XI cannot starve the second.
- Positions come from the player record (`>= 15`).
- The result is printed and written to `output/best_eleven.csv` with columns
  `Squad`, `Slot`, `Name`, `Age`, `CA`, `PA`, `Positions`.

## Build a Windows exe

GitHub Actions builds the GUI automatically:

- Go to **Actions** -> **Build Windows exe** -> **Run workflow**, or
- push a tag such as `v1.0.0` to also attach the zip to a GitHub release.

The workflow runs the tests, builds `FM24CAGrowth.exe` with PyInstaller, and
uploads `FM24CAGrowth-windows.zip`. The zip contains the exe plus
`offsets.toml` and `config.json`; keep those next to the exe because the app
reads them from its own folder and writes `config.json` there.

To build locally:

```powershell
python -m pip install pymem "pyinstaller>=6.22"
python scripts/build_exe.py
```

PyInstaller 6.22+ bundles Tcl/Tk 9 data from Python 3.15 automatically. The
script excludes unused standard-library modules (about 11 MB output instead of
15 MB). The workflow uses Python 3.15 and the same script, so local and CI
builds stay identical.

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
      record + 0              -> record type tag (selects the layout)
      record + ca / pa        -> current / potential ability (u16)
      record + layout offset  -> person sub-object
      person + short_name / first_name / last_name -> name string
      person + birth_doy / birth_year -> birth date
      exe + game_date.rva     -> in-game date for age

      record + positions      -> one byte per position (15+ = can play)
      record + ca             -> write u16 current ability (monthly growth)
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
| `src/fm24_lineup.py` | Best 4-3-3 lineup by CA/PA and positions |
| `src/fm24_best_eleven.py` | First and second XI with scipy assignment |
| `src/fm24_ca_growth.py` | Monthly CA growth (+2) for all controlled players |
| `src/fm24_ca_growth_gui.pyw` | Tkinter GUI for the CA growth watcher |
| `.github/workflows/build-exe.yml` | Build the Windows exe on GitHub Actions |
| `scripts/build_exe.py` | Local/CI PyInstaller build script |
| `src/fm24_memory.py` | Process access, low-level reads/writes, and pointer vectors |
| `src/config.json` | Growth settings: `monthly_gain`, `max_age`, and the linear `cap` |
| `src/fm24_config.py` | Load and validate `offsets.toml` and `config.json` |
| `src/offsets.toml` | FM24 memory offsets |
| `tests/` | Unit tests (no game process required) |

## Development checks

```powershell
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check .
```
