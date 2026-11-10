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
