# Original kernel record markers, flag clears and complete callers

Issue [#629](https://github.com/elgansayer/Neptune-Bomberman/issues/629) continues
#483/#480/#464. Original SH-2 entries6B38/6B56 and940A/942E now pass **18,722
constructed cases twice**, partitioned into four immutable report pairs. Actual
callers process all18 records and all16 helper calls. All ten altered-original
instruction controls are detected. [Derived evidence](../evidence/2026-11-02-original-kernel-records.json).

## Source and recovered effects

USA MK-81070 V1.003 `BOMSS/0KRNL.BIN`,786,432 bytes, SHA256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`,
SH-2 mapping06006000, resident-kernel lifetime. Full SHA256/SHA1 and all three
pinned interpreter sources are checked before execution. The source remains
unchanged. Constructed records/global byte/stack are explicit data overlays;
original executed instructions and literals remain protected.

Entry06006B38 selects an88-byte record at
`060BC190 + signed16(low16(88 * signed16(r4)))`. The upper16 argument bits do not
participate. In particular372*88 still fits positive16 bits, whereas373*88
becomes a negative displacement. This is not an untruncated32-bit index product.
The original reads byte+80. If nonzero, it writes big-endian long1 at record+0;
otherwise it does not write the record. MACL is saved before the multiply and
restored in the actual RTS delay slot. R0 becomes80, R2 the record base, R3 zero
or1, R4 the selected pointer, and T reflects whether the flag was zero. Other
visible state is checked, including restored SP/MACL and preserved PR.

Actual caller06006B56 scans **18 records**. It compares the unsigned byte+81
with the full32-bit argument saved on its stack. High argument bits are not
discarded: FFFFFFFF does not match categoryFF. On each match it clears byte+81,
then calls the unchanged6B38 helper, passing the zero-based index in the original
BSR delay slot. Thus category clearing occurs even when byte+80 is zero, while
the long1 mark still depends on that separate flag. All18 matches/calls, zero
matches and mixed active/category masks are tested. The BF/S record-pointer
increment executes on the final iteration too. R11..R14/PR are restored; nested
MACL saves, argument storage and all28 actual stack bytes are checked. The final
loop comparison sets T=1. Remaining register clobbers are compared exactly.

Entry0600940A returns immediately on argument0, without reading a slot or count;
it leaves the initialized R0 unchanged. Otherwise it selects
`060CE060 + (16*(r4-1) modulo2^32)`. If byte+11 is zero, it returns without
touching the count. A nonzero flag is cleared, then byte060BF4A0 is decremented
modulo256. There is no clamp at zero. The byte load into R2 is signed: counter80
followed by subtraction produces registerFFFFFF7F while storing byte7F. R4 can
end at the selected record or at the count address. T distinguishes the zero/
nonzero predicates. These effects and every other visible register are checked.

Actual caller0600942E calls940A for **all16 indices1..16**, passing each index in
the original BSR delay slot. The counter decreases once per initially nonzero
flag, including wrap; zero initial count and16 active slots produce F0. All16
flags are cleared, and inactive/other record bytes stay unchanged. R13/R14/PR/SP
are restored, including R14 in the outer RTS delay slot. Final loop T=1; the
last helper's other register effects remain and are checked.

Names such as task/scheduler remain historical hypotheses, not established
natural roles. Out-of-pool indices are controlled arithmetic probes, not evidence
that the game naturally accepts them. These are four recovered CPU contracts
and two actual direct caller paths, not naturally captured gameplay or all kernel
code. XBAND/Japan mappings are not inferred from this USA source.

## Runtime comparisons and scope

| Original entry | Cases/run | Instructions | Data events | Maximum real helper calls |
| --- | ---: | ---: | ---: | ---: |
| 06006B38 |2,298|13..15|4..5|1|
| 06006B56 |2,112|198..540|48..156|18|
| 0600940A |4,072|4..18|0..6|1|
| 0600942E |10,240|281..377|38..102|16|

The selection includes all flag/counter byte values,372/373 and other signed/
wrapping index boundaries, selected full32-bit filters, every single active/
matching position, dense/sparse masks and two distinct register/SR/MACL states.
It is not every machine state. Each executed PC and delay-slot marker, every
read/write address/width/value/order, all16 general registers plus PC/SR/PR/
MACL/MACH/GBR/VBR, all controlled canaries and protected original bytes are
compared against the independent byte/register model.

The wrapper distinguishes opcode fetch from data reads, rejects cache-through
aliases and arbitrary code-as-data, and permits only declared data/stack writes
and the three inspected literal addresses. It reuses the accepted mapping helper
and hash-pinned CPU; earlier adapters/limits and native caches remain unchanged.
No device register is flattened into RAM and no call is replaced with a stub.

A real full18-call attempt with a128-instruction request stopped before the
129th instruction executed: trace length128, CPU attempted-step counter129,
40 events and `Local instruction budget exceeded`. It is retained explicitly as
`completed_original_call:false`. Full runs use the new function-local1024 bound;
the maximum observed540 instructions completes. No host/provider limit or CPU
implementation was changed. The short rejection is not counted as a success.

| Altered original instruction | Rejected/tested |
| --- | ---: |
| remove signed index truncation |1/66|
| remove conditional marker store |65/66|
| remove MACL delay-slot restore |66/66|
| omit unsigned category extension |29/64|
| scan17 instead of18 records |64/64|
| omit caller's index-setting delay slot |34/64|
| omit slot flag clear |61/65|
| increment instead of decrement count |61/65|
| call15 instead of16 slots |64/64|
| omit outer R14 delay-slot restore |64/64|

Unaffected mutation cases remain recorded. Positive kernel bytes stay unchanged;
altered copies/hashes remain separate. The248 research tests and14 catalogue
tests passed before integration; the current full research suite has253 passing
tests after the coordinator's disjoint paired-table work. Source-only CI also exercises the actual pinned CPU/adapter using
owned instructions, explicitly no game bytes; its evidence remains separate
from these original runs.

## Retained reports and continuation

| Family | SHA256 of either complete report |
| --- | --- |
| marker |`3bbd9ee74675b63edda47211c6474074e551cb2d03113afc3123c0ace1ef8ac1`|
|18-record caller|`f6d81b6241bb1b6ed9c3dfdfbd8bb381634d67f9fe3b141447e9305d91ed01cb`|
| flag-clear helper |`e309f57a7e2452bddfd53b0f72f990c9a04ffa05ae18beca075dbf06fe9b4625`|
|16-call caller|`70671a56d91465e7f1d23ce143399ebe11162308dad6aad3bbfbc4fae1222941`|

Original execution head0e458325c794a96837e38e90480b9749a3daf36e; probe SHA256
33f929226175dc00195ea0609c3e2658f70b27c659922d6b9f802e61d78034d3.
Private pairs are under `/home/dev/neptune-research-private/629/kernel-records-bprrbpow/`,
with family directories `mark`, `mark-all`, `clear`, `clear-all`. The short proof
is in `mark-all/short-caller-proof.json`. Supervisors/logs are in
`/home/dev/neptune-evidence/code629-20261102/`.

The earlier120-second admission denial and its zero-original-execution record
remain at629/kernel-records-ni0yxfie. Foreign owners released/replaced their
leases normally; nothing was cleared, adopted or stopped. Actual admission read
the existing shared limit3; each own family lease180 seconds was released.
Commands retained60-second deadlines, nice10 and downward-only2GiB address-space
caps. Code/original/interpreter mounts were verified read-only and broker
authority hidden. No provider/model call, scheduler, allowance reset, continuity
activation or paid fallback; other owners preserved, account/CI spend unknown.

After existing admission, use two fresh reports per family:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_kernel_records.py \
  --kernel /home/dev/neptune-research-private/483/0KRNL.BIN \
  --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --kind mark-all --report /home/dev/neptune-research-private/629/NEW-mark-all-run1.json
```

Continue surrounding allocation/record initialization, actual natural callers
and further loader/scheduler/slave/overlay/library code. Nontrivial sound handlers,
observed DSP, menu/save/network/Japan code, independent-engine/hardware/audio
validation and whole executable/function/dynamic-target denominators remain open.
The all-original-code programme stays active and incomplete.
