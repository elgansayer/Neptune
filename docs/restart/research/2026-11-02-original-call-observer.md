# One naturally observed original SH2 helper call

Issue #597 / [PR608](https://github.com/elgansayer/Neptune-Bomberman/pull/608).
This extends the [isolated original-byte arithmetic/stack result](2026-11-02-saturn-table-address-result.md)
with one real original-game entry/return and a matched-core instrumentation
comparison. It does not finish #482/#483, code recovery, extraction or game parity.
The [derived receipt](../evidence/2026-11-02-original-call-observer.json) records
identities, selected values, exact comparisons and limits. Private media, states
and raw traces remain outside Git.

## Observed result

The accepted USA reference checkpoint at frame 33960, followed by ten frames of
port-zero Start and release through frame 34559, reaches the original helper
`0600B934` at frame 34213. Its observed arguments are `(0,0)`, return context
`PR=0600BAEE`, SP `060BFE4C` and MACL 10240. The return value is `00207F74`, with
SP/MACL and the other declared registers/flags preserved. Entry/return scheduler
timestamps are 271179/271211 in the same frame, separated by 14 observer dispatches.
These are core scheduler/dispatch units, not a hardware-cycle measurement.

The observed return context agrees with the static original BSR lead at
`0600BAEA`; the observer did not separately capture that caller instruction.
One natural argument pair does not establish all callers, the full argument
domain or the helper's gameplay purpose. The screen/room itself is still
unidentified; this is not authenticated campaign/battle evidence.

## Real preparation, repeatability and controls

The existing provisioner built a new isolated matched-core generation and
validated exported ABI v2, invalid-entry/budget/frame fences and immutable reuse.
The accepted original core remains unchanged. Recipe hash is
`54cfecd0f16c98e1523854c8d293da4beb6a731dd09a9374c5cf0c43318ea2a2`;
the built observer core is
`0f14356da70ac8b88a8a1727e25acf6137be4ace453c37b1819d82222346faca`.
The unprivileged preparation used one shared host slot, one make job, a 3 GiB
address-space bound and a shared deadline. No provider reservation was created.

Six fresh guarded/offline processes ran 600 original frames each: twice on the
unmodified reference, twice on the observer core disabled, twice enabled.
All six agree on canonical imported/final state, per-frame native video/audio,
inputs/polls and resident original helper/literals. Both enabled traces are
byte-identical, SHA256
`c8dda8b2cb04166b8ad96f54fd916299364bf046c25dd9ae3034a0ecac937194`.
The observer stops after the requested first pair; it does not claim full-window
call coverage. Explicit imports validate this checkpoint/window, not arbitrary
cross-core portability. Historical locks/checkpoints were never re-pinned.

Median whole-run seconds were 7.2953 reference, 7.0450 disabled and 6.9079 enabled.
This two-repeat measurement includes the period after recording stops and normal
host noise; it establishes neither a speed improvement nor steady-state tracing
overhead or hardware accuracy.

Ten mutations of retained real artifacts were rejected: state, video, audio,
undeclared input, return value, SP, MACL, dispatch coverage, empty records and
invalid timing. Artifact hashes were updated for those controls, so rejection is
not merely a stale-checksum failure. These are observer/comparator controls;
they are not original-game RAM mutations or production-Godot regressions.
Owned C fixtures separately exercise nonmutation, pipeline/delay boundaries,
counter/record overflow, incomplete pairs, JIT rejection and exact-sized buffers.

## Retained failures and continuation

The first nested user-namespace attempt failed before execution. Moving network
isolation outside the existing guarded runner passed offline/read-only/hidden
authority assertions without host-root privileges or credentials in the worker.
Earlier 120-frame windows yielded no calls. A 600-frame window from frame 33360
then recorded 128249050 master dispatches and zero calls: a real executed window,
correctly rejected. Advancing to the already captured frame 33960 checkpoint
produced the observed call above. All unsuccessful evidence remains preserved.

Private evidence lives under `neptune-research-private/597/`: preparation receipt
is in the canonical `.factory-tools/trace597-validation-003` generation,
`transition-enabled-004` retains the zero-call failure, `transition-enabled-006`
the discovery, `repeatability-007` the six runs/comparison, and
`captured-controls-008` the rejected actual-derived controls. Supervisors and
bounded commands are retained in `neptune-evidence/trace593/` (historical folder
name). [Reusable commands and limitations](../../../tools/saturn_lab/CALL_TRACING.md)
allow the existing factory to repeat the experiment.

Next recover additional natural arguments/return contexts and the callers' state
contract under #483. Slave execution, overlays, memory/DMA/CD tracing, sound/DSP,
full executable/function denominators, identified campaign/battle scenarios and
Godot state/pixel/audio comparisons remain open. Continue shared manual-session
enrolment/recovery #536 before enabling unattended Neptune provider continuity.
