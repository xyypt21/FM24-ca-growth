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

Build ACA and APA first/second/third 4-3-3 lineups from every controlled team
with scipy's assignment solver:

```powershell
python src/fm24_lineup.py   # one run, then exit
```

The sections are:

```text
ACA First XI / Second XI / Third XI
APA First XI / Second XI / Third XI
ACA Reserves
```

APA projects current CA to `max_age`; ACA adds six months of growth:

```text
age >= max_age: APA = CA
age <  max_age: APA = min(PA, round(CA + monthly_gain * 12 * (max_age - age)))

age >= max_age: ACA = CA
age <  max_age: ACA = max(CA, min(CA + 6 * monthly_gain, cap, APA))
```

After the three ACA squads, `ACA Reserves` lists every remaining player whose
ACA is at least 90% of the 20th percentile ACA of those squads:

```text
cutoff = 0.9 * P20(ACA of the ACA first, second, and third squads)
```

The reserve list is sorted by ACA, highest first. Players already in the three
ACA squads are excluded; APA squad players can still appear.

Example:

```text
ACA First XI
Slot Name                          Age  CA  ACA  APA  Positions
GK   Marius Müller                30.4 125  125  125  GK
DL   Thomas Ouwejan               27.2 123  123  123  DL/DM/ML/WBL
DM   Lewis Bate                   21.1 128  134  144  DM/MC
AMC  Assan Ouédraogo              17.6 127  127  180  MC/AML/AMC
ST   Keke Topp                    19.7 118  124  150  ST
...

ACA Reserves (>= 90% of 20% percentile = 104.2)
Slot Name                          Age  CA  ACA  APA  Positions
-    Paul Pöpperl                 20.8 104  111  122  AML/AMC/ST
-    David Mella                  18.6 109  109  144  ML/MR/AML/AMR
...
```

- `aca` ranks by six-month growth, `apa` by projected CA.
- `monthly_gain`, `max_age`, and `cap` come from `src/config.json`.
- The best XI is selected first, then the second XI from the remaining players.
- The third XI is filled from the remaining players, highest metric first, until
  these depth targets are met: GK 2, DM 6, DC 6, all other positions 4.
- A versatile player counts towards every position they can play, but joins the
  third squad only once.
- Positions are read from the player record (`>= 15` can play the slot).
- Players on loan (loaned in or loaned out) are excluded.
- The lineups are printed to the console; no files are written.

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
      record + current_club   -> current club entry
      contract + contract_club -> owner club entry
      entry + entry_struct    -> club; club + uid_off -> club UID (loan check)
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
| `src/fm24_lineup.py` | ACA/APA first/second/third lineups and the ACA reserve filter |
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
