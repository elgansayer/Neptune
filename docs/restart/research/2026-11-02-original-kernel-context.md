# Original SH-2 context save and restore

Issue [638](https://github.com/elgansayer/Neptune-Bomberman/issues/638),
[PR639](https://github.com/elgansayer/Neptune-Bomberman/pull/639),
EXP-SAT-CODE-018. **All-original-code programme active, incomplete.**
Original KRNL routines 060061C4..060061E6 and 060061E6..0600620A completed
456 selected cases each, twice, with identical complete report pairs. These are
selected CPU contracts, without natural caller/scheduler or timing validation.

USA MK-81070 V1.003 resident KRNL, SH-2 mapping 06006000, kernel SHA256
20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7.
Original execution head e7e5dffc5f10881081c49bf606bc4030e68c23e5.
The [derived evidence](../evidence/2026-11-02-original-kernel-context.json) pins
all imported adapters and the three historical CPU sources at saturn-recomp
f20de940e8013fc84103a5b39c4069ed8071b1f9. No CPU implementation or game binary is
bundled. The [probe](../../../tools/saturn_lab/probe_kernel_context.py) compares
all visible registers/SR, exact PC/delay paths, transactions and every controlled
context/canary and unaffected original byte.

## Recovered layout and effects

Both entries take the context address in R4. Save writes the following 48 bytes:

| Offset | Saved value |
| --- | --- |
|0|R8|
|4|R8, again|
|8..28|R9..R14, consecutive words|
|32|R15/SP|
|36|PR|
|40|MACH|
|44|MACL|

Save executes 17 instructions and 12 writes. It returns R0=0 in the actual
RTS delay slot at 61E4; all other visible registers and SR remain unchanged.
The duplicated R8 is original behaviour, not an assumed standard library ABI.

Restore executes 18 instructions and 12 reads. It loads R8..R15 from +4..+32,
MACL from +44, MACH from +40, PR from +36, and R4 from +0. Its RTS uses the
loaded PR, with R5 copied to R0 in the actual delay slot at 6208. Other registers
and SR remain unchanged. The context is readonly throughout restore. Saved SP
is loaded as a register value; this routine never dereferences it, so no backing
RAM is invented for arbitrary sampled SP values.

The ordinary pinned `CPU.call` resets PR before entry. This experiment instead
uses a small entry driver which preserves PR and delegates every instruction to
the unchanged pinned `step`/`exec`/`fetch`. Before every selected restore, PR differs
from the saved return target; all eight restored R8..R15 also differ from their
entry values. Thus omitted restores cannot hide behind matching initial values.
The only accepted return target is the fixed non-executable FFFFFFF0 sentinel.
Arbitrary restored executable targets and natural task switching are not proven.

## Actual evidence and regression controls

| Entry | Cases/run | Instructions | Data events | SHA256 of either complete report |
| --- | ---: | ---: | ---: | --- |
|61C4 save|456|17|12|6723e27aca27ed27ac4000420c7fef8f40e2683844428c30a0cabdc61c3e96b2|
|61E6 restore|456|18|12|16e0a57bd7c18a4f25cfc5c211b2bdad2f788494a449bae634bef8533a2cede4|

Each entry covers 12 boundary words and 64 walking-one/complement vectors,
three canonical context positions and two SR/canary seeds. Context regions have
16 compared canary bytes on either side. Selected save PR and restore saved PR
are fixed to the sentinel; this is not exhaustive over all register states.

Seven altered-original controls were checked on 66 selected cases each:
wrong second R8 source rejected 55; displaced MACH store 66; missing save result
delay slot 66; missing restore SP 66; missing restore PR 66; missing R4 reload 66;
missing restore result delay slot 66. Removing PR restoration attempts an unknown
instruction fetch after the real RTS/delay slot and is rejected. Its first
failure includes actual PC, PR, registers, transactions and trace in the private
report. Every other control also retains its first rejection. No budget failure
is counted as semantic evidence.

Private final pairs and supervisor:
`/home/dev/neptune-research-private/638/kernel-context-y2u8xqk9/`, folders
`save` and `restore`, each with fresh `run1.json`/`run2.json`. Initial fixture
history remains at `.../638/kernel-context-f82j1jr9/`: it passed transactions,
but some saved/live values matched. Those reports were retained when fixtures
were strengthened; they are not extra recovered functions or a failed original.
Scripts and test logs: `/home/dev/neptune-evidence/code638-20261102/`.

Actual namespace receipts proved original/repository/interpreter readonly and
broker storage hidden. Four final workers exited 0 without timeout, cancellation
or output truncation. Shared host limit 3, own leases 180 seconds, commands
60 seconds/nice10, downward-only 2GiB address-space cap and the smaller local
64-instruction context cap were preserved. Own leases released. No provider/model
call, foreign lease change, scheduler, quota reset, continuity activation or paid
fallback. #536 remains open; account/CI spend is independently unknown.

The strict adapter and both prior probes remain byte-identical to accepted635:
sh2_profile SHA256 26c22576b6398b9f96a1f9b7a2407e4e400c634afcc82d3e916f6b99507087d5,
records SHA256 33f929226175dc00195ea0609c3e2658f70b27c659922d6b9f802e61d78034d3,
delta SHA256 0e23df8655b3b3d9478794f162745540bd790af6b685d761d123eaf01e4d55b7.
Context execution declares no aliases, no original literals, and only its selected
entry's code range. Authored-byte pinned CPU tests prove entry PR preservation,
explicit PR load/return, unknown-target/read/alias/write refusal, instruction cap
and fresh recovery. CI emits this evidence as no-original-game execution; it
does not substitute for the four original reports. Source-only CI
[41478704998](https://github.com/elgansayer/Neptune-Bomberman/actions/runs/41478704998)
passed the new driver smoke; artifact13158691870 and its digest are pinned in
the derived evidence. Local tooling tests passed263 tests and14 catalogue tests;
final CI repeats checks.

## Continue recovery

Next selected original entry is 6DC8..6DFE: apparent record-state transition with
a signed upper bound of 18, no lower-bound check, signed 16-bit multiplication
truncation, flag 1→2 and category clear. This remains a static hypothesis; derive
the negative/high-index and rejection paths before original execution.

The surrounding 6BE4/6D36 caller references this context pair and accepted6B9C.
Its VBR-bit10 indexed cache-through writes and context targets need a separate
explicit profile. No natural scheduler capture follows from isolated context
success. Continue loader/slave/overlay/library code, unresolved sound handlers and
DSP, menu/save/network/Japan paths and original natural callers. Whole executable,
function and dynamic-target denominators remain unknown; neither KRNL nor the
all-original-code programme is complete.
