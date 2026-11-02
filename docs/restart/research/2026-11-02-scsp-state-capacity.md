# Disjoint SCSP state-call capacity

[672](https://github.com/elgansayer/Neptune-Bomberman/issues/672) unblocks the
original NLSND state-update recovery in
[671](https://github.com/elgansayer/Neptune-Bomberman/issues/671). The separate
ABI5 preparation combines the unchanged accepted SCSP word-effect component
with a larger bounded trace and disjoint code/data mapping. Earlier ABIs1/2/3/4,
source files, native generations and reference cores remain unchanged.

The [evidence JSON](../evidence/2026-11-02-scsp-state-capacity.json) records exact
source/recipe/component/native/input identities and real commands' outcomes.
These are native-tool and original-call diagnostics. The full independent state
contract, mutations and complete command11 caller acceptance remain open in671.

## Reproduced blocker

The pinned control-flow analyser seeded at original51B2 finds285 candidate
instructions across8 separated code spans. Seven intervening gaps contain lookup
material; another lookup starts after the final RTS span at5CE4. The verified
original file ends at5D70. Linear decoding of these tables produced misleading
instruction-looking rows and skipped real branch targets. Those failed initial
windows are retained; the final inventory follows actual static branch targets.

Mapping those eight data spans plus pointer/context/stack and a separate caller
context needs12 regions. The accepted ABI4 allows4 code ranges,8regions and128
events. Its real limited-map diagnostic produced2 inactive terminal observations
and14 active instruction-access guards at5AA2, with up to181 instructions and122
events already recorded. No tables were made executable or SCSP registers
flattened into RAM to evade the limitation.

## Prepared profile and actual tests

ABI5 fixes its maximum at2048steps,1024events,16ranges and16regions. It preserves
all original code/data overlap, address, width, alignment and MMIO restrictions.
Its result layout reuses accepted ABI2; its word-register component is byte-for-
byte the accepted ABI4 extraction. Identity binds both underlying adapters, the
state preparation module and derived backend, plus existing source locks.

Fresh offline compilation and reuse passed all of these actual native checks:

-17,280 reference word-effect cases,1,024 identical-program-word writes and640
  owned CPU word-access cases, with unchanged clock/interrupt limitations.
- The real2048-instruction and1024-event overflow fences and subsequent recovery.
- A47-instruction nested call through16 disjoint code ranges, reading all16
  mapped regions, with exact registers/SR, memory, events and PC sequence.
- A missing executable range rejected at its actual target, followed by recovery.
- Direct C-boundary rejection of17ranges or17regions before any instruction,
  event, code/data mutation or device-state change. Python rejection alone was
  not counted as proof of the native boundary.

One first preparation child finished its checks and wrote a ready receipt, but
its guard reported cancellation and exit-15. That attempt remains failed. A fresh
preparation/reuse attempt observed trusted completion acknowledgements and exit0
with unchanged guard decisions and timeout. Metadata-only tracing recorded its
trusted channel; the first cancellation's cause remains unproven. A child's
success output alone never qualified the operation or established factory health.

The required preparation child now runs both ABI4 and ABI5 for applicable
changes. The always-present protected aggregate waits for it; missing/skipped/
failed applicable work cannot qualify. The recipe is documented in
[PROVISIONING.md](../../../tools/factory/PROVISIONING.md).

## Original-call resumption

Using the prepared profile, the original direct51B2 experiment runs with8
separate executable spans and11 or12 mapped data regions. Its fixed16-case
domain varies pending byte0/80, state flags0..3 and caller-context aliasing.
Two fresh guarded processes reached the real return for every case and produced
identical reports. Counts range from31 to245 instructions and66 to156 events.
The156-event paths directly demonstrate why the old event capacity was too small.
All8 code spans and12 distinct data-region addresses were actually read/executed
across the selection. Per-case instruction budget was512, below the native max.

The two previously terminal ABI4 cases agree exactly with ABI5 in registers/SR,
ordered events, PCs, cycles, device before/after and all shared mapped bytes.
An initial resumed experiment still stopped at the final byte lookup. Its
failure is retained; mapping the verified trailing table as read-only data
resolved it. No zero-filled stand-in or relaxed assertion was used.

Full reports stay private under672/original-002; their hash is in the JSON.
The real USA1.003 NLSND input remains
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`.
Inputs/source/native were read-only, network onlylo, broker/auth/signing authority
hidden, shared limit3 and lease180seconds. Guardian identities and terminal states
are retained. Deterministic tests made no model requests; account/CI spend is
unknown. No service, quota, account allowance or Neptune continuity was changed.

Returning successfully with repeatable state is diagnostic evidence. It is not
the independent semantic model and mutation detection671 requires. Natural
caller domains, full SCSP/DSP/audio, hardware timing, production Godot parity,
whole-code recovery and the536 continuity/recovery gate remain open. Current
exact-head/base CI and publication state belong to GitHub and the coordinator
checkpoint, not an assumed green status in this document.
