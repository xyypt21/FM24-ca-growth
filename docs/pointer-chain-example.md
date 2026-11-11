# Walkthrough

## fm24_manager.py

```text
fm.exe base
0x140000000
  + container_rva 0x6365118
  = 0x146365118
        read pointer -> 0x2D1EC5B0        manager container

0x2D1EC5B0
  + vector_off 0x18
  = 0x2D1EC5C8
        read pointer -> 0x1174C95A0        array begin
        read pointer -> 0x1174C95A8        array end at +0x8
        (end - begin) / 8 = 1              one human manager

0x1174C95A0
        read pointer -> 0xF7914FF0         human manager record

0xF7914FF0
  + person_off 0x450
  = 0xF7915440                            person sub-object

0xF7915440
  + uid_off 0x0C
  = 0xF791544C
        read u32     -> 0x77554264         manager UID = 2002076260
```

## fm24_team.py

```text
0xF7914FF0                              human manager record
  + person_off 0x450
  = 0xF7915440                          person sub-object

0xF7915440
  + contract_off 0xC8
  = 0xF7915508
        read pointer -> 0x108950890        contract

0x108950890
  + team_off 0x10
  = 0x1089508A0
        read pointer -> 0xFC221600         managed team

0xFC221600
  + club_off 0x30
  = 0xFC221630
        read pointer -> 0x76A6A630         club

0x76A6A630
  + teams_begin 0x18
  = 0x76A6A648
        read pointer -> 0x536C7B00         owned teams begin
        read pointer -> 0x536C7B20         owned teams end at +0x8
        (end - begin) / 8 = 4

0x536C7B00
        read pointer -> 0xFC221600         first team
        read pointer -> 0xFCEF0790         reserves
        read pointer -> 0xFC773FC0         U19
        read pointer -> 0xFCEF0F78         U18

0x76A6A630
  + linked_teams_begin 0x30
  = 0x76A6A660
        read pointer -> 0x67533850         linked teams begin
        read pointer -> 0x67533858         linked teams end at +0x8
        (end - begin) / 8 = 1

0x67533850
        read pointer -> 0xFC355818         B team

team UID reads
  0xFC22160C -> 0x00000398                 920
  0xFCEF079C -> 0x773B5FC9                 2000379849
  0xFC773FCC -> 0x7736A378                 2000069496
  0xFCEF0F84 -> 0x773B5FD4                 2000379860
  0xFC355824 -> 0x00371331                 3609393
```

## fm24_players.py

```text
team UID 920                            -> 0xFC221600 (see above)

0xFC221600
  + roster_begin 0x38
  = 0xFC221638
        read pointer -> 0xFA5C8870         player records begin
        read pointer -> 0xFA5C8940         player records end at +0x8
        (end - begin) / 8 = 26

0xFA5C8870
        read pointer -> 0x1038E63A8        player record (Leo Greiml)

0x1038E63A8
        read u32     -> 0x45A4E958         record type tag -> person at +0x278

0x1038E63A8
  + ca 0x200
  = 0x1038E65A8
        read u16     -> 136                CA
  + pa 0x202
  = 0x1038E65AA
        read u16     -> 136                PA

0x1038E63A8
  + person_off 0x278
  = 0x1038E6620                          person sub-object

0x1038E6620
  + first_name 0x58
  = 0x1038E6678
        read pointer -> 0xFAA6BA28         name holder
        read pointer -> 0xFFF9A1CC         string holder
        read u32     -> 0x00000003         length = 3 ("Leo")

0x1038E6620
  + last_name 0x60
  = 0x1038E6680
        read pointer -> 0xFB028AB8
        read pointer -> 0x1008D0FCC
        read u32     -> 0x00000006         length = 6 ("Greiml")

0x1038E6620
  + birth_doy 0x44
  = 0x1038E6664
        read u16     -> 184                day of year (2001-07-03)
  + birth_year 0x46
  = 0x1038E6666
        read u16     -> 2001               birth year

exe base 0x140000000
  + game_date.rva 0x631D5BC
  = 0x14631D5BC
        read u32     -> 0x07E9005B         in-game date 2025-04-01
```

A record whose type tag is not in `[player.layouts]` is not a player record and
is skipped. The short name is preferred when present; this player has none, so
the name comes from first name + last name.

The record type tag is the 4-byte tag at the start of the record. It is not a
pointer and not part of the person data; it selects the record layout:

| Tag | Meaning | Person offset |
|---|---|---|
| `0x45A4E958` | Normal player | `+0x278` |
| `0x45C7E798` | Player who is also staff | `+0x368` |

Any other tag (for example `0x45C7D028`) is not a player record and is skipped.

## fm24_ca_growth.py

Uses the player records from `fm24_players.py` and writes CA once per in-game
month:

```text
0x1038E63A8
  + ca 0x200
  = 0x1038E65A8
        read u16     -> 136                current CA
        write u16    -> 138                new CA (only when <= PA)

exe base 0x140000000
  + game_date.rva 0x631D5BC
  = 0x14631D5BC
        read u32     -> 0x07E9005B         in-game date; a new month triggers growth
```

The write is verified by reading CA back. Players whose `CA + monthly_gain`
(from `src/config.json`) would exceed the age cap are skipped, and CA is never
clamped. Preview and settlement lines show the player's age, PA, and cap. The
cap is linear: at or below `start_age` it is `PA × start_ratio`; between
`start_age` and `end_age` it interpolates towards `PA × end_ratio`; from
`end_age` up to `max_age` it is PA. Ratios are rounded to the nearest integer.
With `cap` `(18, 0.7) -> (22, 0.9)`, age 18 gives 0.7, age 20 gives 0.8, and
age 22 gains with cap PA. Players at or above `max_age` do not grow.

Save reload detection

When the game reloads a save, all memory addresses change, including the club
address. The watcher compares the club address on each loop iteration. When it
changes, the state resets to the current month without settling and the next
plan is previewed. Every settlement re-reads all roster, team, and player
addresses, so no address is cached across reloads.

## fm24_lineup.py

Reads one position rating byte per position from the player record. A rating of
15 or more means the player can play that position:

```text
0x1038E63A8                              player record
  + GK 0x208
  = 0x1038E65B0
        read u8      -> 1                  cannot play GK
  + DC 0x20B
  = 0x1038E65B3
        read u8      -> 20                 can play DC
  + ST 0x214
  = 0x1038E65BC
        read u8      -> 12                 cannot play ST
```

The lineup selector builds ACA and APA first XI, second XI, and third XI. The
first two come from the scipy assignment, best XI first and then the second XI
from the remaining players. The third squad fills depth targets (GK 2, DM 6,
DC 6, other positions 4) from the remaining players in descending metric order;
versatile players count for every position they can play. APA projects CA to
`max_age` with `min(PA, round(CA + monthly_gain * 12 * (max_age - age)))`; at or
above `max_age` it is CA. ACA is `max(CA, min(CA + 6 * monthly_gain, cap, APA))`,
or CA at or above `max_age`. `prepare_players()` drops loaned players and adds
the `aca`/`apa` fields for every squad; the reserve list is built by
`fm24_reserves.py`. Players on loan are excluded.

Loan detection compares two club UIDs with the controlled team UIDs:

```text
record + current_club 0x130 -> current club entry
contract + contract_club 0x10 -> owner club entry
entry + entry_struct 0x30 -> club structure
club + uid_off 0x0C -> club UID
```

If the current club is not controlled -> loaned out. If the owner club is not
controlled -> loaned in. Either way the player is skipped.

## fm24_reserves.py

Reads no extra offsets: it reuses the player records from `fm24_players.py` and
the squads from `fm24_lineup.py`. The cutoff comes from the ACA values of the
three ACA squads:

```text
ACA first XI + second XI + third XI  -> ACA values
P20 = linearly interpolated 20th percentile of those values
cutoff = 0.9 * P20
```

Players outside the three ACA squads whose `ACA >= cutoff` are kept and sorted
by ACA, highest first. Squad membership is compared by player record address, so
a copied player dict is still treated as selected. APA squad players are not
excluded, because only the ACA squads define the cutoff.
