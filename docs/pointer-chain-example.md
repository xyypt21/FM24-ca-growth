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
        read u32     -> 0x77554264         UID = 2002076260
```

## Read steps

| Code expression | Address read | Value read | Meaning |
|---|---|---|---|
| `base + container_rva` | `0x146365118` | `0x2D1EC5B0` | Manager container |
| `container + vector_off` | `0x2D1EC5C8` | `0x1174C95A0` | Array begin |
| `container + vector_off + 8` | `0x2D1EC5D0` | `0x1174C95A8` | Array end |
| `begin` | `0x1174C95A0` | `0xF7914FF0` | Human manager record |
| `person + uid_off` | `0xF791544C` | `0x77554264` | UID (`2002076260`) |

Note the difference between the last two rows:

- `manager + person_off` is arithmetic. It points at the start of the person
  sub-object; it does not read a pointer.
- `person + uid_off` is a real 4-byte read. The UID is stored inline, not behind
  another pointer.

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
python src/manager_uid.py
```

The UID should match the value printed by the walkthrough if you are in the
same save, but the addresses will almost certainly be different.
