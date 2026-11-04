# Japan A208 to AE3A scheduler edge

The probe begins at the original indirect callsite `0x0600A208`. Its JSR target
comes from the original literal at `0x0600A2CC` (`0x0600AE3A`), and the JSR
delay slot loads the task cursor from captured WorkRAM-H address `0x060BCC80`.
Original AE3A then reads the 18-row table pointer literal, the VBR-selected
cache-through pointer, and row state byte `+83`. Execution stops at the first
ACE8 target after recording the original call's delay-slot value.

Two VBR slots and two independent register seeds produced four original-byte
runs. The captured task cursor is row 0 and its `+83` byte is nonzero. VBR slot
0 selects row 0, so AE3A writes marker `+81=4` and reaches ACE8 with R4=0. Slot
1's selected pointer is zero, so it takes the other path and reaches ACE8 with
R4=1. The prologue's seven stack stores, caller PR save, row marker effect, and
both ACE8 call return addresses are checked. An AE6C `BF` to `BT` mutation
changes the matching-row edge and is rejected.

Reports from independent executions 287 and 288 are byte-identical, SHA-256
`ffbdb34f270f29d7c5fe40894c12b7759a810b723a3a09e831f1cf3fe73d097b`, each mode
0600. The probe source SHA-256 is
`c8146a2403eae4b3762735ec10947426d4316ac4dfd2d96a45798fb11d9e967a`. Failed
harness attempts 284–286 are retained privately.

The source is the original Japan T-14302G V1.000 KRNL (`0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`) mapped at
`0x0600A000`. The WorkRAM-H base, task cursor, table, row marker, and VBR
selection come from the captured frame-1200 state; remaining registers and
stack are constructed. The probe stops before executing ACE8, so it does not
prove a complete scheduler cycle or natural gameplay timing. Continue by
composing the captured path through ACE8/A164/A186 and tracing the A208 caller's
F040 continuation. Full code and asset recovery remains active and incomplete.
