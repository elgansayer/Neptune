# Real-match bot liveness evidence

Run the current policy against real map collision, actors, bomb fuses, flame
damage and the normal authority clock:

```sh
python3 tools/godot/evaluate_bots.py --godot /path/to/pinned/godot \
  --evidence /tmp/neptune-bot-evaluation-unique
```

The wrapper executes the discovered `test_bot_match_liveness` suite through the
existing strict supervisor. Each case creates a fresh authority, starts its normal
countdown and provisions real BALANCED controllers with human-equivalent starting
inventory. It runs eight seconds of active play on the unmodified original
Neptune Standard and Neptune Twelve JSON fixtures, using separate fixed seeds.
There is no frozen physics, manually steered actor, synthetic bomb-placement
success or inventory boost. Test-only subclasses observe the production manager
and command dispatcher by invoking their unchanged `super` implementations.

Each `BOT_MATCH_EVIDENCE` record includes map and policy/physics/observation source hashes,
engine and policy identities, both seeds, participant commands and movement,
actual bomb creation, causal elimination events, terminal result if reached, and
manager callback p50/p95/p99/max wall costs. The enclosing JSON adds the executable
SHA-256, source Git head and dirty state. The source manifest includes the AI,
entities and observations directories plus room, command and clock/configuration
entry points; changes during a match fail its assertion. These hashes do not identify
the entire build; use an exact clean commit and retain the native CI identity for
a release comparison. Missing/truncated/duplicate match evidence fails the wrapper.

Movement statistics sample actors after real physics phases. If the engine runs
several physics steps before a render callback, these samples can miss intermediate
cells or reversals; they are liveness diagnostics, not exact tick replays. The
manager profiler captures every active manager callback up to a finite 4,096-sample
limit, including observation/perception and tree work, without replacing its
decision logic. Stage samples distinguish public observation refresh, authoritative
forecast, public forecast/predictor, decisions and opponent intelligence. Production
stage timing is disabled by default; the test profiler explicitly enables it.
Wall timings depend on host load and logging and do not influence policy decisions.

The runtime shares recursively immutable private observation payloads. Each policy
retains its own record objects and lazily materializes opponent groups when queried;
its own actor still refreshes on every observation revision. Public snapshots and
compound record getters return detached writable copies. The accompanying mutation
and privacy tests verify these boundaries, including accepted commands and player
departure within one simulation tick. Forecast reuse likewise requires the same
public calculation phase and exact clock, preserves an independent seconds cache,
and falls back to calculation for stale or forced observations. The legacy full-map
safety BFS is built on demand and invalidated on refresh.

Repeated hypothetical-bomb and placement-capability queries share a bounded
128-entry cache only for an identical public observation revision and exact
simulation timestamp. Position, range and fuse are distinct keys; callers receive
detached results. Same-tick bombs, terrain edits or roster/source invalidation clear
the previous assumptions. Unversioned raw authorities retain fresh calculations.
The regression suite checks actual shortened chains and blocker changes as well
as exact keys, export mutation and capacity bounds; caching never approves a
placement that the original calculation rejected.

The liveness assertions require every admitted bot to change tile, actual bomb
creation, enough real callbacks, complete elimination retention and no structurally
invalid policy commands. Ordinary refused actions remain recorded separately from
invalid commands. Deaths do not automatically fail these competitive matches:
`self_ko` establishes actual bomb ownership, not whether a death was avoidable.
An empty terminal result means this bounded excerpt ended before the match did.

The wrapper saves failing results as `passing: false`, preserves the log, returns
nonzero and refuses to overwrite a previous evidence directory. An engine/addon
compatibility error remains a failure even when individual scenario assertions
execute. No win-rate, full-match completion, deterministic replay, target-host
performance budget, browser session or AAA-quality promotion follows from these
two short runs. Follow the held-out tournament and experience requirements in
[the research and promotion contract](BOT_QUALITY_RESEARCH.md).
