# Pointer Chain Example

The chain is easier to read when each step shows the address being read, the
value stored there, and what that value means.

The values below come from one live FM24 session. Addresses change every time
the game starts; the offsets in `src/offsets.toml` are the stable part.

## Walkthrough

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
```

## Read steps

| Code expression | Address read | Value read | Meaning |
|---|---|---|---|
| `base + container_rva` | `0x146365118` | `0x2D1EC5B0` | Manager container |
| `container + vector_off` | `0x2D1EC5C8` | `0x1174C95A0` | Array begin |
| `container + vector_off + 8` | `0x2D1EC5D0` | `0x1174C95A8` | Array end |
| `begin` | `0x1174C95A0` | `0xF7914FF0` | Human manager record |
| `person + uid_off` | `0xF791544C` | `0x77554264` | Manager UID (`2002076260`) |
| `person + contract_off` | `0xF7915508` | `0x108950890` | Contract |
| `contract + team_off` | `0x1089508A0` | `0xFC221600` | Managed team |
| `team + club_off` | `0xFC221630` | `0x76A6A630` | Club |
| `club + teams_begin` | `0x76A6A648` | `0x536C7B00` | Owned teams begin |
| `club + teams_begin + 8` | `0x76A6A650` | `0x536C7B20` | Owned teams end |
| `club + linked_teams_begin` | `0x76A6A660` | `0x67533850` | Linked teams begin |
| `club + linked_teams_begin + 8` | `0x76A6A668` | `0x67533858` | Linked teams end |

Note the difference between pointer reads and arithmetic offsets:

- `manager + person_off` is arithmetic. It marks where the person sub-object
  starts; it does not read a pointer.
- `person + contract_off`, `contract + team_off`, and `team + club_off` are
  pointer reads. The value stored at that address is the next object.
- `person + uid_off` and each `team + uid_off` are real 4-byte reads. The UIDs
  are stored inline, not behind another pointer.

## Team UIDs

The club points at two arrays. `teams_begin` holds the first team, reserves, and
youth teams. `linked_teams_begin` holds linked teams such as the B team.

| Team address | UID address | UID |
|---|---|---|
| `0xFC221600` | `0xFC22160C` | `920` |
| `0xFCEF0790` | `0xFCEF079C` | `2000379849` |
| `0xFC773FC0` | `0xFC773FCC` | `2000069496` |
| `0xFCEF0F78` | `0xFCEF0F84` | `2000379860` |
| `0xFC355818` | `0xFC355824` | `3609393` |

## Why there is an array

The manager container does not store the manager directly. It stores a
begin/end pair for an array of manager pointers:

```text
begin = 0x1174C95A0
end   = 0x1174C95A8    (difference 8 bytes = one element)
```

The human manager is `begin[0]`. Reading that element gives the manager record
address `0xF7914FF0`.

## Try it yourself

```powershell
python src/fm24_manager.py   # 2002076260
python src/fm24_team.py      # five team UIDs, one per line
```

The UIDs should match the values printed by the walkthrough if you are in the
same save, but the addresses will almost certainly be different.
