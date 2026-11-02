# Original NLSND command12 and frozen SCSP DSP register effects

Dependency [666](https://github.com/elgansayer/Neptune-Bomberman/issues/666) of
[665](https://github.com/elgansayer/Neptune-Bomberman/issues/665), implemented in
[670](https://github.com/elgansayer/Neptune-Bomberman/pull/670). The first real
command12 diagnostic stopped at41C8: forbidden word write100700. That failure
remains retained. ABI4 now executes the supported even-word paths through the
original4188 helper,1E4C handler and17F2 dispatcher to their actual returns.
This is isolated original-instruction validation against constructed state and a
source-pinned device component, not natural sound playback or full code recovery.

The [machine-readable evidence](../evidence/2026-11-02-original-nlsnd-dsp.json)
records original/source/component/native identities, counts, controls and limits.
Raw source inputs and full reports remain private. USA1.003 NLSND is23,920bytes,
SHA256 `f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`.
The historical reference is Beetle01bc063f, with unchanged Musashi preparation
sources atf20de940. Earlier ABI1/2/3 generations and all reference cores survive.

## Device contract

The adapter extracts the actual selected word branches, full DSP declarations
and endian helpers from hash-verified external source. Upstream notices and
COPYING are retained in the generation. It does not map device space as RAM.

| Word offsets | Observed reference component effect |
| --- | --- |
|700..77E|64 coefficients: store value shifted right3; readback shifts left3|
|780..7BE|32 full16-bit MADRS values|
|7C0..7FE|Unmatched write falls through without state change; reads unsupported|
|800..BFE|128 64-bit MPROG entries, four big-endian word lanes each; set MPROG_Dirty even on identical writes|

All640 even destinations were exercised with9 edge values and3 seeded states:
17,280 actual reference-component cases, followed by640 owned CPU write/read/RTS
cases. Full logical arrays, dirty state, and all other bytes of the projected DSP
structure and surrounding canaries are compared. Unsupported byte/long accesses,
addresses outside the profile, gap reads and odd accesses fail closed. Fresh
compilation and cache reuse passed; truncation, dirty-flag and lane mutations
compiled successfully then failed the independent state oracle. The first native
build failed because extraction selected a directive mention inside a comment;
the failed stage was preserved and the complete macro-comment boundary corrected.

Device clocks are frozen. These register branches call no interrupt processing;
slots, timers, DSP decode/execution and samples are absent. The full SCSP object
is not claimed tested. Odd accesses stop at a native alignment fence, not a
recovered68000 address-error exception path. This source shares emulator lineage
with prior research; it is not independent hardware corroboration.

## Original command contract

The helper loads its context pointer from0412 and masks context byte4 with30.
Inactive calls perform no device writes. Active calls choose selector mask3 when
bit4 is set, otherwise7; multiply the masked D0 selector by8; mask D1 to31 and
multiply by8. Context byte5 contributes an unsigned byte offset. Four words are
read from `4210 + 8*(D1&31)` and written consecutively from
`100700 + context_byte5 + 8*(D0&mask)`. The256-byte4210 table is read-only data,
never declared executable because a linear disassembler prints instruction-like
rows for it. Reachable device destinations cross COEF, MADRS, gap and MPROG.

D0/D1 become their scaled indices; D3 becomes the mask; D7 becomes the byte
offset; A0 is the context; A1/A2 advance by8. The common40FA return computes
word flags from D0, preserving X on inactive direct/handler paths; the dispatch
index shift and active shifts clear X. Inactive paths retain their other data
and address registers. The caller restores A5/A6 and balances the nested stack;
A4 retains the original A6. Exact18-register, mapped-RAM/canary, ordered-access,
executed-PC and device-state comparisons are required on terminal paths.

The27,195 distinct cases span helper/handler/dispatcher, four SR patterns, two
register/context/device variants, all256 values of each byte field in a declared
union and boundary combinations. This is not the full Cartesian input domain or
proof of which commands natural gameplay supplies. Two fresh processes produced
identical reports:20,574 active and6,237 inactive complete returns,384 native
odd-destination diagnostics. Diagnostics are explicitly incomplete calls.
Three instruction mutations changed the selector mask, table mask and device
base; each48-case set reached terminal comparisons and was rejected. Guard
failures cannot qualify as successful semantic mutation detection.

## Run and merge boundary

Prepare without originals using the recipe in
[PROVISIONING.md](../../../tools/factory/PROVISIONING.md), then run the original
probe inside the existing offline process guard with verified input/native
mounts read-only and broker/auth/signing authority hidden:

```sh
python3 tools/saturn_lab/probe_netlink_dsp.py \
  --source-file /private/NLSND.container \
  --prepared /private/abi4/prepared --report /private/new-report.json
```

Use the configured shared admission limit, bounded processes and fresh output
paths. Actual evidence used limit3, lease180seconds,80instructions/case,
512MiB address space,60 CPU seconds and75 wall seconds per original process. Guardian
identities and terminal outcomes are retained. No provider call or account-policy
change was introduced. Actual account and CI spend is unknown.

The required `Pinned Godot and Saturn installation` aggregate now depends on the
applicable real native child. Missing, skipped or failed applicable child results
block it. Research Python tests alone are tooling evidence. Keep exact-head and
current-base CI and original revalidation distinct; publication/merge status
belongs to GitHub and the live coordinator checkpoint.

Parent665 still needs commands10/11 and natural caller/domain work. Whole SCSP,
DSP/audio timing, hardware comparisons, production Godot state/pixel/audio parity,
whole-code recovery, bot acceptance and Neptune continuity remain open.
