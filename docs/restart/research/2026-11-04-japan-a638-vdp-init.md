# Japan A638 descriptor and VDP1 transfer prefix

## Original-byte execution

The probe executes original Japanese `0KRNL.BIN` at WorkRAM-H `0x0600A000`
(786,432 bytes; SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`) from
`0x0600A638`. It includes the original fill helper A58E and halfword-copy
helper A5A2, returning through A5B4's RTS and delay slot at A5B6. The two
cases each execute twice against captured frame-1200 WorkRAM-H. The interpreter
is `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`.

Identical reports are retained under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-215/`.
Each report SHA-256 is
`dc9cf590c5edeae6e93ba2964de74cfb4d30abeaab269fe7f222f67ef084b87f`; normalized
results SHA-256 is
`2194710779af2154a59861161213353e72fd1d073fe4792186ca5a425e6e34bf`. The
probe SHA-256 is
`6fb9d9eea079368e5172cac90078bd9cae2a7d3d69c095cdf0f669e413f1adaf`.

## Recovered behavior

A638 zero-fills 96 bytes at `0x060BCE8C`, then sets halfwords at offsets 0, 20,
22, 32, and 64. The values observed are 9, `0x013F`, the current timing word
from `0x060BCE88`, 10, and `0x8000`. It then calls A5A2 with source
`0x060BCE8C`, destination `0x25C00000`, and byte count 96. The original helper
performs 48 sequential halfword stores through `0x25C0005E`; the probe records
these as VDP1 VRAM write intents and does not apply them to a hardware model.
Both entry R14 and PR are restored and SP returns to its input value.

Two original-source mutation controls reject a changed VDP1 VRAM base and a
changed `0x013F` literal. Initial attempts are retained in `execution-213`
(instruction ceiling reached before loop completion) and `execution-214`
(RTS delay-slot fence omitted A5B6). The corrected pair is `execution-215`.

## Limits and continuation

This is a direct constructed A638 entry, not an execution composed from the
A472 caller. The frame-1200 WorkRAM-H state is the initial memory; VDP1 VRAM
stores remain intents. It does not establish VDP1 hardware/display behavior,
natural startup timing, or the A638 caller's reachability. The next composed
range is the return to A4C8 and branch into A546; that loop calls additional
VDP1, SMPC, SCSP, and DMA helpers that require separate bounded contracts. The
full original-code and asset recovery programme remains active.
