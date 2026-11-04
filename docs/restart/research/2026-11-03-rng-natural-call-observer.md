# Bounded native observer extension for RNG draw calls

This source change extends the existing matched Beetle/Mednafen master SH-2
observer from the already inspected table helper at `0x0600B934` to also accept
the inspected draw helper at `0x0600A0EC`. It does not claim a natural call has
been captured.

## Inspected source boundary

The original is the USA MK-81070 V1.003 `0KRNL.BIN`, SHA-256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`, mapped at
`0x06006000`. The draw entry `0x0600A0EC..0x0600A10E` has SHA-256
`de2d869392e860a358346b973f43e40070cc2ba7b6a7b0c0ecc2beada6d5afd4`; its nested
index helper `0x0600A08C..0x0600A0B4` has SHA-256
`21e8bd6d7c0b4fe77ae5b53b1181df88a8b36e734db870edd5919395273f107f`. The draw
entry begins with `sts.l MACH,@-r15`, then saves PR. It returns through RTS at
`0x0600A10A` with NOP at `0x0600A10C`; its inspected constructed-call execution
restored SP and MACH. See [the prior original-byte result](2026-11-03-rng-bounded-draw.md).

## Observer contract

The native observer still hooks only the pinned core's master SH-2 interpreter;
JIT mode is rejected. It accepts only `0x0600B934` or `0x0600A0EC`, stores at most
128 entry/return records, and bounds each pending call to 4096 master dispatches.
For A0EC it checks the entry opcode, root RTS address/opcode, NOP delay slot,
return PC, and restored SP/MACH. Each record contains all 16 registers and
SR/GBR/VBR/MACH/MACL/PR, including the caller's SP and PR. The observer does not
read game memory or copy stack bytes; this preserves the core's bus behavior but
does not by itself recover stack contents.

Only the owned C fixture has exercised the new A0EC observer state machine so
far. Its tests cover accepted/rejected target selection, the root RTS/NOP delay
slot, stack/MACH restoration checks and existing B934 behavior. They are tooling
tests, not original-game execution. The fresh pinned core build is deferred on
this VPS while free disk remains below the retained 6 GiB native-build reserve;
the existing CI provisioning job will compile and smoke-check the changed tool.
No original bytes, BIOS, disc image or save state is included in this change.

## Remaining work

The next experiment must capture a real A0EC entry and return, with repeated
reference/observer-disabled/observer-enabled windows and exact input/state/video/
audio comparisons. Current title-screen Start and A-button inputs have not
entered A0EC. Natural caller ordering, seed origin, full recurrence, wrap
semantics, regional differences and the remaining game functions/modules are
open. Issue #492 and the all-code programme remain active.
