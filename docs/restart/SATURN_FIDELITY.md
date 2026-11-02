# Saturn fidelity acceptance contract

Owner clarification: 1 November 2026. The faithful Saturn profile must reproduce
the selected Sega Saturn Bomberman release's complete maps, levels, assets,
timings, speeds, mechanics, effects, music and sound. This strengthens the existing
#29/#38 and #477 programme. It is a target, not a claim of implemented fidelity.

## Exact comparison boundary

Pin release/region, disc/BIOS/input lock, core/build/settings, controllers,
RTC/start state, native image format and audio output format before measuring.
USA MK-81070 V1.003 and Japan T-14302G V1.000 are separate references. Cross-check
critical behaviour through #513 and disclose shared emulator ancestry. Matching
digital captures does not establish matching display, speaker or device latency.

Exact acceptance requires equal canonical state and ordered events, native pixels,
and native-rate audio samples and event timing for the declared scenario. Record
the start origin and clock mapping. Do not hide mismatches through per-run
realignment, dropped frames/samples, resampling, masks, perceptual scores or widened
tolerances. Any fixed format conversion needs explicit reproducible evidence.
If measurement cannot resolve the claimed precision, exactness remains unverified.

Approximate checks remain useful for exploration and prototypes; they cannot
satisfy an identical-output claim. Intentional Neptune differences belong in an
explicitly selected profile. Accessibility/device settings preserve simulation
semantics and identify any presentation differences. Content publication follows
[OPEN_SOURCE_AND_CONTENT.md](OPEN_SOURCE_AND_CONTENT.md).

Complete source reconstruction is not a prerequisite for each slice. Recover
sufficient assets, data and semantics, implement them in Godot and compare them.
Continue broader code recovery alongside independently eligible creator, bot and
multiplayer work under [COMMUNITY_CONTENT.md](COMMUNITY_CONTENT.md).

## Required coverage

| Area | Measured contract and existing owners |
| --- | --- |
| Maps/levels | Rooms, collision, objects, spawns, transitions, secrets and variants across Normal solo/co-op, Master and standard/wide Battle. #395–#398/#410/#490/#494 |
| Mechanics/speeds | Numerical units, subpixels, collision/corners, placement/fuses/flames/chains, kick/throw/bounce, items/damage, enemy/boss/CPU policies, simultaneous-event priority and RNG order. #407/#491–#493 |
| Visuals/effects | Native texels/palettes, anchors/layers, animation durations/transitions, draw order, scrolling, camera/HUD and colour calculation over time. #399/#485–#487/#495/#429 |
| Music/sound | Samples versus sequences/CD/streams, trigger tick/sample, pitch/rate, intro/loops, envelopes, gain/pan, voice priority/stealing, DSP/mix, interruptions, pause and transitions. #399/#488/#489/#287 |
| Completeness | Per-release content/route/interaction inventory; separate discovered, decoded, measured, implemented, privately published and exactly verified. #409/#410/#515 |

VBlank, gameplay update, input polling, audio sample clocks, loading gates, pause
and slowdown are distinct measured domains. Never assume exactly 60 Hz or equate
Godot physics ticks with Saturn updates. Use explicit integer/fixed-point/rational
observation units where appropriate. The current [simulation clock](SIMULATION_TIME.md)
is infrastructure, not evidence of a recovered Saturn update schedule.

Presentation uses authoritative event time and the recovered timeline. Late event
delivery must not restart an effect at age zero or duplicate sound. Render rate
and audio buffers must not change damage/progression. Verify offline reference
parity separately from network and device latency.

Retain bounded lossless PCM with sample format/rate/channel order/count/hashes.
Check first divergent sample, long-run drift, loops, interruptions and missing or
duplicate events. Extracting a track or hashing original emulator audio does not
prove Godot playback parity.

## Bounded agent handoff

Use existing task `acceptance`/`evidence` fields, feature IDs, dependency proofs
and lease store; no second intake schema or scheduler is introduced.

1. Inspect live issue/PR/lease state. Select one unowned scenario with exact
   release, input timeline, initial state, time domains, outputs and precision.
   State fidelity applicability and explain genuinely unrelated checks.
2. A capture worker retains repeated unmodified original runs, verified source
   identities, checkpoints and uncertainty. Label forced/instrumented runs and
   check their consequences against unmodified execution.
3. A Godot worker implements the measured contract through existing simulation,
   rendering and pack interfaces. Candidate output cannot become its own oracle.
4. An executable verifier compares equivalent scenarios, records first divergence
   in source units and binds evidence to head/current base, acceptance revision,
   content lock, source/core/configuration/input/adapter hashes and replay commands.
5. Detect relevant deliberate one-tick/position/order, pixel/palette, frame-shift
   and sample/loop/trigger mutations. Missing/truncated/stale evidence and early
   termination fail. Preserve fixtures and original assertions.
6. Publish a focused PR and trusted private receipt. Apply
   [MERGE_POLICY.md](MERGE_POLICY.md); model approval is optional. Update issue and
   coverage only to the scope the executable evidence demonstrates.

## Next acceptance slices

Finish active bounded work first. Reuse these issues and split only independently
testable children. This order concerns fidelity; eligible community work continues.

| Result | Existing issues |
| --- | --- |
| Before continuity: compatible shared manual-session leases/heartbeats, restart recovery and effective shared slot accounting, then the next supervised job. Preserve caps and other sessions. | #536/#33/#514 |
| Feature-specific trusted private reference gate bound to actual source/candidate/acceptance identities; absent/stale applicable evidence blocks the fidelity claim. | #76/#511 |
| One campaign room and battle scenario in Godot: measured walk, bomb/fuse/flame/damage, effect frames and triggered sound; a music transition/loop window and a co-op interaction. | #29/#488/#489/#492/#493/#429/#284/#287 |
| Expand the same gates to rooms, variants, actors, CPU/enemy policies, menus, bosses, music and endings using observed stable inventory IDs. | #38/#395–#399/#410/#515 |

Stage #76/#511 without a dependency cycle: first implement #76's selection and
receipt interface with adversarial tool fixtures, then #511's authenticated private
experiment integration, then consume actual receipts for fidelity claims. Interface
tests establish the gate contract, not a real-reference result.

Concrete source leads at inspected main `33dd10d0022b3ca5366f0de85e9fdd95a94c1af0`:
[`ExplosionRenderer.initialize`](../../client/ui/explosion_renderer.gd) ignores
the provided start time and uses local wall-clock animation constants;
[`GameView.update_explosions`](../../client/game_view.gd) starts the paired effect
and sound when it first receives the explosion;
[`BombRenderer`](../../client/ui/bomb_renderer.gd) immediately plays OGG effects.
#284/#287/#429 should audit and replace the relevant faithful-profile paths using
measured clock/presentation contracts. These findings do not establish the correct
original values and do not justify inventing replacement timings.

## Tools and reusable workflows

Reuse Elgl Repo Factory and its supported provider broker. Scripts execute hot
frame/sample loops; agents plan, interpret bounded evidence and implement fixes.

| Capability | Status and useful next work |
| --- | --- |
| Original control | `tools/saturn_lab/frontend.py` provides bounded original replay and video/audio observations. Add retained bounded PCM/scenario outputs through #488/#489/#511; it is not a Godot parity runner. |
| State comparison | Reuse `tools/saturn_lab/compare_trace.py` and its [exact trace contract](../../tools/saturn_lab/TRACE_FORMAT.md). It reports the first divergence; source labels/hashes alone do not authenticate captures. |
| Pixel/audio diagnosis | Native pixel/palette/layer and sample-index PCM diffs, mutation controls and bounded outputs. Evaluate pinned FFmpeg/ffprobe and imaging tools through #508/#518. |
| Code/data analysis | Reuse #478 prior art and archive tools; validate Ghidra loader/headless analysis through #481. Smoke-test actual bounded adapter capabilities before use. |
| Agent skills | #508 packages tested capture/replay, decode/provenance, clock measurement, audiovisual comparison, divergence reduction and recovery. Require pinned tools, real commands, negative cases, resumable outputs and reproduction by another supported agent. |
| Operator dashboard | #80/#82/#515: job/lease/heartbeat, shared capacity, known spend, blockers, last actual parity run, first divergence, frame/sample drift and per-release coverage/unknowns. |

Reserve shared emulator/display/heavy-build resources as well as code paths.
Keep existing budgets, one-heavy-job policy and manual-session ownership. This
document neither starts providers nor increases concurrency. Read live #33/#536
before claiming a continuous service is running.

## Completion honesty

The current 5 metadata / 8 runner / 10 gameplay selections in
`tools/merge_gate/run.py` do not execute whole-game Saturn audiovisual parity.
#76/#511 own that integration. A tooling/documentation PR can pass its own checks
while game fidelity remains open. Schemas, green tool tests, issue closure and
worker summaries do not certify exactness.

Mark a slice exactly verified only for retained executable comparisons. Whole-release
fidelity requires a reconciled content/route/interaction inventory, applicable
state/pixel/audio checks, resolved independent disagreements and no required
unknowns. Unknown totals remain unknown; all discovered items passing does not
establish that every item in the game has been discovered.
