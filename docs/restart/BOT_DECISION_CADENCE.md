# Strategic reaction and immediate hazard reflex

Enhanced Neptune policy `neptune-heuristic-v2` uses the personality's existing
`reaction_time_ms` before selecting each new intentional goal. The production
tree waits using the authority's simulation clock, then chooses an attack,
collection, farming or patrol objective. Callback delta, rendering rate and host
uptime cannot finish the wait. While waiting the actor submits neutral movement;
after a goal starts its native movement task continues every physics tick.

The root uses a dynamic selector. Its higher-priority public-hazard branch can
interrupt a running strategic wait or objective in the same controller update.
This is an explicitly immediate survival reflex shared by the personalities.
It uses the same public bomb/hazard observations and validated movement commands;
it grants no inventory, speed, fuse, collision or damage advantage. Waiting to
select a new strategic goal is not a delayed observation model or a complete,
tuned difficulty system. Safe-interval waiting within an escape route remains
part of survival execution and is not subject to this strategic delay.

The manager remains the sole native tree update owner. Inactive matches submit
neutral movement and do not execute the policy. The original single-update
regression in `test_bot_physics_ticks` continues to apply. There is no second
scheduler, model request or background decision thread in this change.

`test_bot_decision_cadence` checks every configured personality's first eligible
simulation time, frozen-clock behavior despite large callback deltas, a new
deadline per new goal, native execution continuity after eligibility, and the
actual production tree interrupting a 500 ms strategic wait after observing a
real bomb. These are cadence/priority regressions, not a full fairness or
human-experience certification. Observation delay, planning budgets, fallibility,
difficulty selection UI, held-out tuning and browser/network latency comparisons
remain separate work.

Attack and planting estimates also use public skate and virus speed rather than
the old fixed five tiles per second. `test_bot_attack_safety` checks public speed
propagation and that an unsuccessful escape or insufficient finite margin cannot
become permission to attack. These checks do not establish support for every
special bomb or make the enhanced policy Saturn-accurate.
