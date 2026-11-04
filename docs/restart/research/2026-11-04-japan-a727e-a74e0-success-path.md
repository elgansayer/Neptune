# Japan A727E/A6142/A74E0 success-path slice

## Original-byte execution

The probe composes original Japanese `0KRNL.BIN` bytes at:

- A727E handler `0x060A727E..0x060A72AD`
- A6142 status helper `0x060A6142..0x060A614F`
- A74E0 byte-copy helper `0x060A74E0..0x060A7505`

The retained frame-1200 state and kernel identities are checked before each
run, and the executing ranges and pointer literals match the captured original.
The pinned SH-2 interpreter records every instruction including call, branch,
RTS, and delay-slot instructions.

Thirty-four input combinations ran twice each in byte-identical private reports
under `/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-175/`.
The paired report SHA-256 is
`7e6196d7922f6e4f8fb8e1e041ae7deef62688ef10bc4015393d7e7ba65c1b34` and the
result digest is `8b9f63b27a0daaca01b028ccd7debb2158cb595a02a873db3cda4d547a9bbd6e`.
The concatenated source-range digest is
`5028f0bc0c704940910c40c04a745e5b15e91325e766dcab9b6c54a70de9d360`.

The constructed status word at `0xFFFFFF8C` separates both branches: values
0/1 make A6142 return zero and A727E return one; values 2/3 make A6142 return
two and take A727E's success route. Success-route cases execute A74E0 for each
length 0–3 and two source/destination word patterns. A74E0 loads one longword
from its staged source pointer, spills it to its stack frame, copies the
requested low-order byte count into the staged destination, then restores its
stack. Exact reads, writes, PC paths, return values, stack image, and all other
WorkRAM-H bytes are checked.

## Limits

The captured frame-1200 global block `0x060FCD30..0x060FCD3B` is zero. For
success-route cases, the probe stages the global layout produced by A717C and
uses constructed RAM source/destination words. It constructs MMIO status values
at `0xFFFFFF8C`; no hardware or emulator side effect establishes what the
original device returns there. This is a bounded success-path execution, not
natural A727E reachability, device semantics, or complete kernel recovery.

The earlier index-4 early-return result remains separately recorded in the
[dispatch result](2026-11-03-japan-kernel-dispatch-index4-early.md). Next trace
the real status source/device behavior and natural A727E/A7178 callers, then
continue further Japanese/USA functions and modules. The all-code and all-assets
objectives remain open.
