# Walkthrough

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
