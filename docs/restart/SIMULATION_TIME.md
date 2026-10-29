# Authoritative simulation time

Each GameInstance owns a monotonic session clock and physics-step counter:

- `get_simulation_time_msec()` returns elapsed simulation milliseconds (float).
- `get_simulation_time_sec()` returns the same clock in seconds.
- `simulation_tick` counts physics callbacks, including countdown/cleanup callbacks.
- `get_clock_state()` returns a snapshot with `server_time` in milliseconds and
  `simulation_tick`; regular state packets include both fields.

The clock starts at zero when the instance is created. It advances by the actual
physics `delta`, so engine time scaling changes simulation pace without changing
durations in game time. A paused SceneTree stops the authority and its child actors.
Disabling the authority's physics callback stops its clock; individually stepping
or unpausing child nodes is a testing/debugging operation, not a complete room pause.

The explicit Godot 4.5 physics phases are authority clock/status at priority -200,
bombs at -150, bot hazard publication/decisions at -100, then player movement at
default priority 0. This makes observed bomb elapsed time and danger deadlines
agree at the decision boundary. BotManager refreshes AIManager and HazardPredictor
after bomb advancement. Immediate placement queries use the same current clock.
Idle process priority is separate from physics process priority.

A child `SimulationStatePublisher` runs at physics priority 100 after the actors.
It publishes only when the authority's existing network interval is due. Thus the
packet's clock/tick and actor state describe the same completed physics step.
Disabling the authority's physics also disables this publisher's work. Sending
inside the early clock phase would label previous-step positions with a newer tick.

This is the implemented Neptune simulation schedule, not a measured claim about
either reference game's simultaneous-action ordering. Reference profiles still need
the research experiments. Existing fuse, movement, status-duration and safety-margin
values are unchanged; their timing now shares one physics origin.

Active AI tasks use `shared/ai/simulation_time.gd` with their configured authority
from the blackboard. A missing authority is an execution error, with no wall-time
fallback. OpponentTracker is configured with the same GameInstance. Stuck detection
uses simulation elapsed time and its existing distance threshold; it no longer
applies a second time-scale adjustment to movement already scaled by physics delta.

Bomb forecasts, active-flame expiry, placement grace, tactical locks, movement
penalties, observed opponent times, virus expiry, immortality and server explosion
retention use simulation time. Zero is a valid hazard deadline. Mortal-danger
queries compare a deadline with `now + time_to_safety + buffer`.

Network ping/latency, transport-input age and local client interpolation/rendering
retain wall clocks for their respective processes. Client rendering already treats
received explosion start time as metadata and starts its visual animation locally.
The existing virus countdown compares `virus_end_time` against the newly supplied
`server_time`, both in simulation milliseconds. Do not compare either value with
client or host uptime. Browser/native transports must carry these primitive fields
without replacing them with local timestamps.

This clock is necessary for reproducible experiments; it does not alone establish
full replay/policy determinism. Policy RNG isolation, observation filtering, causal
death attribution, held-out tournaments, dynamic/special hazard intervals and
network prediction/reconciliation remain separate #30–#32/#45 work. A restored
session will also need its clock/tick restored with the remaining replay/checkpoint
state. No complete checkpoint/replay format is introduced here.
