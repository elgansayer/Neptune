# Original NLSND slot-reset helpers

[#680](https://github.com/elgansayer/Neptune-Bomberman/issues/680) qualifies the slot
byte operations reached by command10 and compares three complete original helper
contracts. Parent665 remains open. The [evidence receipt](../evidence/2026-11-03-original-slot-effects.json)
binds source/input/native identities, actual commands and retained diagnostics.

## Separate reference device profile

ABI7 admits byte reads at slot lane0B and writes at00/0B/15/17 across32 slots,
retaining the exact existing DSP word component. Slot words are accompanied by
original decoded control/envelope/send fields, key-execute latch and volume/pan
calculations. A raw byte array cannot reproduce those effects. The extracted
component retains pinned declarations, selected original case bodies, helper,
table and notices. It runs no device clock, envelope, key execution or audio.

The independent contract compares slot words, decoded fields, every captured
untouched byte and the unchanged DSP state.98304 byte-value cases,1024 owned CPU
cases,96 ORI.B read-modify-write cases, latch sequencing, raw/CPU address and width
guards, fake-MMIO-RAM rejection, inherited DSP word effects and full trace/count
fences/recovery pass fresh preparation and reuse in existing CI. ABI7 checks a
separate library/identity/receipt,98400-byte result and3400-byte slot view; ABIs1–6
and their caches are unchanged. The complete-byte sweep avoids redundant scalar
conversion while retaining the full state comparison.

The coordinator verified the exact source head, successful preparation job,
artifact identity, source/component/binary hashes, smoke/reuse evidence and ELF64
little-endian x86-64 architecture before loading the retained tool inside the
offline local namespace. Its local owned loading/recovery checks passed. This
reuses the existing trusted preparation boundary; an arbitrary uploaded artifact
is not executable factory policy. No original inputs were present in preparation.

## Complete original helper comparisons

| Entry | Constructed cases per process | Instructions | Independent contract |
| --- | ---: | ---: | --- |
|3540|327|100|Set A5 to100000; OR1F into byte lane0B of all32 slots, updating release-rate fields and preserving the other bits.|
|355A|156|52|Zero byte lane15 across16 slots starting at caller A5; update/mask the send word and decoded send fields.|
|356E|156|56|Zero byte lane17 across16 slots and recompute direct/effect volumes; clear exactly16 caller-RAM bytes at A6+187E..188D using four ordered long writes.|

The639-case selection includes all256 release-input low-byte seeds, four initial
SRs, two register/RAM-address variants and every valid16-slot starting window.
All visible registers, SR/CCR, exact ordered transactions, PCs, every mapped RAM
byte, complete device effects and untouched state are compared. D7 ends0000FFFF;
A1 ends just past the addressed slot sequence. Move/OR operations preserve X;
other final flags follow the declared result. Model cycle counts are retained for
repeatability, not claimed as measured hardware time.

Two fresh processes pass the selection and produce identical full reports. Six
changed-original families alter release mask/count, send lane/count, volume lane
and final RAM destination. All24 changed calls reach return and fail the independent
comparison. Guard termination is never counted as a successful semantic mutation.
The original source/expected contract and comparison precision remain unchanged.

## Actual command10 continuation

The separate128-case handler/17F2 matrix preserves all6 previous complete outcomes
and extends all122 previous device-guard prefixes. All original code buffers stay
unchanged; no MMIO is mapped as RAM. The resulting outcomes are:

| Outcome | Cases | Status |
| --- | ---: | --- |
|Return|32|Diagnostic only; no independent complete command10 contract yet.|
|Write0780 at3536|64|Explicit forbidden low-RAM write; classify/qualify its data contract before adding a mapping.|
|Longword write100800 at35B4|32|Explicit forbidden DSP width; retain the existing word-only component until a separate profile is qualified.|

In the pinned reference, C00..DFF is24-bit sign-extended DSP TEMP work-buffer state,
not EFREG or an ignorable output-register range. Longword reset and low0780 work
remain separate dependencies. Natural callers/command domains, hardware timing,
DSP execution, actual PCM and production Godot fidelity remain unverified.

```sh
python3 tools/saturn_lab/probe_netlink_slot_effects.py \
  --source-file "$NEPTUNE_NLSND_SOURCE" \
  --prepared "$NEPTUNE_ABI7_PREPARED" \
  --previous-prepared "$NEPTUNE_ABI6_PREPARED" \
  --report "$NEPTUNE_NEW_PRIVATE_REPORT"
python3 tools/saturn_lab/check.py
```

The376 research-tooling tests pass separately from original execution, emulator,
game and factory health. Source/input/native are read-only, network onlylo,
broker/credentials/signing authority hidden, shared limit3, lease300s and guard5s.
Original processes have512MiB address space,40s CPU,45s wall and4MiB files; helper
calls have128 instructions and command10 has8192. Tooling uses its previously
qualified fixture limits. All accepted subprocesses exit0 without cancellation,
timeout, truncation or surviving guardians. Both filesystems retain5GiB reserves.

Failed attempts remain recorded: the first used an incorrect inherited size bound;
the next exceeded CPU120 during combined reuse despite a passing inner fresh
receipt; the next did not start before bounded host admission expired. CI fresh/
reuse and subsequent admitted local original comparisons are distinct accepted
execution. No foreign lease, service, provider policy, allowance or continuity was
changed. Test model requests are0; account/review/CI spend is unknown. Whole game
and complete code recovery remain open with unknown denominators.
