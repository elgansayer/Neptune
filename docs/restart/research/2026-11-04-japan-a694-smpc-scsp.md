# Japan A694 SMPC and SCSP switch

## Original-byte execution

This direct-entry probe executes original Japan 0KRNL.BIN at A694 through its
RTS, and the A5CE longword fill helper used by mode 1. The kernel SHA-256 is
23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb; initial
WorkRAM-H is captured frame 1200, normalized SHA-256
3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff. Interpreter:
saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9.

Two reports in
/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-223/
are byte-identical. Each report SHA-256 is
f8703796c97daaac12feb48bdf36c721496672038a808e649eec214d51418b69; normalized
results SHA-256 is
a6023f42b2b853b4cbe746f3434272d6231fc16587b04f7a60622f03b7897560. Probe
SHA-256 is
f707d564a68cbb8c1cbb1629f913d46a2a58633e72995159e487a04bef53c0ab.

## Recovered switch behavior

Across four constructed R4 modes and two register seeds:

- Mode 0 emits SMPC COMREG command 7.
- Mode 2 emits SMPC COMREG command 6.
- Mode 1 writes byte 2 to SCSP control, writes 256 longwords of value 0x400
  across the 1 KiB region at 0x25A00000, then writes 0x0007FFFC at its base
  and 0x4E7160FC at DSP RAM 0x25A00400.
- Other tested mode 3 returns without device stores.

All SMPC and SCSP accesses are recorded as strict write intents. Mutation
controls reject a changed SMPC command address and a changed SCSP fill size.
Attempts execution-220, execution-221, and execution-222 retain the initial
stack-memory expectation and two mutation-control diagnostics; corrected paired
evidence is execution-223.

## Limits and continuation

The mode values and entry registers are constructed. This does not establish
that A546 selects these modes, SMPC protocol completion, SCSP effects, sound
timing, or audio output. The full A546 loop and original Japan/USA modules and
assets remain to be recovered.
