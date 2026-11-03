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
The earlier failed attempts remain in `execution-006` through `execution-008`;
they are retained and are not counted as successful execution.

The pinned decoder window at `0x0600B4EC` is retained privately at
`analysis/japan-b4ec-disassembly.txt`, SHA-256
`bdc400dad5a815dc45a5e32f2a57324278c1d211834054252cf94f23b5fff8e0`. It
continues the surrounding service and callback candidates but does not establish
the helper's natural callers. Local focused tests cover the probe's case,
range, and bound definitions; they do not execute or validate game behavior.

## Limits and continuation

This establishes one bounded original SH-2 CPU contract under the pinned
`saturn-recomp` interpreter. It does not establish natural call frequency,
record meaning, device or BIOS semantics, hardware timing, a complete kernel
map, other Japanese modules, or gameplay. Continue with the original caller
graph and the separate Japanese startup path at `0x0600A312`, retaining the
VDP2, DVCR, BIOS, and SCU side-effect requirements. The all-code and all-assets
programme remains active and incomplete.
