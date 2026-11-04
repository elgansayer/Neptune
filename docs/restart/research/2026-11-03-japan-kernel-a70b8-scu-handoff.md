# Japanese kernel A70B8 to A6150 SCU write-intent handoff

This result uses original Japan `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Composed original-byte execution

The probe composes A70B8 `[0x060A70B8,0x060A7150)` with A6150
`[0x060A6150,0x060A61B0)`. A70B8 classifies a constructed pointer after masking
it with `0x0FFFFFFF`, builds its 40-byte descriptor, and publishes `1` at the
constructed global `0x060FB588`. It calls original A6150, which consumes the
descriptor and emits five SCU write intents (D0R, D0W, D0C, D0C+4 and D0C+12).
The CPU then stops at `0x060A7136`, before A61B0's BIOS calls, D0EN write and
interrupt-priority handling.

Forty pointer/R5/R7/seed cases ran twice. The paired private reports in
`execution-131` are byte-identical at SHA-256
`124fc1be9d7ade7d3e209d658ff04d784423c13554a570a58a73bfc1d719f683`; the
ordered result digest is
`cf23cc5dcccba2807965e2925fac52719e1a19fdbe500b128cd7636d9d182fca`. The
composed code and literal hashes are
`aa07ceaafe02e7bec24af3bd5f33b128b08dbebeae196ac51fbc12106fb2661e` and
`cd2c5c93273098fe5c39357bb72c3133888d9a4ea053ce0eda2f857e4face17c`. The
probe hash is
`c3a9eac890f3f5d0613c0bd47fb9b21ffc2bb7553af1f090bfb490b5ced0d27c`.

Changing A6150's D0R literal at `0x060A61EC` to `0x25FE0080` is rejected by
the composed intent comparison.

The MMIO sink records CPU write intents only; no SCU side effects or device
timing are modeled. The next A61B0 call is deliberately outside this execution.
Natural callers, BIOS behavior, DMA completion and gameplay remain open.
