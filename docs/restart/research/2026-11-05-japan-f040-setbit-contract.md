# Japan F040 helper set-bit contract (tool ready, original execution pending)

## The open question

The accepted caller-derived helper probe
([`probe_japan_095c24_caller_derived.py`](../../../tools/saturn_lab/probe_japan_095c24_caller_derived.py))
measured one longword read and written through R2 with bit 31 set, with R0-R14
and SP preserved. That measurement used the GPRs captured at **one** F040
caller state. In that state R4 held `0x1F`, so "bit 31" is exactly what a
rule that takes its bit index from R4 would also produce.

The accepted F040 loop evidence says the helper is called repeatedly while R4
decreases by two per visit and R5 advances through powers of four
([loop snapshots](2026-11-04-japan-f040-loop-register-snapshots.md)). Whether
the helper always sets bit 31, or sets bit `R4` (or `R5`), or something else,
is therefore not established. The helper's role in the F040/F134 path, the
natural `0x0600A20E` caller, and every gameplay meaning stay open.

## What this change adds

[`probe_japan_f040_setbit.py`](../../../tools/saturn_lab/probe_japan_f040_setbit.py)
runs the original F040 path from the captured frame-1200 WorkRAM, observes
**every** call to the original `0x06095C24` helper, and records for each call:

- the GPRs at the helper entry and at its inner visit `0x06095C60`;
- every write the helper performs, split into stack spill/restore traffic and
  data traffic, so the single data word it stores is identified from the
  original write events rather than from a change in value;
- the bits that the store changed in that word.

A second run repeats the same execution with a constructed `0x00000000`
pre-word at the observed result address before each call, so a repeated
(idempotent) store stays observable. Candidate bit-index rules (constant 31,
`R4`, `R5`, and low-bit variants, taken at the helper entry and at the inner
visit) are then discriminated mechanically, and a rule that no observation
supports is reported as rejected rather than as agreement.

The run is anchored to accepted evidence before it is reported: the caller
data slice `0x060FC500..0x060FC700` must hash to the accepted
`4d43fa36…` slice, and the stack pointer at the helper entry must be the
accepted `0x06001F24`. A run that does not reproduce those facts fails instead
of producing a result.

## What has actually been checked here

Seventeen owned synthetic unit tests
([`test_probe_japan_f040_setbit.py`](../../../tools/saturn_lab/tests/test_probe_japan_f040_setbit.py))
cover the changed-bit arithmetic, the stack/data split, the rule
discrimination (including "no evidence" and wrong-rule cases), the register
series checks, the constructed pre-word mechanism, the instruction budget, the
source-matching fetch fence, the rejection of a constructed address outside the
captured WorkRAM, the anchor failures and the private report handling. They use
a test-owned stand-in CPU and never original game code.

The harness itself is checked against the **real pinned** `saturn-recomp` SH-2
interpreter. The probe exposes an `owned_smoke(emu)` that assembles an owned
synthetic caller and helper: the caller dispatches to the helper four times
while R4 decreases by two and R5 advances by four, and the helper stores
`1 << (R4 & 31)` at an owned pointer. The pinned CPU must observe exactly four
calls, the four changed bits 31, 29, 27 and 25, the owned result store, the
R4/R5 progressions and a rejected constant-bit rule; the same bits must repeat
in the constructed run; altered source bytes, a constructed address outside the
captured WorkRAM and a small instruction budget must be rejected. The existing
pinned-CPU job in
[`saturn-lab.yml`](../../../.github/workflows/saturn-lab.yml) runs that smoke
with the hash-verified interpreter checkout and keeps its source-only receipt.

That is interoperability evidence for the harness only: no original game byte
was executed. Two pinned-interpreter limits were seen while preparing it and
matter for any original-code claim: `ADD` does not set the T flag in this
interpreter, and its decoder does not decode `0000nnnn00000000` and maps
`0100nnnn00000000` to `SHLL`.

**No original-byte result is claimed here.** The private Japan kernel and the
frame-1200 capture are not available in this session, so the experiment below
has not been run. The pinned interpreter sources were fetched from the public
upstream repository at the accepted revision and verified against the accepted
SHA-256 pins, which is what the harness check above uses.

## Exact next runnable command

On the existing private Japan study host, with the accepted Japan `0KRNL.BIN`
(SHA-256 `23685e15…`), the frame-1200 capture (SHA-256 `c115d4b4…`, checkpoint
`frame` 1200, core `c862380e…`) and the accepted interpreter checkout:

```sh
timeout 300s nice -n 10 python3 tools/saturn_lab/probe_japan_f040_setbit.py \
  --kernel <japan-0KRNL.BIN> \
  --state <japan-frame-1200-state> \
  --checkpoint <japan-frame-1200-checkpoint.json> \
  --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --report <private>/f040-setbit-8192-run1.json \
  --instruction-limit 8192
timeout 300s nice -n 10 python3 tools/saturn_lab/probe_japan_f040_setbit.py \
  --kernel <japan-0KRNL.BIN> \
  --state <japan-frame-1200-state> \
  --checkpoint <japan-frame-1200-checkpoint.json> \
  --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --report <private>/f040-setbit-8192-run2.json \
  --instruction-limit 8192
cmp <private>/f040-setbit-8192-run1.json <private>/f040-setbit-8192-run2.json
```

Use fresh private report paths: the probe creates the report exclusively and
refuses to overwrite. Keep the original media unchanged and do not widen the
WorkRAM or device fences to make a run succeed.

## How to read the result

- `anchors.data_slice_matches_accepted` and
  `anchors.helper_entry_sp_matches_accepted` must be true, otherwise the
  regenerated caller state is not the accepted one and the run is reported as a
  failure with the observed runs retained.
- `hypothesis_results.constructed` lists every candidate rule with the number
  of observations that could test it and the mismatching observations. A rule
  is only meaningful when several observations test it; a single observation
  fits many rules and must not be read as a result.
- `observed_runs[*].helper_calls[*].set_bits` is the observed bit index per
  call in the unmodified captured execution; the constructed run repeats the
  measurement with a cleared pre-word.
- `pair_comparison` must show identical PC and read traces and identical write
  address/width shapes for the two constructed seeds.

## Reproducibility finding

The accepted caller-derived helper result is pinned to a private caller report
with SHA-256 `e1b3dde0…`. That report was produced by a variant of
`probe_japan_f040_entry.py` that also captured the `0x060FC500..0x060FC700`
WorkRAM window in every snapshot; that variant is **not** in this repository,
and the repository's entry probe does not emit that field. Because the report
embeds the SHA-256 of the tool that produced it, a report regenerated from this
repository cannot reproduce the pinned report hash. The accepted helper result
is therefore anchored to a private artifact, and this probe anchors to the
accepted data slice hash and helper-entry stack pointer instead. Reproducing
the accepted caller report needs the producing probe variant itself, which is
a separate recovery item.

## Still open

The helper's purpose, its natural callers, the F040/F134/A946 contract, the
task that owns the flagged word, the meaning of the R4/R5 progression, every
other kernel, gameplay, sound, DSP and asset code, and all whole-program
denominators remain open. Nothing here establishes a game rule, a device
effect, timing or parity.
