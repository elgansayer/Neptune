# Japanese A61B0 snapshot-service execution

This result continues the original Japan kernel probe at `0x060A61B0`. The
kernel is the private, unchanged `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`. The executed original range is `[0x060A61B0,0x060A6280)`.

## Composed bounded execution

The probe executes A61B0 with the frame-1200 WorkRAM-H image and its captured
service stubs/tables, plus matching BIOS 1.01 Japan ROM bytes. The save state is
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`; the
normalized WorkRAM-H image is
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`. The
BIOS is SHA-256
`dcfef4b99605f872b6c3b6d05c045385cdea3d1b702906a0ed930df7bcb7deac`.
These are distinct source classes: original game instructions, captured
runtime snapshot bytes, and BIOS ROM table data. The snapshot does not prove
that its service stubs were naturally executing at frame 1200.

Six constructed cases (R4 index 0–2 and two register seeds) each ran twice with
byte-identical paired reports. Index 0/1/2 selects service 75/74/73 and stores
the corresponding original game handler at `0x060A62D8`/`0x060A6348`/
`0x060A63B8` into the system table. The matching BIOS vectors at `0x2000072C`,
`0x20000728`, and `0x20000724` are copied to the corresponding VBR slots.
Each case publishes the old system/vector values and flag in the original
globals, writes `0x101` as a D0EN intent at `0x25FE0010 + 32*index`, restores
SP/PR and non-T SR fields, and returns. The typed sink records the D0EN write
intent only; it models no SCU effect.

The paired private reports are in `execution-144` and have identical
SHA-256 `dab7f885a8c94066c18485ca00b327d0db1684f4d7add72e7373fec455c2fcdc`.
Their ordered result digest is
`905aa08c5c13cdd45c0f87569a48b4720e7cdcfeddf3e3700b7f7b9aaffc02c6`.
Three selected BIOS-vector mutation controls changed the final VBR writes and
were observed. Executed source bytes hash to
`86b2224c493286772681c353a12de5e2a46f0748e87dbe0fed5680d715f436c0`; the
probe hash is
`4d29f033fa6a8d65623f8dda1c26d1aef4ea83b46aba2141224f045f42873be3`.

This is interpreter evidence for a bounded original routine under a
constructed entry ABI and snapshot-provided service implementation. It does
not prove natural caller or runtime-PC behavior, BIOS implementation, SCU
effects, complete kernel recovery, or full asset extraction. Continue into
A61B0's callers and adjacent original functions with the same source and
execution distinctions.
