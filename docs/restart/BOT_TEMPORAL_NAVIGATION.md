# Temporal navigation and hazard intervals

The enhanced Neptune policy shares a bounded safe-interval planner through
`GridSampler`, `DangerAwareAStar` and the production `BTMoveToCell` action.
This extends the existing public-observation and authoritative-command path;
no movement, fuse, collision or damage rules change. It is not Saturn CPU parity.

## Forecast contract

`BombThreatForecast.build_timeline()` returns legacy earliest `deadlines`, an
ordered union of lethal `intervals`, and explicit `uncertain` capability notes.
Current public flames retain their inclusive expiration. Pending stationary
bombs use public lower and upper fuse bounds, their observed elapsed timer,
chain shortening, and conservative progressive-growth/physics-frame slack.
The public leisurely-fuse range is 5..6 seconds; its private sampled duration
never enters these observations or calculations. Remote bombs can be triggered
immediately and have no finite guaranteed automatic expiry.

The forecast retains an already exploding actor's original public pattern,
including arms not yet visible and paths fixed before a later wall appears.
Pending bombs conservatively extend past soft blockers that another observed
bomb may remove before their latest possible detonation. Geometry expansion
and chain shortening are monotonic and bounded; exhaustion uses a larger
soft-block-free envelope rather than silently omitting possible fire.
Kicked bombs conservatively
cover the blast cross at every possible earlier stopping cell along their
observed direction; this is an envelope, not an exact trajectory prediction.
Airborne observations include the fixed remaining waypoints, bounded remaining
flight duration and possible final ground cells. Landing restarts the full public
fuse; paused pre-pickup elapsed time is not subtracted. The forecast also covers
chain-triggered airborne actors that continue flying before native expansion.
Carried bombs retain a local four-direction throw/drop envelope. Their owner's
future private choice remains unknown: both planting-checker entrypoints refuse
intentional planting near this uncertainty, while distant play remains available.
Other players' new actions require a fresh observation. This does not predict private inputs,
future placements, arbitrary bounce paths or every creator-authored effect.

Times use authority milliseconds. Lethal intervals round outwards to whole
milliseconds before storage in engine `Vector2` values, preventing ordinary
float rounding from clearing an inclusive boundary early. The planner adds a
100 ms margin on each side of a hazard. Unknown or inconsistent upper bounds
remain infinite rather than acquiring an invented clearance time.

## Search and execution

A search state includes a tile, its safe interval, arrival time, traversed-edge
count and predecessor. A deterministic A* heap orders candidates by earliest
possible goal arrival. Labels preserve arrival/depth alternatives so a
short-step budget cannot discard a later but shorter feasible route. An edge
requires both its source and destination to remain clear for the complete
crossing; a wait also requires the source to stay clear throughout the wait.
The first crossing uses the actor's actual public world position, including
an off-center start; later crossings use tile-center distances.

Default bounds are 2,048 expanded states, 8,192 generated states, a 12-second
future horizon, at most 64 hazard windows per cell, and the caller's step limit.
The result distinguishes `found`, `unreachable`, `invalid` and `exhausted`.
An empty path or exhausted search is never interpreted as proof of safety.
Earliest-deadline callers retain their conservative API; interval callers receive
explicit waypoint arrival and departure times.

`BTMoveToCell` executes a scheduled wait with zero movement input, rechecks the
remaining source/destination windows on fresh observations, and replans for new
fire, walls, bombs or player obstacles. An intentional wait does not accumulate
stuck penalties. Actual movement remains `ServerPlayer` physics; no position
snapping or teleporting is added. Unstoppable-virus actors cannot schedule a
stationary wait. Movement tests that freeze the game clock must advance that
clock explicitly when exercising real motor callbacks.

Entering or continuing an intentional wait resets both the stuck counter and its
timestamp. Legal departure then starts a fresh 500 ms nonmovement window; time
spent waiting cannot abandon or penalise a valid target. Actual stalls retain
the same deadline and penalty. `test_bot_route_wait` reproduces a brief idle
followed by a new public flame, repeated scheduled waits, real motor resumption
and genuine stalls before and after a wait without changing those thresholds.
The [retry receipt](evidence/2026-11-03-netplay-retry.json) retains the failing
baseline, cadence checks, related movement scenarios and passing full native run.

The existing escape search keeps its established conservative refuge choices.
When a single lethal deadline cannot find a refuge, a bounded multi-goal interval
search can wait for temporary fire to clear, while requiring the final refuge's
last safe interval to have no later known hazard. A source bomb whose deadline
arrives before the corridor clears still refuses this wait.

## Evidence and limits

Focused suites are `test_bot_route_wait`, `test_temporal_navigation`, `test_temporal_route_runtime`
and `test_hazard_intervals`; retain `test_bomb_forecast` and
`test_public_observations` as forecast/fairness regressions. They cover detours,
separate/overlapping flames, inclusive expiry, search bounds, deterministic
schedules, actual native waiting and crossing, moving player obstacles,
source-bomb deadlines, progressive native blast lifetimes and hidden-fuse
sample independence. Actual engine/build, command results and log identities
belong in the accompanying validation receipt.

These scenarios do not establish arbitrary future opponent-carrier movement,
all combinations of moving-bomb semantics, safe traversal
through a currently occupied bomb after its disappearance, mode/team competence,
held-out tournament strength, browser play, or production tick budgets. Whole
policy quality still requires the gates in [BOT_QUALITY_RESEARCH.md](BOT_QUALITY_RESEARCH.md).
