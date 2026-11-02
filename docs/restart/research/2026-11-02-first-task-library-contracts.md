# Original first-task initialization and library contracts

Issue [655](https://github.com/elgansayer/Neptune-Bomberman/issues/655) remains
open. This result broadens the earlier one-state diagnostics and completes two
further library initialization routines. Full89C8, successful95B04 and the
all-original-code programme remain incomplete.

The [derived evidence](../evidence/2026-11-02-first-task-library-contracts.json)
retains exact report/source hashes, private directories, controls and limitations.
Original USA kernel SHA256 is20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7,
resident at06006000; interpreter revision isf20de940e8013fc84103a5b39c4069ed8071b1f9
with all three accepted source hashes checked. Executed probe source is
13cce5feeb5c82a4ed4df9d4ee57ca298f837a4c, frozen with eight source-file hashes.

## Actual repeated original execution

Each family ran twice in fresh guarded processes; full report bytes match within
each pair. Cases use constructed register/global/stack states, real original
calls and independently specified scalar, register, PC/delay and transaction
expectations. Prior natural623A entry does not make these constructed states
natural whole-function evidence.

| Original path | Cases per run | Actual outcome | Instructions |
| --- | ---: | --- | ---: |
| 89AC | 1,920 | Complete RTS+NOP return | 23 |
| 89C8→real89AC→89FC | 1,920 | Incomplete parent prefix | 127 |
| 623A→89C8→real89AC→89FC | 1,920 | Incomplete caller/parent prefix | 130 |
| 95B04 parameter validation | 1,280 | 1,220 complete error returns;60 valid prefixes to95B54 | 20–41 |
| 96A80 | 1,536 | Complete callback-address initialization return | 12 |
| 96AC0→real96A80 | 162 | Complete table initialization return | 68+6×max(0,signed count) |

Total8,738 cases per selection, twice:4,838 complete returns and3,900 incomplete
prefixes per run. These totals describe selected cases, not recovered function
or whole-module denominators. All31 family/control combinations have actual
non-budget rejections using disposable original copies. Reports retain exact
failed control traces/events/state and source hashes. The real caller128 refusal
also remains:128 executed/129 attempted, stopped at060089BE. The unchanged
accepted1024 profile admits explicit smaller budgets144 for the caller and256
for table initialization; the old128 guard is unchanged.

## Measured contracts and limits

89AC writes fourFFFFFFFF words at060BD8C4..060BD8D3. The89C8 prefix initializes
four plus12 pointer words to00200000 and12 halfwords to zero, calls real89AC
and stops at89FC. All104 global bytes,12 stack bytes and saved callerPR/R14/local
word agree.00200000 is stored without being dereferenced by these paths.

95B04 clears the word060FA8C4 before checking parameters. The signed first
argument must be1..24; otherwise it returns-5. Within that range, a second
argument with either low alignment bit set returns-21. An optional nonnull
descriptor must contain mode0 or1, signed length at least2 and a nonzero third
word; failures return-4. Count checks precede alignment, which precedes descriptor
reads. Closed errors restoreR13/R14/SP/PR through the real common return/delay
path. Valid cases stop before95B54 and its BIOS call; they retain the live
16-byte frame. No successful library return is fabricated, and the API's purpose
is still unconfirmed.

96A80 reads the block pointer from060FA8BC and stores four original code
addresses at block+4,+8,+12,+16:060A69A2,060A6B08,060A6BFE,060A6BF2. Its real
RTS delay slot performs the final store. It does not execute those callbacks.

96AC0 preserves the liveR13/R14/SP/PR and MAC state, stores its count at block+0,
calls real96A80 and clears scalar words at offsets94/B4/A8/B0/AC/B8/C4, ten words
across438..45F, and one word per positive count atC60+i×A8. Selected counts cover
0..24 and signed80000000/FFFFFFFF skip paths; the direct helper's negative paths
are separate from95B04's1..24 parameter contract. The explicitly bounded block
at060D0000 has7036 bytes, compared in full including all untouched gaps. Original
halfword literals96BD4..96BDD are mapped from actual verified source bytes as
read-only data; no guard API or device model was widened.

Every visible register, SR/PR/MAC, PC, executed delay flag, data transaction,
controlled output, read-only canary/input and other mapped source byte is checked.
The original file rehash is unchanged. These are interpreter instruction counts,
not measured hardware cycles or proof of gameplay/audio/Godot parity.

## Execution and continuation

Private batch:`/home/dev/neptune-research-private/655/contract-batch-mlbb_e2m/`.
Frozen adapter:`.../655/adapter-ff791d837afa18580f443525fb8ba317a7e6255286c9ee023edfcef61eb5be7b/`.
All per-family directories and full report hashes are in the derived evidence.
Runner/worker/deriver sources remain under
`/home/dev/neptune-evidence/code655-20261102/`.

Live foreign exclusive/full-slot admission deferrals and the first constructed
canary rejection are retained separately. The latter crossed high RAM's upper
boundary before CPU creation; the fix lowers constructedSP by0x100 and checks
all region boundaries. It changes no guard. Each admitted run used its own
180-second lease within shared3,60-second/nice10/downward2GiB limits, offline
namespace, read-only originals/source/dependencies and hidden broker/credentials.
Own leases were released; foreign factory reservations remain untouched.
No provider dispatch or native build occurred.312 research and14 catalogue
tests pass separately from these original reports.

Continue the positive95B04 path, including the actual BIOS vector06000344,
A6790,969E0,96C60 and their device/callback dependencies, then complete89C8's
real return. The retained static lead file is
`.../655/library-dependency-source-leads.json`; source analysis is not execution.
Do not substitute HLE/callee results or use arbitrary flat RAM for devices.
Then continue the full623A task body, root cycle, unresolved17F2, slave/loader/
overlays, sound/DSP and regional network/menu/save paths. Whole-code denominators
and physical timing remain unknown; do not close655 around these prefixes.
