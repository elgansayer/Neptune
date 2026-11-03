# Hosted casual round lifecycle

This is the development/demo configuration, not a measured Saturn timing claim.
The existing authoritative Godot simulation remains the only match clock and
command path. Hosted defaults are 180 seconds active, a three-second countdown,
a five-second results interval and filling to four total participants with the
existing `BALANCED` policy. Trusted startup flags `--room-duration` (1..3600),
`--room-countdown` (1..30) and `--room-intermission` (1..60) accept integer
simulation seconds. `--room-fill-to=0` still disables filling.

For the default legacy PCK's sampled destructibles, casual rooms reserve a
two-cell radius around each declared start. This prevents the random pattern
from trapping real safe-plant bots in two-cell pockets. Hard geometry, spawn
positions and explicit authored map/pack selections remain intact. The sampled
arena is then retained exactly for every rematch. This is a demo configuration,
not a measured Saturn starting-layout claim.

The public snapshot includes `round: {epoch, phase, remaining, result, config}`.
Phase is `waiting`, `countdown`, `active` or `results`. `remaining` is the
corresponding simulation duration; `config` announces the configured `duration`,
`countdown` and `intermission`. The compact `a` always includes an explicit
boolean, and compact display seconds round upwards. Initial-map messages carry
the same round envelope, simulation tick and simulation milliseconds. The client
rejects older epochs and older state ticks. Human input carries `round_epoch`;
the server rejects packets from a previous round before applying any command.

Existing completed-tick timeout/survivor settlement commits one detached result
and emits its terminal signal once. The terminal result includes its epoch. It is
repeated as snapshot data during results so an individual lost packet cannot hide
the outcome; repeated state is not a second settlement. No new reward or durable
statistics consumer is introduced.

After the results interval, ServerMain creates a fresh GameInstance outside the
physics query flush. It validates the same content lock/selection, restores the
original sampled arena and destructibles, carries connected human identities and
starts the next countdown. Accepted room filling creates the remaining real bot
controllers once for that new authority. The old authority is disabled, detached
and freed with all actors, bombs, flames, mounts, eggs, items, callbacks, bot tasks
and observation views. Each new authority starts its own simulation clock; the
strictly increasing server-owned epoch separates clocks, event IDs and snapshots.
The client clears its entire prior map, actors, effects and terminal UI on the
new epoch, without reconnecting or registering a new guest.

Late arrivals during active/results are capacity-bounded authenticated spectators
with current map/state. They receive actors at the next countdown before missing
seats are filled with bots. Bots never exclude a waiting human, and no live human
is evicted or spawned into ongoing flames. Concurrent human and pending content
admission cannot exceed the room's actual seat capacity. Duplicate connected
user identities are refused.

The last human departure disables the complete current authority immediately and
installs an empty waiting authority. There are no unattended bot-only rounds. An
arrival between departure and deferred teardown is transferred into a fresh live
countdown. In-flight exact-content transfers retain their existing bounded
readiness/timeout transaction before a handoff.

`tests/test_hosted_room_recovery.gd` checks repeated same-peer handoffs, fresh
world state, late spectator admission/bot replacement, explicit zero/default
filling, retained results, content-transfer protection, stale input/authority
rejection, last departure and the deferred-cleanup arrival race. Existing
`tests/test_round_settlement.gd` remains the focused atomic outcome coverage.
The exported browser/server gate supplies real browser input and repeat-session
acceptance; native tests alone are not public rollout evidence.
