# Separate native command observation under707

**Not an installed or ready native observer.** The source patch component, separate GPL header, ctypes ABI, and owned compiled fixtures are implemented. The trusted recipe and exact-head CI workflow are integrated. The earlier ABI v1 exact-head provisioning and native-check runs passed; that matched-core package was transferred with verified source/recipe/binary receipts and reused twice locally under the guarded worker. A reference-only continuation from the accepted frame1200 seed reached frame1800 and saved a verified full-kernel-resident checkpoint. The prepared observer then executed600 original frames from that checkpoint, but its bounded128-record buffer overflowed at129 actual CD word transfers before a complete root could be accepted. A repeat matched every frame/audio/video/final-state hash and retained128 records:111 reads and17 writes. Site060958EC accounts for46 reads of25890008 returning0BC1. Two reference and two observer-disabled600-frame controls with the same eight-frame Start pulse matched the enabled runs on frame, audio, video and final-state hashes. This is a repeatable original polling lead, not a recovered function or accepted command trace. Two adjacent leaves are separately executed over original kernel bytes with the exact pinned SH-2 interpreter:060958EC returns each of three observed words unchanged, and06095904 writes each of four observed words to its original literal address25890008 in the RTS delay slot. Each takes3 instructions. The larger poll helper at06095A84 was executed on each of three exact natural eight-read sequences from06095A94 with maskR4=1: seven reads have bit0 clear, the eighth has bit0 set, it returns0 and stores that final word throughR5; each path takes77 interpreter steps. Original code at06095A3E contains the matching BSR/delay slot (`B021/64D3`), targeting06095A84 and returning at06095A42, which matches the retained PR and register state. The natural access at060959DE also retainsPR=060959AE; source at060959AA is `BSR 060959CA; NOP`, so the observed call chain links service entry06095992 through060959CA to the poll helper. A second leaf at06095ACE has also been executed in three recorded call contexts: it reads the four words at25890018/1c/20/24, stores them in order through the observedR4 destination, returns the fourth word, and takes12 interpreter steps. Its BSR at06095A4E and recordedPR06095A52 match. This establishes local nested semantics without proving the outer service return; timeout and wider caller behavior remain unresolved, and device meanings are not assigned.
The neighboring packet writer at06095AB4 is now replayed through its original13 SH-2 instructions in three retained call contexts. Its BSR at06095A36 and observedPR06095A3A agree; four stores to25890018/1C/20/24 reproduce the actual transfer words in order. The replay source buffer is reconstructed from those observed output transfers, so original caller-buffer contents are not independently validated. Report:`/home/dev/neptune-research-private/707/cd-word-helper-output-010/report.json` (SHA256`904d042519ff1b51f4cf5c852d1f075b49d7fb440d1198e4a9016041e0b81afe`). The poll timeout and wider service behavior remain open.
The fixed profile2 path now has two reference controls, two observer-disabled controls and two enabled original runs, all from frame1800 with the same eight-frame Start pulse and each executing600 original frames. Reference/disabled controls succeeded; all six runs have identical frame (`56f7f663f4c9efad393cee9edaad972cd04bd6c792aa4a3d9434db284730a5cc`), video (`0939dcfcc86c6faae671b242573817477a7015acf574a5d829e5d1153fbe5e6e`), audio (`eafc18cc2ff4305e000446326d97be2a3b884cf8b114ec1ecf794d626a3b393d`) and final-state (`207d3e58bbb24ad85791c131a91b3903ee0419242ff2988e446715fd0e252802`) hashes. Both enabled profile2 traces overflow at transfer129 with128 records and no root; their complete record arrays and status are identical. The normalized profile1/profile2 comparison also matches all128 records and these four outputs, so changing profiles does not avoid this polling overflow. Guarded profile2 receipt `/home/dev/neptune-research-private/707/profile2-validation/supervisor.json` (SHA256`c67e34cfd5f8cfc8703db34dcf958e629a1c77d4f1054932241a61cd31fb046b`); original captures and the pairwise profile1/profile2 receipt remain under `/home/dev/neptune-research-private/707/`. No command root was accepted. ABI v2 now keeps the native cap at128 storage slots while losslessly encoding consecutive transfer records when sequence, timestamp and register values follow exact integer steps and every other captured field is identical; otherwise a new slot is required. The exported trace carries the repeat count, timestamp step and per-register steps, so each original event is reconstructible and counted. A check of the retained original capture found40 consecutive reads (sequences88–127) at060958EC/25890008, all0BC1, with timestamp step33 and only R14 changing by+1; this group can occupy one slot and preserve all40 observations. Private evidence:`/home/dev/neptune-research-private/707/lossless-repeat-candidate.json` (SHA256`3222b7f495d1273e1dc47db10ac2bf666ec8b02aa8a51cd30c10725012fc7be9`). A compiled owned C fixture covers the same timestamp/R14 progression, decoder reconstruction and unchanged128-slot overflow fence; the focused10-test suite passed. ABI v2 has not yet been rebuilt into a matched core or run against the game; exact-head CI and fresh original windows remain necessary.
The all-original-code programme and655 remain active and incomplete.

Original command-packing PR706 retains9,152 pending-boundary cases/run twice.
It reaches actual95992 through AE676/AE908 andA4FAC/A4FBE, without executing a
service return. The first subsequent device word read is959DE at25890008.
This capability must observe the original device-bearing path directly.

The proposed separate tool is`beetle-saturn-command-trace`, using a fresh matched
historical reference generation and distinct`neptune_command_*` exports. Preserve
reference cores, locks, immutable caches, call/context/init ABIs and root Apache
licensing. The eventual native header and complete corresponding core source
retain the upstream GPL notices through the existing preparation boundary.

Two initial fixed profiles observe one naturalA4FAC root: AE676's actual JSR/
MOV delay returningAE698 (mask64,packet48), or AE908 returningAE92E (mask128,
packet62). Observe source-call/delay/entry continuity,95992/959CA entry/return,
command/response/CPU/stack/SR snapshots and actual rootRTS/NOP-delay/return.
Command/response snapshots use only validated fixed-size High Work RAM views;
unavailable pointers require explicit validity tags, not invented observed zeros.
Response/local bytes at entry retain their actual values without initialization.

Proposed private witness ranges are95904+256words,A4FAC+118words,AE676+23words,
AE908+23words andAEA30+4words:424words total. Confirm against the unchanged
original kernel before entry, every record and final capture. These are source
witness spans, including literals/unexecuted neighbors where declared, not counts
of executed instructions or complete functions. Preserve verified partial-loader
imports; no accepted record may use a partial/mismatching resident witness.

The inspected matched core fuses a load, comparison and conditional branch.
A snapshot at the next outer dispatch can miss the immediate post-load state.
`provision_command_trace.py` therefore appends a master-only callback after the
existing actual`MemRead16` and`WB_WRITE`, using a single-evaluation address local.
The generic word-store handler receives a callback after its existing actual
`MemWrite16`, using its already computed address/value. Neither hook calls a bus/
device accessor again. The pre-dispatch observer must retain the true executing
PC/opcode before pipeline rotation; callbacks must label transfer state precisely,
without presenting it as a completed later instruction or physical cycle.

The existing triplet fusion body, CPU/bus operations and timing steps remain
byte-identical. A separate actual fused-NOP hook is still required for call/root
return continuity. The eventual observer must be value-only: no CPU/RAM/device,
WB/MA timing, pipeline, event scheduling, fusion or JIT changes. Observe relevant
CD word transactions at25890008/0C/18/1C/20/24 from their real transferred values.
Do not silently discard repeated polls or overflow to obtain a successful trace.

The initial bounded contract retains one root,128 storage slots, depth16,4,194,304
pending master hooks and120 pending frames. These are observer hooks, not SH-2
instruction/hardware-cycle counts. Source/frame/pipeline/stack/counter/depth/
capacity/unfinished/unsupported errors retain diagnostics and fail acceptance.
The ordinary job guard, shared3 admission/180-second leases and host/provider/
storage reserves stay unchanged; no local core build below preparation reserve.

Current patch/header/ABI validation is separate from native readiness:

- Ten focused owned tests include a compiled exported-header ABI fence and lossless-run fixtures, plus real
  compiled baseline/observed transfer fixtures:
  one address evaluation, one actual mock bus operation, identical CPU/RAM/WB
  results, correct signed-load/truncated-store values and no slave callbacks.
- The focused10-test suite passes after ABI v2 lossless-run changes. The earlier39 related/221 factory checks cover ABI v1 and have not been rerun for v2. Exact-head run`41658156944` passed, and provisioning run`41658156759` built and loaded the ABI v2 core, but its post-build check failed because`provision.py` still expected ABI1. That validator now expects ABI2 with the unchanged216-byte record/128-slot/424-word layout; its regression test passes. A fresh exact-head build/smoke is required before native-game windows.
- The header requires the profile-specific source JSR and delay, A4FAC root, A4FBA
  RTS/NOP delay and return, service boundaries, and actual transfers. An owned compiled semantic fixture drives that event order through the exported ABI and verifies that final source-witness mismatches fail. Transfer PC/opcode
  comes from the master prehook; command/response words carry validity tags and are
  read only from aligned canonical high Work RAM.
- A retained corresponding GPL archive was used to reverse only exact accepted
  init-hook insertions; all six reconstructed source hashes match the inspected
  original reference pin before applying the new patch. This checks actual
  source anchors with an explicitly owned nonobserver header, not a native build.
- Private receipt:`/home/dev/neptune-research-private/707/patcher-pin-_bb68yfc/report.json`;
  SHA256`fb5da294b45597d0ac1e06479028d2613067400161df6a5802c36027645c3e23`.

Earlier ABI v1 exact-head runs41648585340 (provisioning) and41648585631 (native checks plus
aggregate gate) passed. Job125960585219 built the matched core, exercised the no-media
ABI/fence smoke, and verified first-build/reuse identity. The artifact transfer receipt
is `/home/dev/neptune-research-private/707/ci-preparation-001/command-trace-transfer-verification.json`; binary SHA256 is
`3a95acef8cc6e20297d907a9658f6ae6c067f8ae1a72dbb84a594b742938184a`. Two guarded local cache-reuse attempts passed with that same binary. CI received no game/BIOS.
The bounded CPU-only service replay at`060959CA` used one retained natural call,
returned to captured caller`060959AE` after171 original instructions, and
reproduced its actual status/poll/register reads and five writes. Report and
limitations are in [the service replay result](../restart/research/2026-11-03-cd-command-service-replay.md).
Next rebuild ABI v2 through exact-head CI without compiling a local core, then
run fresh guarded reference/disabled/enabled600-frame windows per profile from
the verified frame1800 seed. Compare exact canonical import/final state and
every native video/audio/input observation, retain each event through lossless
run decoding, verify independent source witnesses and reject semantic record-copy
controls. If the root still does not return, continue tracing around060958EC
and the outer service timeout/return; keep failures private.
Tool preparation is not original evidence; native boundary/device traces alone do
not prove physical timing, full game behavior, Godot parity or all-code completion.
