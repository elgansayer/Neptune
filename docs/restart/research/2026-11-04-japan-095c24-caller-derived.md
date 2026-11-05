# Japan KRNL 0x06095C24 caller-derived word probe

The original Japanese kernel helper at `0x06095C24` was run in isolation using
registers captured at the F040 diagnostic's call entry and the matching
frame-1200 WorkRAM capture. Eight cases (four constructed longwords at the
pointer in R2, across the two captured seeds) each execute 220 original
instructions. The helper reads and writes one longword, setting bit 31;
R0-R14, SP, and the observed stack window are preserved. It reads 52 data
items and writes six items per run, including five stack spill/restore pairs.

Two fresh runs produced byte-identical private reports with SHA-256
`8f74e5f7ce8b96df095944db3a68b9bf195c50b3d32f38066ae247bf08f44b34`. A
mutation replacing original instruction `0x06095C7E` (`0x2252`) with NOP
`0x0009` leaves the output at zero and fails the expected `0x80000000`
comparison. The data slice and caller state are tied to the retained frame
capture by hashes in the probe.

This is a bounded helper contract, not exhaustive 32-bit coverage or evidence
of a natural gameplay caller. The F040 run itself begins at a constructed
direct entry and its caller path remains incomplete. The routine's larger
caller purpose, hardware timing, other kernel functions, modules, gameplay,
audio, and all assets remain open. Private execution reports are retained
under `/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-332/`.

Reproduce with
[`probe_japan_095c24_caller_derived.py`](../../../tools/saturn_lab/probe_japan_095c24_caller_derived.py).
