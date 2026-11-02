# Original USA memory helper and direct caller: isolated execution

Issue [#591](https://github.com/elgansayer/Neptune-Bomberman/issues/591), under
#483/#480/#482/#464. Two new entries were executed against the accepted original
USA kernel on the VPS. This result continues beyond the separately owned #590
B934 experiment; it does not complete any parent programme.

Both fresh runs passed **1,980 constructed cases**: 180 at `0x0600A3E0`, and
1,800 at its direct caller `0x0600A3FA`. Complete reports are byte-identical,
SHA-256 `cc73feaa8d8f757ddea6dbf9b673a667c4e0612de310e1fe51393e4508101496`.
The [derived receipt](../evidence/2026-11-02-original-position-bounds.json)
retains source/tool/range hashes, controls and the results digest. Complete private
reports are `/home/dev/neptune-research-private/591/position-002/run{1,2}.json`;
`position-001` retains the earlier smaller passing experiment unchanged. Host
supervision scripts/logs are `/home/dev/neptune-evidence/code591-20261102/`.

## Source and original paths

Identity: USA MK-81070 V1.003, original `BOMSS/0KRNL.BIN`, 786,432 bytes,
SHA-256 `20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`,
load base `0x06006000`, SH-2 address space, resident-kernel mapping. Master/slave
CPU assignment and natural residency/caller observations remain unvalidated.
The experiment checks the existing SHA-1 and three interpreter source hashes at
`saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9` before execution.

| Entry | Original file extent, exclusive end | Classification | SHA-256 |
| --- | --- | --- | --- |
| `0x0600A3E0` | `[0x43E0,0x43FA)` | 13 executed instruction halfwords | `f4db5f0035bc8e740000b0ab9df034fd727414afd2771e7f2113d98fb745ef18` |
| `0x0600A3FA` | `[0x43FA,0x444A)` | 40 caller instruction halfwords; execution also visits the helper | `48528755e85f60809e9b87d09f763df456150be623e6e954b72f52b29415519c` |
| `0x0600A4D4` | `[0x44D4,0x44D8)` | caller's four-byte literal, value `0x060C381C`; not instructions | `4efc0b67133675678d80a9844fa616851f502bb3611a3f481a225638ddf001cd` |

A bounded original caller path was actually executed: caller `0x0600A41E` uses
BSR, its `0x0600A420` delay slot supplies the record pointer, helper RTS at
`0x0600A3F6` executes the store at `0x0600A3F8`, and returns to `0x0600A422`.
Caller RTS `0x0600A446` restores r14 in its `0x0600A448` delay slot. Each caller
case executes 53 instructions including all delay slots. The helper uses 13.
These are interpreter instruction counts, not Saturn cycles or game ticks.
A second BSR lead at `0x0600A46E` is statically found but not executed here.
Scanning aligned halfwords for branch encodings does not classify every byte as
code or enumerate indirect targets. No direct BSR/BRA lead to A3FA was found;
its entry remains a static boundary plus constructed-call execution identity.

## Recovered memory and argument contracts

For the helper, r4 is an explicitly initialized record pointer, r5 a descriptor
pointer, and r6 a 32-bit scalar. `s16`/`s8` mean signed loads; `u16` means
truncation on the store. The exact observed byte operations are:

```text
x = s16(record[16:18])
record[20:22] = u16(x - r6)
record[24:26] = u16(x + s8(descriptor[0]) - s8(descriptor[2]) + r6)
```

The record is read at +16 twice; descriptor bytes +0 and +2 are read once.
Only those two halfwords are written. r0 and r3 change in the sampled states;
all other initialized general registers, SR, MACL/MACH, PR, GBR/VBR and SP are
preserved. The stack is deliberately unmapped for this helper. No return-value
meaning is assigned to the final r0 value.

The direct caller accepts r4=index, r5=descriptor, r6=vertical scalar,
r7=horizontal scalar. Its original literal selects:

```text
record = 0x060C381C + u16(84 * index)
horizontal = s16(r7)
vertical = s16(r6)
```

It invokes the original helper for the first axis using `horizontal`, then
performs the analogous second-axis operations using record +18, output +22/+26,
descriptor +1/+3 and `vertical`. Both scalars pass through halfword stack slots:
this caller's contract differs from calling the helper with an arbitrary full
32-bit scalar. Sampled changed general registers are r0, r3, r4 and r6. r5,
r7–r14, SR, MACL/MACH, PR, GBR/VBR and SP are preserved in these states.
It spills/restores r14, r13, PR and MACL and reserves eight local bytes, for a
24-byte stack extent. Exactly four longword spill stores and two halfword local
stores occur, besides the four record stores. The saved spill values remain in
the stack after SP restoration; no claim is made that stack contents are restored.

The names “position” and “bounds” describe the upstream lead and arithmetic;
the gameplay/collision role is **not naturally validated**. Prior art is the
pinned [krnl.c](https://github.com/callumjenkins/pc-saturnbomberman/blob/c73bc117daec9f2dba4bf32cb08b5f0a91fb93a3/decomp/krnl.c)
helper hypothesis. The caller contract above comes from inspected original
instructions and the new original execution, not an upstream function name.

## Controlled memory, cases and rejection controls

Each case uses a fresh CPU and mapped-memory copy. Original instruction/literal
bytes stay unchanged. Record bytes, four descriptor bytes and caller stack are
explicit constructed test inputs, not a captured original RAM state. Where the
selected record overlaps the original file's mapped extent, the harness carves
out that 84-byte data region without overlapping mappings. Everything else from
the file remains mapped read-only by the write guard. Additional mappings contain
only the specified record/descriptor/32-byte caller stack, with no device RAM.
Every mapped byte outside the declared output fields/stack store bytes must equal
its pre-call baseline; every record byte must match a separately implemented
byte-oriented contract, including unchanged fields. Any extra/missing/repeated
write, unexpected register change, unmapped access, escaped PC, failed return or
128-instruction overflow fails. All writes are logged with address and width.

The leaf tests the complete 5×4×9 constructed product: halfword values
0/1/0x7FFF/0x8000/0xFFFF; four descriptors containing positive/negative byte
boundaries; and deltas 0/1/0x7FFF/0x8000/0xFFFF/0x10000/0x7FFFFFFF/
0x80000000/0xFFFFFFFF. The caller repeats all 180 cases for indices
0/1/127/255/780/781/0x7FFF/0xFFFF/0x10000/0xFFFFFFFF. This exercises record-offset
wrap and scalar narrowing, not a valid gameplay index domain. Other record and
register states, pointer aliasing and all possible input combinations are untested.

Mutations alter a private in-memory copy, never the source file:

| Original instruction mutation | Rejected / tested | What failed |
| --- | --- | --- |
| helper subtraction → addition | 100 / 180 | independent output-byte comparison |
| helper return delay store → NOP | 180 / 180 | independent output-byte comparison |
| helper RTS → self loop | 180 / 180 | 128-instruction bound |
| caller offset truncation → NOP | 27 / 45 | unmapped record reads for overflowing cases |
| caller final vertical store → NOP | 45 / 45 | independent output-byte comparison |
| caller delay-slot r14 restore → NOP | 45 / 45 | register/SP preservation guard |

Unchanged-result cases for a particular mutation are retained; a control must
reject at least one meaningful selected case, not every possible argument.
These controls and the byte contract detect semantic mistakes, but use the same
pinned CPU lineage. Independent emulator/hardware and natural gameplay validation
remain required before broader fidelity claims.

## Reproduction and publication boundary

After existing host admission, using fresh report names:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_position_bounds.py \
  --kernel /home/dev/neptune-research-private/483/0KRNL.BIN \
  --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --report /home/dev/neptune-research-private/591/NEW-position-run1.json
# Repeat with NEW-position-run2.json, then cmp both complete files.
python3 -m unittest discover -s tools/saturn_lab/tests -p test_probe_position_bounds.py -v
python3 tools/saturn_lab/check.py
```

Source execution head `efea635769ebaf8d1dc1216fd19df128b0c982ae`, intake base
`abc6dfa`. Actual supervision used the installed process guard and existing host
gate, current configured shared host limit 3 (read, not changed), a 180-second
lease and per-command timeout 60 seconds. Read-only source/input and hidden
broker-authority assertions passed. Each original run completed in under
20 seconds. No model calls, purchases, allowance changes, daemon start or lease
cleanup of another owner occurred. Existing account/CI spend remains unknown.

Eight owned synthetic tests exercise selection, signed/truncated byte results,
immutable private output and wrapper failures. The 148-test input-tooling suite
passed. Those tests establish tooling behavior, not the original-game result.
CI must still pass against the exact publication head/current base.

New status: two original entries disassembled, memory semantics reconstructed
for stated inputs, isolated-original-byte tested, with a constructed direct caller
path. Natural-runtime-validation, Godot parity, sound/DSP/overlay code and complete
programme/function/dynamic-target denominators remain open/unknown. Next bounded
code targets are the adjacent split-halfword add helpers `0x0600A25E` and
`0x0600A2D8`; continue without taking #590 or Gemini #487's owned work.
