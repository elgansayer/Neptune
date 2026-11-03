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

## Original Japanese startup counter at A5E4

The next startup decode from `0x0600A312` enters SH-2 SR/MMIO handling, calls
BIOS indirect services, and polls cache-through synchronization words. The
nearby helper at `0x0600A5E4` is a bounded leaf: it reads the Japan literal at
`0x0600A62C` (`0x060B3D40`), reads one 16-bit word, adds one, and stores the
low 16 bits in the RTS delay slot. It clobbers `r2`/`r3`; other GPRs and
special registers remain unchanged in the constructed CPU contract.

`tools/saturn_lab/probe_japan_word_counter.py` executes 520 cases over 0–255
and wrap/sign boundaries (`0x7FFF`, `0x8000`, `0xFFFE`, `0xFFFF`), each with
two register patterns. It checks the exact literal/global transactions, delay
slot write, 16-bit wrap, and register preservation. Three instruction/literal
mutations are rejected. Paired reports in
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-018/`
match at SHA-256
`d2c0e00dcb5aaf0813f8dbff8fee0eb3a10e8910fff6de0f0094cdf548a09a14`.
The probe hash is
`3c8c0c6b015a7ca86ec2d01ff31fe50eac0def14199535807a0284a21bd7dc96`;
original code and literal hashes are embedded in the reports. The A312 startup
decode and A492 tail are private static listings with SHA-256
`668d6570080c03a7fbbee5f4e6c72e4270a0bdf3b2d44fc611fffc285fe39887` and
`cf5e2f9539007d142ffd7c4eedba82309452288b2b05ffcf5c1504d186defed9`,
respectively. These do not substitute for runtime validation of BIOS, VDP,
SCU, or synchronization behavior. The full repository research suite passes
523 tests at that checkpoint; this is separate from original execution reports. The all-code
programme remains incomplete.

## Original Japanese context save at A164

The static task path identifies `0x0600A164` as the context-save counterpart
to the previously executed restore at `0x0600A186`. The exact range
`[0x0600A164,0x0600A186)` writes 12 longwords to a bounded 48-byte frame:
R8 is copied to both offsets 0 and 4; R9–R15 go to offsets 8–32; PR, MACH,
and MACL are written at offsets 36, 40, and 44. The write order is 0–32,
then 40, 44, 36. The RTS delay slot sets R0 to zero. This records the original
routine’s duplicate R8 stores without inferring why the caller uses them.

`tools/saturn_lab/probe_japan_context_save.py` executes 31 constructed register
patterns twice per case in each paired report. It checks all 12 writes and
their order, unchanged registers/special state, the return delay slot, and the
exact frame bytes. Two original-instruction mutations are rejected. The first
attempt is retained in `execution-019`; it exposed the non-offset-ascending
write order and is not counted as a successful run. Corrected reports in
`execution-020` match at SHA-256
`117795f538d5fb7bd28ea6f20b3ffd6fdfca7eab083ef94ca40c2386141826fe`.
Probe SHA-256 is
`0bccacf6b12c79e54a48a985fc1ee0f297acecd5e5a1837745c6cd9f2df0d730` and code
range SHA-256 is
`0e41c89784b32e6f5a18b98cbd02170bcda3ce780b250c370f24d156274322ad`.
Together A164/A186 now have separate bounded save and restore contracts, but
no natural task-switch/caller or live frame-lifetime proof. After this probe,
the full research suite passes 524 tests; this remains separate from original
execution evidence.

## Japanese A7D0 context-save callsite

Static caller inspection found A7D0 loading the original A164 target from
literal `0x0600A8D4`, then executing `JSR @R3`; the delay slot advances R4 by
32 from the task-frame base at `0x060BDD24`. The resulting save frame begins at
`0x060BDD44`.

`tools/saturn_lab/probe_japan_context_callsite.py` composes the exact original
A7D0 load/JSR/delay path with A164 and stops at A7D6 immediately after A164's
actual RTS return, before executing the next caller instruction. It checks 31
constructed register patterns twice per case in paired reports, the literal
target, frame pointer, PR return address, all 12 ordered context writes, and
the untouched first 32 bytes of the task record. Two original instruction
mutations are rejected. Paired reports under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-021/`
match at SHA-256
`b8bf97eda6f4c1b5be0b213dc5d09f7f707977bc5dd6ff82a4501135e8af21d9`.
Probe SHA-256 is
`9472ba56d97732f683d0a60c5dfe9709d7cc0fd423db7139166d52f15560b43d`.

This is a constructed original caller/callee path, not proof the startup path
naturally reaches A7D0 or that the frame remains live across a task switch. The
full research suite passes 525 tests; tooling tests are separate from these
original execution reports.

## Japanese AB78 context-save callsite

The second original A164 caller begins at `0x0600AB78`. Its prologue saves
R14–R8, PR, and MACL on the stack, reserves four more bytes, loads frame base
`0x060BDD7C` and target `0x0600A164` from literals, and calls A164. Unlike the
A7D0 path, its delay slot does not advance R4. The saved R15 value is the
post-prologue stack pointer, and A164 stores return address `0x0600AB94` in the
frame.

`tools/saturn_lab/probe_japan_ab78_context_save.py` executes the exact original
AB78 prologue, literal loads, JSR/delay slot, and A164 callee for 31 constructed
register patterns twice per case in each paired report. It verifies the
40-byte caller stack traffic, context frame and write order, both original
literal targets, exact return boundary, and special-register state. Two
instruction mutations are rejected. Reports in `execution-025` match at
SHA-256 `b57f2a64f2e9b5de7cb4e3429767ade763f6f123edca3ccc1db09e90a969094f`;
probe SHA-256 is
`269870291c39f4bcdf1dcca6e106435b1e8e83bd1e8a60e37c08aa07c8cdc352`.

The first attempts are retained in `execution-022` through `execution-024`:
they exposed the caller's R15-after-prologue value, the real return sentinel,
and the need to treat a rejected mutated pointer access as a control rejection.
These are constructed caller paths; natural task switching and context
lifetime remain unresolved. The full research suite passes 526 tests, separate
from original execution evidence.

## Japanese AD34 VBR-selected context-save callsite

The third original caller starts at `0x0600AD26`. It reads VBR, derives a
one-bit index, loads a frame pointer from cache-through table `0x2600A020`, and
calls A164. The JSR delay slot advances the selected frame pointer by 32 bytes.
The exact target literal at `0x0600AD8C` points to A164.

`tools/saturn_lab/probe_japan_vbr_context_save.py` composes this caller and
callee for 31 constructed register patterns at each of two VBR values, twice
per case in byte-identical paired reports. It verifies the selected frame,
ordered stores, table/literal read sequence, and return boundary, and includes
two instruction mutation controls. The paired execution-028 report hash is
`573494700d714b29edbe46e31e19bd3ae54e3a5f9211a5fe7e2bb8e7feb16827`.
Attempts in execution-026 and execution-027 are preserved; they exposed a
harness backing-buffer mistake and its diagnostic, not a game-code result.
The VBR values, table entries, and frame/task identity are constructed. This
does not prove natural scheduler reachability or context lifetime.

## AD38 context restore continuation (static)

The return boundary after AD34 is followed by a conditional restore path. At
`0x0600AD38`, R0 is tested; a nonzero result loads saved R5 from the stack,
loads frame `0x060BDD7C` and target `0x0600A186`, then calls the context restore
routine. Both paths derive the same VBR-selected cache-through index for the
ready word at `0x2600A028`, clear it, and restore the caller stack/PR/R13/R14.
`0x0600AD60` separately polls that ready word and tail-branches to ACE8 when
nonzero. A bounded probe now composes AD38 with A186 and tests both R0 branches
using constructed state. Since `tst r0,r0` sets T for zero and the following
instruction is BF, A164's zero return takes the restore path; constructed
nonzero R0 skips restore. Both paths clear only the VBR-selected ready word and
return through the original stack/PR/R13/R14 epilogue. Sixteen seeds per branch
run twice in each paired report, with two branch-opcode mutation controls.
Reports in `execution-035` match at SHA-256
`85ec5602db6ad65b4411c34c430979ad38e57b03aa7f2c0dea73e93d39755f1d`.
The nonzero return is a constructed branch case, not evidence A164 produces it;
no natural task lifetime, scheduler run, or device timing is established.

## Japanese startup and SR/VDP helper leads (static)

The subsequent original startup entry at `0x0600A312` saves SR and six caller
registers, masks interrupts, then calls `0x0600A472`. The latter reads VDP2
`TVSTAT` at `0x25F80004`, selects one of two original timing words, updates the
kernel timing words, and calls BIOS `SYS_SETUINT` / `SYS_CHGSCUIM` entries before
calling `0x0600A638`. The latter's decoded prefix writes a record at
`0x060BCE8C`, refers to VDP1 VRAM at `0x25C00000`, and continues into SMPC/SCSP
paths. These are source-byte disassembly findings only.

Retained pinned-decoder outputs are `analysis/japan-a312-startup-tail.txt`
(SHA-256 `4a68724e3e89616a0cad60c19716eca7279a0d1c686b8da6dca333412d2a289e`),
`analysis/japan-a472-sr-helper.txt` (`ad5d92b780af3b50996940debc41cb7aff17c1262f75fa8dd27f5bed9d5c8f2f`),
and `analysis/japan-a638-sr-continuation.txt`
(`5f59a6db9b28cbe7741ed10bf385b1ed197f2f6905866b8e347c9a10b45f822b`).
The dynamic A312 path requires explicit SR, VDP2, BIOS, SCU, cache-through,
VDP1, SMPC and SCSP behavior; no flat-RAM execution or guessed device model is
claimed. Follow-through at `0x0600A410` shows the tail registering interrupt
handlers `0x0600B2FC`, `0x0600B344`, and `0x0600B3BC`, calling `0x0600A946`
with an A1DA callback/context, storing the `0x0600B2C8` result at `0x060BCC80`,
calling A1AC, and tail-jumping to AB78 after restoring saved registers. The
retained A410 decode SHA-256 is
`466e7c0b26825a97efc5db9b2a7011fa7f502ec31b85a5cafa39199e4eadb5b9`. Continue
with original-byte static range/call-target reconciliation until an existing
approved emulator capture can support a bounded natural probe.

The A1DA callback literal at `0x0600A2B4` resolves to original target
`0x0600CCD2`. Its static entry zeroes four words at `0x060BEA3C`, initializes
six short entries at `0x060BEA7C` and associated pointer records, then calls
`0x06096A38` and `0x060978A0` before proceeding through further original
`0x06096BF0`, `0x06096D8E`, and `0x06096A38` dependencies. The current 80-step
decode shows distinct early-return/error branches and a later cache/context
path, but does not establish the callees' full contracts. Retained output
`analysis/japan-ccd2-callback-target.txt` has SHA-256
`beeccec0eb6f7268f05bac711667f22770afa4e4c60bcdb9f4a42e7ca78e8c90`.
The CCD2 setup loop calls `0x0600F69A` ten times. Its decoded slice uses R4 and
zero-extended R5 as 16-byte indices into a source table at `0x060B3F74`, copies
eight words into a destination record table at `0x060C0748`, and mirrors those
words to `0x060C0738`–`0x060C0744`. This is a static address/field-flow
description, not a validated table meaning or runtime contract. The retained
F69A decode SHA-256 is
`9f56414197cf26776ea11b4fc28b831908185b3da0d8bfaece44cbff7635ce24`.
The CCD2 path also calls `0x0600EFC0`, whose static prefix loops over ten
indices through `0x0600F69A`, then initializes a cache-through callback slot at
`0x2600A0EC` and calls additional original entries including `0x0600F338`.
The F338 prefix reserves 128 stack bytes, writes VDP2 VRAM at `0x25E00000`,
and calls several kernel helpers before the decode ends. Its first helper at
`0x0609BF28` clears a set of `0x060FC5xx` words and calls `0x0609E988` plus
`0x0609CF44`; the latter calls five more entries in the `0x0609E...` range,
fills eight words at `0x060FC5A8`, and clears `0x060FC5C8`/`0x060FC5F4`.
These static dataflow notes do not assign display meaning to those fields.
Retained decode digests: EFC0 `5936c70fa7ec7f0132b20b86104260499aaa97f1b2231d84674e8f49b25a3214`,
F338 `f28b0b5a21b10d7e142389f9fc3700a4ca84bb98d2b4f8a0b150fe6178df5a33`,
9BF28 `5eb8b16c3c24e19484a0f2f79026073f23155065eef660a97d37d53edd631c40`,
and 9CF44 `a4b7e48ac979c9496aa3f16c9b13e0ac135ce9b797260c036e00e7662f07ae64`.
The first 56 instructions at `0x0609E180` repeatedly call `0x06095C24` with
selector `0x0101` and different source/destination pointers, masking 16-bit
values at `0x060FC570` and `0x060FC5A0` with `0xFFF0` and `0xF0FF` before
writing them back. This is a static word-transform/control-flow observation;
the hardware register meaning is unresolved. Decode SHA-256:
`1fe8e4b5d4dbd9aeadf0a10de20d087eaa8eac5458add784b6fe001243bdc78b`.
Adjacent helper `0x0609E25C` similarly calls `0x06095C24` with selector
`0x0201` and updates the word pair at `0x060FC578`; `0x0609E2EC` uses selector
`0x0301` and pair `0x060FC57E`. Both preserve selected byte/word fields using
immediate masks and are separate original routines, not one inferred semantic
register. Their static decodes are retained as
`analysis/japan-9e25c-vdp-helper.txt` (SHA-256
`5d4d6e08c32d458872915a3614dfe4ff3795966604cc43d449b8d0d0b9180fd4`) and
`analysis/japan-9e2ec-vdp-helper.txt` (`9babaa54b89146e80c84185eb3fb1332267f41dde25e8e6eb03450cbc1361a41`).
The adjacent `0x0609E3C8`/`0x0609E484` slices use the same `0x06095C24`
helper with selectors `0x0401` and `0x0501`, updating words at `0x060FC586`
and `0x060FC58E`. The called helper `0x0609E988` separately zeroes several
control words in `0x060BC678`–`0x060BC690` and `0x060FCBF8`, while initializing
`0x060BC67C` to one. The E3C8, E484 and E988 static decode hashes are
`7f3f8779f06627ead552ccb90aa40cd05b468cbf5778ceba804b5e3e65014ec7`,
`d0b18fb7297174bb855be13a124d364b035de2d11c8ae37b191ea9ee26bc28e7`, and
`3d58c1fa0dca976bcc919030aa26df24d739df9ea594f367d4e816158ecde834`.
The following `0x0609E9D0` state routine tests control word `0x060BC678` for
states 2 and 3, checks `0x060BC688`, modifies VDP1 `FBCR`/`TVMR` fields on
selected paths, and updates the cache-through state word `0x060FCBF8`. The
common epilogue restores PR/R11-R14; its adjacent EAB4 path reads VDP2 TVSTAT
and conditionally updates VDP1 `FBCR` before clearing the same state and
`0x060BC688`. Static output hashes: E9D0
`09053f4c771d60c890b125c39f127353b0812415b9069176077750a19be926af`; EAA8
`fa14cc6ae4d855ad67f9c79f4de094d5c383b210050c810e069f99ed87c25f93`. These
paths remain unexecuted because their branches depend on device state and
callback lifetimes not modeled by the isolated helper probe.
The next original `0x0609EB80` routine takes a mode in R4, saves caller state,
and builds one of two buffer layouts under `0x060FB724`; it tests status word
`0x060BC65A` against `0x0160` before choosing an update path. The 72-instruction
static decode has digest
`d3a4913018fa77163c1800b16d683e3b9cabdc2da578988f6139bdaab5f993cb`.
Its mode semantics, buffer lifetime, and device interactions remain unknown.
The shared helper at `0x06095C24` is now original-byte tested separately from
VDP/MMIO behavior. Its packed R1 low byte supplies field width, the high byte
supplies the gap below the high end of the word, R0 supplies inserted low bits,
and R2 points to the single updated longword. The five caller-observed selectors
`0x0101`–`0x0501` were tested over 16 R0 values and eight old-word patterns:
640 distinct cases twice per report, with two original-instruction mutations.
The helper writes exactly one bounded target longword, spills/restores R1 and
R3–R6 on the bounded stack, returns the width-masked R0, and preserves the
sampled remaining GPRs/MACH/MACL/PR. SR test-bit preservation is not claimed.
Paired execution-041 reports match at SHA-256
`7abb46f337199ab0ad94cbf97edd99f5a22e48dcbf081f69881c4ac6ffbf49c7`; initial
harness/oracle failures in execution-036–040 are retained. This isolated helper
contract does not validate the selector meaning, VDP device state, or natural
startup call order.

## Limits and continuation

These results establish bounded original SH-2 helper and constructed
caller/callee contracts under the pinned `saturn-recomp` interpreter. They do
not establish natural call frequency, record lifetime, device or BIOS
semantics, hardware timing, a complete kernel map, other Japanese modules, or
gameplay. Continue with the original caller graph and the separate Japanese
startup path at `0x0600A312`, retaining the VDP2, DVCR, BIOS, and SCU
side-effect requirements. The all-code and all-assets programme remains active
and incomplete.
