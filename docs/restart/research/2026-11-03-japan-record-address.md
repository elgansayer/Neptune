# Japanese kernel record-address helper

This result continues the Japan T-14302G V1.000 kernel investigation. The input
is the unchanged 786,432-byte `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at the evidence-based candidate address `0x0600A000`. It is distinct from the
USA kernel and its mappings.

## Original-byte execution

Pinned disassembly identifies a compact helper at `0x0600AEF2`, with code range
`[0x0600AEF2, 0x0600AF04)` and a four-byte literal at `0x0600AF04` containing
`0x060BCEEC`. Its instructions load 88, spill MACL, multiply the signed low
words of `r0` and `r4`, sign-extend the low product word, add the literal base,
return in `r0`, and restore MACL in the RTS delay slot.

`tools/saturn_lab/probe_japan_record_address.py` maps only those original
instruction bytes, the original literal, and the exact four-byte stack slot at
`SP-4`. It rejects other reads, writes, or instruction fetches. Across 34
constructed values, each executed twice per run, the recovered result is:

```text
r0 = 0x060BCEEC + sign16(low16(sign16(r4) * 88))
```

Only `r0` and `r3` change among the general registers. SP, `r4`, SR and MACL
return to their initial values; the one stack write and read transfer the exact
MACL value. Each call executes nine original instructions including the delay
slot. The values `0..18` cover the directly useful record-index range and the
remaining cases exercise signed and wrap boundaries; this is not exhaustive
over all 32-bit inputs.

Two original-copy mutations are rejected: changing immediate 88 to 87 changes
the result for index 2, and replacing word sign extension with byte sign
extension also changes that result. The two successful private reports are
identical. Run 1 is
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-009/japan-record-address-run1.json`,
SHA-256 `39a8cad60727d86a794aa6b9cadc970329a7939326feb810c03e3079638f3e85`.
Run 2 has the same SHA-256. The focused four-test suite and full
`python3 tools/saturn_lab/check.py` suite (510 tests) pass.

## Original call-site continuation

A wider static window then found an indirect callsite at
`0x0600CC5C`: its literal at `0x0600CCA4` is `0x0600AEF2`, the delay slot at
`0x0600CC60` moves the preceding `r0` value into the callee's `r4`, and the
return path stores callback address `0x0600CB96` at the selected record's
offset `+12` in the RTS delay slot at `0x0600CC6A`. The preceding producer at
`0x0600A946` remains unvalidated.

`tools/saturn_lab/probe_japan_record_caller.py` executes those original caller
instructions together with the actual `AEF2` bytes. It maps the two exact code
ranges, three original literals, a two-word stack, and one 88-byte record. For
all 18 record indices, two executions in each of two byte-identical reports
run 17 original instructions, transfer MACL through the callee spill/restore,
return the record address, and perform only the original word store at
record `+12`. Three mutations are rejected: changing the call delay-slot
argument, changing callee stride 88, and changing the caller's store offset.

Run 1 is
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-010/japan-record-caller-run1.json`,
SHA-256 `e407ea8f80caebe4c9baae01b0e1501c16b82bb239b6a9c1a44ca7cbaa212ae4`;
run 2 has the same hash. The caller window is retained as
`analysis/japan-cc44-disassembly.txt`, SHA-256
`fa33999a5853d6426e9df74fc547dd4a233995b3dd1ab56c8ed39542a7c10874`.
The focused caller suite passes four tests; the current complete research suite
passes 514 tests.

This executes a real original callsite sequence under a constructed incoming
`r0`, stack return word, and record buffer. It does not execute the preceding
`A946` producer or demonstrate that the game naturally reached `CC5C`; BIOS,
device, timing, gameplay, and other caller semantics remain open.
The earlier failed attempts remain in `execution-006` through `execution-008`;
they are retained and are not counted as successful execution.

## Original record latch helper

Static decoding of the `A946` producer shows that it calls `AA34`, which scans
the 18-record table and reaches cache-through/VBR-backed services and an
original self-loop error path. The adjacent leaf at `0x0600AACC` is independently
bounded: code `[0x0600AACC,0x0600AAEA)` includes the `RTS` delay slot, and the
only literal is `[0x0600AB2C,0x0600AB30)` containing `0x060BCEEC`.

`tools/saturn_lab/probe_japan_record_latch.py` executes the original leaf over
all 18 valid indices with the record activity byte at `+80` both clear and set.
Each of 36 cases runs twice in each of two identical reports. Reads are limited
to the selected byte, literal, code and exact stack slot. Inactive records stay
unchanged; active records get longword `1` at the record base. MACL is restored
from `[SP-4]` in the return delay slot; the helper clobbers the T condition bit.
Two instruction mutations, inverted activity branch and changed latched value,
alter the resulting record state.

The successful reports are
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-011/japan-record-latch-run1-v2.json`
and `japan-record-latch-run2-v2.json`; both have SHA-256
`3366d8ca157abe4ca46e0112c8a907601b7169c56e986c2574cf109d02325f7a`. Each
contains 36 result rows and accounts for 72 original calls, with every
index/state pair run twice. The
first failed runs are retained in the same private directory: they exposed the
required return delay-slot mapping and T-bit clobber, and are not counted as
successes. The full research suite passes 516 tests.

This is an isolated helper contract with a constructed record table and flags.
It does not establish the `AA34` caller's device contract, a natural caller,
record lifetime, timing, or gameplay behavior.

The next static window covers the tail of the neighboring `AAEC` routine at
`0x0600A9E4` onward; its retained decode is
`analysis/japan-aa34-tail-disassembly.txt`, SHA-256
`a831d46a73a2feb40d1ac867e0f1fa86a41cc6b59cd5617330bc40d2dfa11f29`. The
original-byte listing places the real entry at `0x0600AAEA` (the decode starts
two bytes later) and its end at `0x0600AB2A`. It shows an 18-slot loop that
compares each record's byte `+81` to a stack-saved input, clears the matching
tag to zero, and calls `AACC` with the current slot index. The nested `AACC`
reads byte `+80` and sets the first longword to one only for an active record.

`tools/saturn_lab/probe_japan_record_tag_scan.py` executes the composed original
`AAEA` scan and `AACC` latch code with exact source ranges, one literal, an
18-record buffer, and a bounded stack. Its 39 scenarios cover every slot with
active and inactive flags, no match, three matches, and all 18 matches. Each
scenario executes twice in each report. The scan reads all 18 tag bytes in
order, changes only matching tag bytes and conditionally the matching first
longwords, and restores callee-saved registers, non-T SR bits, MACL, PR, and SP.
The full-match path executes 522 instructions, below the per-call 1,024-step
limit. Two original-instruction mutations are rejected: inverting the tag
branch and skipping the last slot.

Reports
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-012/japan-record-tag-scan-run1-v11.json`
and `japan-record-tag-scan-run2-v11.json` match at SHA-256
`0675cf60088e81723b16e90ae737edf28e0f8690a6495a119dc5e9c0b9b1a0e0`. These
are constructed CPU-only experiments; they do not establish natural caller
reachability, record lifetime, BIOS/device behavior, timing, or gameplay.
Probe source SHA-256 is
`8253afcd545e73dc93d3f913240ad626bfd6143a84cd56ec92636d62402b6a8f`. The full
research tooling suite passes 518 tests; this is separate from the original
execution evidence.

## Original Japanese context restore

Following the `AB78` static tail jump led to original code at `0x0600A186`.
The inspected range `[0x0600A186,0x0600A1AA)` contains 18 instructions
including the RTS delay slot. It reads exactly 12 longwords from a 48-byte
context, restores `r8`–`r15`, MACL, MACH, PR and `r4`, then the delay slot
overwrites `r0` with incoming `r5`. It performs no memory writes.

`tools/saturn_lab/probe_japan_context_restore.py` tests 31 distinct constructed
contexts twice in each of two identical reports. Each context contains distinct
patterns in the saved fields and uses the interpreter return sentinel as PR.
Two original-byte controls reject an altered `r8` offset and removal of the
return delay-slot move.

Reports
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-013/japan-context-restore-run1.json`
and `japan-context-restore-run2.json` match at SHA-256
`a1d0baa9373310749a7fc67705cba37ea2c86455c9b134e6f697861f908c676a`.
Probe source SHA-256 is
`579bfad6f0eb2e32c225f0d9b8369e5fd7f8fba38e56bb9daf5433d7aa40ba24`.
This confirms only the constructed leaf contract; it does not prove natural
task-switch reachability or live task-context lifetime.

The pinned decoder window at `0x0600B4EC` is retained privately at
`analysis/japan-b4ec-disassembly.txt`, SHA-256
`bdc400dad5a815dc45a5e32f2a57324278c1d211834054252cf94f23b5fff8e0`. It
continues the surrounding service and callback candidates but does not establish
the helper's natural callers. Local focused tests cover the probe's case,
range, and bound definitions; they do not execute or validate game behavior.

## Original Japanese record transition at ADB0

Static decode of the Japanese kernel places a second record transition at
`0x0600ADB0`, called by the `AAEA` tag scan. It compares signed `r4` against
18, uses the Japan literal at `[0x0600AF04,0x0600AF08)` for table base
`0x060BCEEC`, and indexes 88-byte records using the sign-extended low 16 bits
of the signed-word product. For a selected record, it reads byte `+80`. If that
byte is exactly 1, it changes it to 2, clears byte `+81`, and returns zero;
otherwise it returns `0xFFFFFFFF`. The routine spills MACL at `[SP-4]` and
restores it in both RTS delay slots. The bound is signed 32-bit, so negative
indices also pass that comparison; this experiment does not model their
out-of-table memory effects.

`tools/saturn_lab/probe_japan_record_transition.py` maps only the original
instruction range and literal, plus one constructed 88-byte record and the
exact four-byte stack slot. It executes every index 0–17 against activity
bytes 0, 1, 2, 3, and 255 and four tag-byte values (360 cases), retaining exact
instruction paths, memory transactions, record state, MACL and stack evidence.
The signed upper-bound refusal at index 18 is included in an original
instruction mutation control. The controls alter the bound branch, active
comparison, and stored transition value; all three are rejected. The full-match
scan that calls this helper is a separate probe and does not make these
constructed calls natural.

The paired reports under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-016/`
are byte-identical at SHA-256
`11643ddedfc846bc7e22087cf82eb2c1dcb4c35ec15bd7085142a39f5fcced7a`.
Each has 360 original calls, a maximum of 24 instructions per call, and three
non-budget mutation controls. The Japan kernel SHA-256 remains
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`; source
code SHA-256 is `9ccfcdb76cd0a080e6824c99457713e1d9297df632f30d819d1a5380ef682591`,
literal SHA-256 is `467250026107641638b8e76ad43aaf4a5e5e765762adb4d0516bac605166bc2c`,
and probe SHA-256 is `80bb9e8894dfbd2ab0ce136c75363e730d6defd44d6468136e4f4413bf390202`.
The report does not
establish negative-index memory behavior, natural caller/runtime behavior,
device or BIOS semantics, timing, gameplay, or independent-emulator agreement.
The repository research suite passes 522 tests; that count is separate from
original execution evidence.

## Limits and continuation

These results establish bounded original SH-2 helper and constructed
caller/callee contracts under the pinned `saturn-recomp` interpreter. They do
not establish natural call frequency, record lifetime, device or BIOS
semantics, hardware timing, a complete kernel map, other Japanese modules, or
gameplay. Continue with the original caller graph and the separate Japanese
startup path at `0x0600A312`, retaining the VDP2, DVCR, BIOS, and SCU
side-effect requirements. The all-code and all-assets programme remains active
and incomplete.
