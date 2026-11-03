# Seeded Neptune policy streams

Issue [#445](https://github.com/elgansayer/Neptune-Bomberman/issues/445) is one
bounded part of #30 and #87. This is the enhanced Neptune heuristic, not measured
Saturn CPU behaviour. The pinned Godot/native addon baseline is unchanged.

Before adding a GameInstance to SceneTree, trusted match setup may set
`bot_policy_seed` to an integer. Null uses a fresh independently randomised seed.
`ServerBotManager.get_policy_seed()` records the effective value; owned fixtures
explicitly use 424242. `configure_policy_seed(int)` accepts changes only with an
empty roster. It does not reseed the global gameplay RNG.

The manager provisions one RandomNumberGenerator per participant into its native
controller blackboard as `policy_rng`, with policy version
`neptune-heuristic-v2`. The version includes the temporal routing, objective
selection and strategic reaction changes; it deliberately rejects v1 snapshots.
Stream seeds use the first 60 SHA-256 bits of
`<policy-version>:<decimal-match-seed>:<decimal-peer-id>`. Reproduction requires the
same stable participant IDs as well as the same match seed, policy and engine.
A second participant's planning never advances the first participant's stream.
The stream lives for the participant lifetime and is released on despawn.

The active BTWaitAmbush task uses this stream for its five equally selectable
idle directions; it no longer calls Array.pick_random on the global RNG. Missing
policy state stops movement and returns native FAILURE without a random fallback.
Timing, patrol radius, movement, fuse rules and safety assertions are unchanged.

## Trusted checkpoint API

`get_bot_policy_snapshot(peer_id)` returns a detached dictionary; unknown IDs
return an empty dictionary. `restore_bot_policy_snapshot(peer_id, dictionary)`
returns false without mutation for unknown participants, incorrect shape/types,
policy/engine/participant/seed mismatches and noncanonical/out-of-int64 state.
These are trusted authority methods, without RPC annotations or client commands.

Snapshot fields are strings: `format` (`neptune.bot-policy-rng/1`), `policy`,
`engine`, `peer_id`, `match_seed`, `stream_seed`, and `state`. Decimal int64 strings
preserve exact bits through browser/JSON paths, including values above 2^53.
Restore checks every identity before assigning the RNG state. Seeds and state
are reproducibility metadata, not authentication credentials.

This restores the next random choices, not complete match or behaviour-tree
state. A future replay/checkpoint must also capture clocks, timers, running task
state, map/ruleset/pack locks, actors and other subsystem streams. No cross-engine
RNG sequence compatibility is promised. General map/item/presentation RNG
partitioning remains #87; hidden-input observation filtering and held-out policy
quality evaluation remain #30–#32. No external model runs inside the game tick.

## Executable evidence

`tests/test_bot_policy_rng.gd` exercises real LimboAI tasks/controllers and owned
ServerPlayer fixtures. Two original-source cases fail: global perturbation changes
actions, and ambush consumes gameplay RNG. The candidate checks action equality
under unrelated random draws and a second bot's planning, distinct seeds/IDs,
JSON continuation, malformed restore atomicity, live-roster reseed refusal,
missing-stream failure, explicit fixture seeds and despawn cleanup. Nonconstant
directional output is a control against a no-op implementation passing.

The required merge gate runs these discovered cases within the full native suite.
The Godot workflow also exercises this focused suite with FPS caps 30/60/144.
Neither cadence checks nor RNG continuation prove complete match determinism,
reference fidelity, browser play or tournament quality.
