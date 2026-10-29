# Online bots are a core feature

The product must remain enjoyable with a small player population. Bots provide
real opponents in casual online rooms, solo practice, configurable challenges and
repeatable playtests. This is a major product workstream alongside extraction and
fidelity, not only a testing convenience.

Read [COMMUNITY_CONTENT.md](COMMUNITY_CONTENT.md) for the expanded contract. Bot
role and policy lineage are independent: competitive opponents, cooperative
companions and authored campaign enemies/bosses can share bounded navigation and
hazard infrastructure without sharing objectives or fairness assumptions. #55
adds role-specific proof; #30–#32 remain the initial competitive priorities.
Unknown mod effects must never be assumed safe from untrusted author hints.

## Two explicitly different policies

1. Saturn CPU: behaviour reproduced from the selected original release, difficulty
   and mode using the research lab's recordings and experiments.
2. Neptune bots: improved, configurable opponents designed for the new online game.
   Preserve the game's rules while adding tactical quality and personalities.

Do not change the reference rules to make bots stronger. Do not label a tuned
Neptune bot as Saturn-accurate without parity evidence.

## Product requirements

- Server-controlled bots can fill casual rooms to the configured player count.
- Bots are visibly identified; show policy/difficulty without pretending they are people.
- Host controls for bot count, difficulty, teams and behaviour profiles.
- Joining humans can replace bot seats at a documented safe boundary, initially
  the next round. Avoid changing control in the middle of a decisive action.
- Optional disconnect takeover, with identity/state ownership and reconnection
  rules tested; this is separate from ordinary room filling.
- Default ranked human leaderboards exclude bot-filled matches. Dedicated bot
  challenge boards can exist with clearly identified rules and policy versions.
- Both browser and desktop players see the same authoritative bot actions.
- Validated community maps must support bots or explicitly declare unsupported
  mechanics with a clear compatibility reason. Never silently treat unknown hazards as safe.

## Implementation direction

First audit the current LimboAI/utility/pathfinding stack and reproduce failures.
Keep useful working components. Prefer a behaviour tree for top-level priorities
with utility scoring for tactical choices, bounded search and time-aware navigation.

Bots submit actions through the same validated command semantics as human players.
The implemented placement boundary and remaining command work are documented in
[BOMB_COMMANDS.md](BOMB_COMMANDS.md). Movement and ability dispatch are described in
[PLAYER_COMMANDS.md](PLAYER_COMMANDS.md).
They do not teleport, alter speed/fuses or directly grant items. Feed them an
explicit observation view. Hidden item contents, private opponent inputs and
unobservable future events must not leak through server-state access. A visible
bomb's observed placement time may be remembered to estimate its fuse.

Use simulation ticks and a seeded policy RNG. Difficulty changes reaction delay,
planning budget and deliberate fallibility rather than hidden stat boosts.
Share bounded hazard computations where semantics are identical. Keep gameplay
decisions local and bounded; no external LLM requests inside the match tick.

Per-participant policy seed/state and its limits are documented in
[BOT_POLICY_RNG.md](BOT_POLICY_RNG.md).

The implemented authority clock and its units/physics phases are documented in
[SIMULATION_TIME.md](SIMULATION_TIME.md). Controlled clock experiments are separate
from complete policy RNG, fairness and replay determinism acceptance.

Decision priorities: immediate survival, safe movement/escape, useful item/block
collection, attack opportunities, positioning and team objectives. Require plan
commitment/hysteresis to avoid oscillation, with immediate replanning on material
hazard changes. Safe planting must consider shortened chains, moving bombs,
active flame intervals, blocked escape paths and supported special bomb rules.

## Specific current-source audit leads

These are source-level findings at `6da6f5...`, not runtime-confirmed fixes:

- `shared/ai/ai_manager.gd`: hypothetical planting uses a fixed 3000 ms fuse and
  adds blast tiles without recomputing hypothetical chain effects.
- `shared/ai/planning/bomb_safety_checker.gd`: repeats fixed 3-second assumptions;
  verify route timing, chain reactions and dynamic hazards against actual simulation.
- `AIManager.update_opponent_intel`: updates `last_seen_pos` before calculating
  `last_dist`, so both distances use the new position in this method. Reproduce
  whether aggression estimation is affected and add a focused regression.
- `shared/ai/base_ai_controller.gd`: inspect the apparent triple-quoted source
  wrapper and whether this file is loaded before treating it as an active controller.
- `tests/bot_test_suite.gd`: a null test result counts as success; inspect actual
  assertion contracts and fail on execution errors or missing assertions.
- PRs #18 and #20 overlap on test discovery/selection. Reconcile them before
  measuring bot quality. Observe the real runtime, not just test summaries.

## Evaluation contract

Each run records engine/build, policy version, difficulty, ruleset and map hashes,
seed, participant types, replay/event evidence, result and CPU timing. Use held-out
maps and seeds for promotion; a worker may not tune against all evaluation cases.

Initial deterministic scenarios:

1. Walk a fixed route without alternating indefinitely between adjacent tiles.
2. Escape an own bomb when an actual feasible escape exists.
3. Refuse a placement whose escape is cut off by an earlier chain reaction.
4. Avoid active flames until they expire; respond to newly blocked paths.
5. Collect reachable items while respecting the survival priority.
6. Exercise kick/throw and supported special mechanics without invalid inputs.
7. Complete mixed human/bot rooms, bot replacement and reconnect cases.

Measure avoidable self-KOs separately from unavoidable deaths; do not promise zero
deaths in adversarial play. Track win rate with sample sizes/uncertainty, survival,
idle/oscillation time, item efficiency, invalid actions and p95/p99 tick cost.
Benchmark ten-player Saturn scenarios, twelve-seat extensible rooms and multiple
matches on the target host before declaring performance adequate. Establish
numeric budgets from that baseline.

Power-inspired modes require mode-aware objectives, not only survival logic.
The mode/pack capability contract supplies observable objectives and hazard rules.
Test score pursuit, team cooperation and tie/timeout decisions after observing each
mode. Refuse unsupported mechanics explicitly rather than treating unknown hazards
as safe. Keep mode-specific tournament results separate from aggregate win rate.

AI development agents can run tournaments, inspect replays, propose policy changes
and tune parameters offline. Promote a candidate only if regression, fairness,
held-out quality and performance gates all pass. Keep the prior policy available
for rollback. Optional learned policies come after a reliable heuristic baseline.
