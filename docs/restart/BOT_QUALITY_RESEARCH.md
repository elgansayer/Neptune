# Building production-quality Neptune bots

Research and source audit: 3 November 2026. Scope: the current Godot game and
enhanced Neptune opponents, with separate requirements for companions, authored
enemies and faithful Saturn CPUs. Related existing work: #30, #31, #32 and
BOT-001..018 in the [catalogue](backlog/INDEX.md#bot-competitive-bots-companions-and-enemies). These are continuation
recommendations, not new claims that an issue is unowned or complete.

The practical route is to strengthen the existing public-observation,
LimboAI, utility and navigation stack, then promote policies using measured
gameplay. A stronger heuristic, a successful spawn, or a green scenario suite
does not establish AAA quality. That requires reliable movement, fair and
readable decisions, effective tactics, appropriate difficulty, complete mode
support, stable multiplayer lifecycle and demonstrated performance together.

## What is already useful

The production path is `main_server.gd` → `GameInstance` →
`ai/bot_manager.gd` → `ai/trees/bot_default.tres`. The manager creates native
LimboAI controllers, drives them once per active physics callback, and passes
observed actors and a bound command port into their blackboards. The older
`ai/bot_controller.gd` is not the controller created by this admission path;
changing its decision interval would not tune these bots.

| Component | Source-audited capability | Limit to preserve in claims |
| --- | --- | --- |
| Room admission | Capacity and spawn reservations, initial-countdown fill, rollback of a failed fill batch, explicit participant metadata | Initial fill is not next-round human replacement, reconnect takeover or an entire match test |
| Public observations | Detached visible arena data and actor-bound validated commands; covered drops, private inputs and sampled secret fuses omitted | Trusted GDScript remains reflective; this is not a community-script sandbox or equal network latency |
| Authority clock and RNG | Simulation-time queries and a seeded stream per bot | Policy RNG state alone is not a complete deterministic replay/checkpoint |
| Bomb forecasts | Public fuse bounds, active-flame intervals, conservative progressive-growth windows, chain/soft-block-removal envelopes, possible kick corridors and public airborne landing observations; earliest-deadline compatibility queries remain available | Unknown carried choices and incomplete flights remain explicit; conservative envelopes are not precise future trajectories or certification of every special mechanic |
| Behavior tree | Escape, tactical attack, collection and farming branches with native actions | Available branch names do not prove robust priorities or that every ability succeeds |
| Elimination events | Actual damage provenance, original actor incarnation, direct/lingering flame sources and nullable self-KO | Self-KO does not establish avoidability, chain initiator, assist or ranking credit |

Reuse the documented [observation](PUBLIC_OBSERVATIONS.md),
[command](PLAYER_COMMANDS.md), [room](ROOM_BOT_FILL.md) and
[elimination](ELIMINATION_EVENTS.md) interfaces. Avoid a second bot scheduler,
another movement authority or a separate simulator whose rules drift silently.

## Research findings and the engineering decisions they support

**Use spatial and temporal state together.** Phillips and Likhachev's SIPP
represents configurations with safe time intervals and searches feasible
transitions between them. It supports waiting through temporary obstacles
without enumerating every possible timestep. Applying it here is an engineering
inference: interval forecasts could let a bot wait for fire to clear and then
cross, rather than treating an eventual blast as permanent. The planner's
guarantees would depend on correct hazard trajectories and movement timing;
they do not transfer automatically to uncertain opponents or Godot collision.
[SIPP, ICRA 2011](https://www.cs.cmu.edu/~maxim/files/sipp_icra11.pdf).

**Search far enough to see a bomb resolve, while bounding branching.**
Osogami and Takahashi combine shallow tree search with deterministic pessimistic
future scenarios; their agents placed first and third in the 2018 Pommerman
competition. This supports evaluating delayed blast consequences and possible
opponent escape denial within a fixed budget. Neptune should compare a small
set of immediate actions followed by conservative hazard rollouts, rather than
copy the paper's rules or treat one predicted opponent action as certainty.
Pommerman's discrete rules and limited visibility differ from this game.
[Competition paper, ACML 2019](https://proceedings.mlr.press/v101/osogami19a.html).

**Keep behavior trees and add utility where choices compete.** Bill Merrill
describes integrating utility selection into an existing behavior tree. This
fits the current architecture: survival remains a hard constraint, while
reachable loot, farming positions, offensive pressure and map control can
compete on explicit scores. Add commitment and switching cost so minor score
changes do not reverse movement every tick. This is an application proposal,
not evidence that a particular utility formula improves Neptune.
[Building Utility Decisions into Your Existing Behavior Tree](https://www.gameaipro.com/GameAIPro/GameAIPro_Chapter10_Building_Utility_Decisions_into_Your_Existing_Behavior_Tree.pdf).

**Quality includes fairness and dependable movement.** Michael Booth's Valve
presentation discusses robust navigation, reaction time, imperfect knowledge,
predictable decisions and action-transition diagnostics for human substitutes.
Those are useful production criteria here. Its game-specific teleport and
friendly-fire exceptions are not compatible defaults for competitive Neptune;
retain the same authoritative movement and damage rules as humans.
[The AI Systems of Left 4 Dead](https://steamcdn-a.akamaihd.net/apps/valve/2009/ai_systems_of_l4d_mike_booth.pdf).

**Measure varied multi-agent play.** The Pommerman authors identify planning,
opponent/teammate modeling and communication as distinct challenges. A bot
beating one weak opponent or surviving an empty arena says little about team
support or exploit resistance. Use several frozen opponent policies and separate
solo, free-for-all, team and objective cohorts.
[Pommerman: A Multi-Agent Playground](https://arxiv.org/abs/1809.07124).

**Report uncertainty.** NIST describes proportion confidence intervals, including
Wilson and exact binomial methods. Use them for genuinely independent binary
outcomes; rotate seats and resample whole seed groups for paired policy
comparisons so correlated games are not presented as independent evidence.
TrueSkill can help summarize multi-party and team results with uncertainty,
but a rating cannot replace safety, fairness or performance gates.
[NIST confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm),
[TrueSkill, Microsoft Research](https://www.microsoft.com/en-us/research/publication/trueskilltm-a-bayesian-skill-rating-system-2/).

### Existing implementations inspected

The following are source inspections, not reproduced tournament results. They
inform independently implemented Neptune changes; no upstream implementation or
trained weights are copied into this Apache-2.0 project.

| Source and inspected identity | Concrete implementation finding | Neptune decision |
| --- | --- | --- |
| [BorealisAI action filter](https://github.com/BorealisAI/pommerman-baseline/blob/b909bb09283074747eea1ef694d4275a32d9fc1c/action_prune.py), `b909bb09283074747eea1ef694d4275a32d9fc1c` | Recomputes shortened bomb lifetimes, compares escape steps to danger, and performs a hypothetical-plant lookahead. Kicking is disabled by default and other agents are treated as static. | Preserve an explicit legal/safe action boundary before tactical scoring. Reuse Neptune's chain forecast and actual movement rules; do not inherit discrete-step assumptions or mistake the filter for a complete opponent model. |
| [Pommerman MCTS baseline](https://github.com/tambetm/pommerman-baselines/blob/b08a21e661cb9fe71c1bd10e9f3b36305f3d761d/mcts/mcts_agent.py) and [neural variant](https://github.com/tambetm/pommerman-baselines/blob/b08a21e661cb9fe71c1bd10e9f3b36305f3d761d/mcts_nn/mcts_nn_agent.py), `b08a21e661cb9fe71c1bd10e9f3b36305f3d761d` | Uses visit/value/prior action statistics and a bounded iteration count; the neural variant supplies policy/value estimates at leaves. The experiment restores full environment JSON, models other actors with `SimpleAgent`, and leaves the normal `act` entry point unimplemented. | Useful as a search experiment, not a drop-in fair online bot. Build any forward model from permitted observations and verify it against authority physics first. Keep a fixed search budget, a safe fallback and an ensemble of opponent assumptions. This inspected repository declares GPL-3.0, so no source is transplanted. |

The dypm/Hakozaki algorithm was inspected through the authors' paper, including
its longer pessimistic continuation and survivability objective. The paper
identifies competition Docker artifacts; this research did not obtain or run
their executable source. No verified standalone implementation named
“Dyp-MCTS” was located, so that name is not presented as an audited dependency.
[Authors' technical report](https://dominoweb.draco.res.ibm.com/reports/RT0982.pdf).

Kartal and colleagues also evaluate planning-guided asynchronous RL, using
shallow MCTS as a demonstrator, in a two-player miniature Pommerman setting.
That supports investigating offline imitation of a reliable planner after the
baseline is sound; it does not establish that a learned policy will improve
twelve-seat Neptune play or remove the need for a deterministic safety layer.
The accompanying change therefore improves bounded heuristic positioning
directly, without a new training service or per-tick model dependency.
[Safer Deep RL with Shallow MCTS](https://arxiv.org/abs/1904.05759).

## Bounded improvements in the accompanying code change

These describe implementation scope. Actual executed commands, engine identity,
passing/failing counts and limitations belong in the change's validation evidence.

- Hosted casual startup requests four total participants by default, capped to
  the selected room/map/preset capacity. Existing humans and reservations count;
  explicit `--room-fill-to=0` disables filling. Explicit excessive targets still
  fail. Filling uses the existing countdown transaction, not debug spawn RPCs.
- Temporal routing uses bounded safe-interval A* with actual route travel and
  source-departure occupancy instead of Manhattan displacement as elapsed time.
  It can schedule a wait for observed fire to clear, records departure times
  for movement, and revalidates cached routes on public hazard changes. Existing
  earliest-deadline callers retain conservative semantics. This implements the
  interval-search technique, not complete trajectory prediction or a safety
  guarantee against adversarial future moves.
- Item selection targets the actual reachable item, prices real route length,
  skips unreachable objectives and clears stale targets on failure. Tests include
  selection around a wall and collection through native movement physics.
- Opponent intelligence compares the previous position before overwriting it,
  handles the first observation neutrally, and updates shared spatial statistics
  once per observed player rather than once per bot. An aggression estimate is
  a heuristic, not access to an opponent's private intention.
- Aggressive chase now searches reachable firing positions instead of choosing
  a greedy adjacent flank repeatedly. The current tile is a valid candidate,
  existing fire and occupancy exclude approaches, and candidates use actual
  effective range, route depth, covered opponent exits and available own exits.
  A bounded shortlist receives the existing plant-escape precheck at actual
  actor speed. Invalid/unreachable attacks release their target for farming or
  collection. A target is provisional; final movement and planting still
  revalidate current public state. This is not MCTS or a guaranteed trap.
- Remote inventory is consumed through the same validated detonation command
  as human input, after the strategic reaction wait and from a refuge outside
  observed blast lanes. An already exploding old remote cannot hide the next
  eligible bomb. Native tests cover real explosions, ownership, unsafe lanes
  and the actual production tree.
- Strategic goals observe a simulation-clock reaction wait while ongoing motor
  execution retains physics cadence. A higher-priority public-hazard reflex can
  interrupt the wait immediately. This consumes the existing profile reaction
  setting; it is not delayed perception or a complete difficulty model.
- Production kick actions now issue ordinary validated movement and remain
  running until public state confirms real physical contact. The attack selector
  contains the kick action, and the danger branch can aim an adjacent normal
  bomb toward an opponent before its defensive fallback. Attempts have a bounded
  timeout and reject insufficient fuse time, missing ability, burning lanes and
  stopping geometry that still hits the kicker. Earlier public chain deadlines
  override a candidate bomb's nominal fuse during the contact check.
  Moving-opponent prediction and
  all special-bomb trajectories remain unproven.
- Farming replaces the 41×41 spatial scan and repeated per-candidate pathfinding
  with one reachable-tile BFS (default maximum 256 cells), at most twelve escape
  checks, cached valid goals and a short negative-result cooldown invalidated by
  public terrain/occupancy/hazard changes. Diagnostics default off; explicitly
  enabled snapshots reuse cached scores rather than rerunning gameplay searches.
  These are work bounds and measured regression contracts, not a target-host
  twelve-seat CPU or tail-latency result.
- Planting treats visible players and live bombs as current obstructions, with
  the evaluated actor explicitly excluded from its own hypothetical route.
  Missing safety support and unsuccessful marginal searches refuse planting;
  personality cannot turn a failed escape into permission. Unresolved nearby
  projectile choices have an explicit placement capability refusal.

The focused suites are `test_temporal_navigation`,
`test_temporal_route_runtime`, `test_bot_item_collection`,
`test_bot_opponent_intel`, `test_bot_attack_positioning`, `test_bot_kick_tactics`,
`test_bot_farming_budget` and the extended room-fill cases. None is a held-out
tournament, a browser/native match, or a Saturn CPU comparison.

`tools/godot/evaluate_bots.py` adds short real-physics liveness runs on fixed
four- and twelve-seat maps/seeds. It retains actual movement, planted bombs,
command outcomes, causal eliminations and sampled manager timing, and preserves
supervisor failure when engine/scripts are rejected. These are two diagnostic
scenarios, not a tournament, an avoidability classifier, or statistical evidence
that the proposed promotion thresholds have been achieved. Use the accompanying
validation receipt for the exact build, source identities and actual results.

## Implementation sequence through the existing backlog

### 1. Finish hazard and escape contracts: #151, #152, #153, #162, #294

Complete the shared interval forecast and time-dependent occupancy model.
Current conservative growth, overlapping fire, soft-block removal, kick and
airborne landing envelopes need broader mechanic comparisons. Complete dynamic
obstacle interactions, carrier movement/throw choices and supported special
effects against actual runtime behavior. Keep
observed fuse uncertainty separate from private sampled values. Include hurry
boundaries only when their future state is public under the selected policy.

Extend the current `(tile, safe_interval)` search and waiting integration using
real mechanic comparisons. Account for actual speed, off-center position,
reaction delay, collision clearance and turns. Plant only after simulating the candidate
and finding a viable escape, including the first departure and subsequent
retreat. Revalidate when a bomb moves, terrain changes, a player blocks the
route or the command is refused. Return an explicit exhausted/unsupported result
instead of interpreting a failed search as safety.

For every supported mechanic, compare forecasted intervals and occupancy against
the authoritative simulator, including near-boundary and mutated cases. Known
built-in bomb IDs currently accepted by the observation layer do not certify
their forecast coverage. Publish capability gaps before advertising support.

### 2. Make action selection stable and tactically useful: #155, #156, #97

Retain a goal until reached, invalidated or decisively outscored; emergency
survival interrupts immediately according to observable danger. Record the
chosen objective, scored alternatives, escape margin and transition reason.
Detect low progress and repeated A↔B tile cycles; invalidate the responsible
plan and retry a bounded alternative without snapping position or resetting
the whole behavior tree every frame.

For bombing, score block access, reachable space after resolution, opponent
escape options, teammate routes, inventory and retreat margin. Evaluate a few
candidate placements with pessimistic reachable-opponent envelopes. Do not
confuse bomb spam, proximity to a target or a hypothetical trap with a successful
attack. Add scenarios where waiting or preserving an exit wins over planting.
Audit remaining default-speed assumptions in utility/opening/safety helpers
against the active actor's speed before claiming speed-aware tactics throughout.

### 3. Implement real difficulty and personality: #93, #94

The source audit initially found `reaction_time_ms` written without an active
consumer. The accompanying strategic-wait action now consumes it in the
production tree. It deliberately preserves an immediate public-hazard reflex;
this distinction must remain visible in profile documentation and tests. The
separate legacy controller's throttling is not evidence about room bots.

Introduce versioned difficulty data for observation/reaction delay, bounded
planning effort, opponent-model detail and seeded choice noise. Keep physics
and legal input processing at the normal tick rate. New information must not
affect intentional actions before the configured delay; safety checks must use
the selected policy's permitted knowledge. Define explicitly whether any reflex
channel has a separate, equally disclosed delay. Test earliest action tick at
each profile and across render rates. Never adjust speed, fuse, collision or
hidden drops to compensate for easier or harder decisions.

Keep personality orthogonal: risk appetite, item preference, positioning and
team role can differ at the same skill level. Version effective policy behavior
and configuration in match metadata; RNG lineage alone does not identify the
algorithm. Retain the prior build for comparison and rollback.

### 4. Complete modes and lifecycle: #31, #154, #95, #96, #265

Expose typed public objectives, team relations and hazard capabilities through
the existing mode/pack API. Companions need follow/defend/assist orders, route
yielding and objective cooperation; authored enemies need declared perception,
attack telegraphs and phase rules. They share navigation, not an opponent's
objective function. Test two independently authored fixtures rather than
branching on a sample pack ID. Unknown effects require a visible compatibility
reason and neutral/refused bot behavior.

Add human replacement at the next-round boundary without stealing retained
human reservations. Test join during countdown, death, disconnect, reconnect,
full rooms, rollback and repeated rounds independently. Disconnect takeover
needs an explicit identity/control-transfer contract. Carry bot type, policy,
difficulty and version into durable results; keep human ranked results free of
mixed-bot matches unless a separately named ruleset allows them.

Native and browser clients must observe the same authoritative decisions.
Run real WebSocket/browser/native mixed matches, late joins and round transitions;
a native room probe does not establish browser support. Measure transport
latency separately from bot reaction delay and disclose the policy selected.

### 5. Add evaluation, explanations and load budgets: #32, #98, #99

Extend the current supervisor and elimination stream. Each tournament run needs
build and engine hashes, effective policy/configuration, map/ruleset/content
digests, master seed, participant streams, roster/seat order, tick inputs,
outcomes, command refusals, decision durations and retained event/replay identity.
Detect truncated events and fail incomplete matches rather than counting them
as draws. A diagnostic overlay should show current intent, planned path, time
windows, rejected actions and budget exhaustion without leaking hidden state.

Compute avoidable self-KOs only with a reproducible pre-action state and a
specified feasible counterfactual under the same observable information and
reaction model. The existing `self_ko` flag establishes ownership only. Keep
unknown/unavoidable classifications explicit; stop using proximity as cause.

## Proposed promotion gates

These numbers are initial engineering proposals, **not measured achievements,
industry standards or approved final host budgets**. Establish the reference
host and current baseline first, then commit reviewed limits before tuning.
Do not loosen a limit after looking at a candidate's failing results.

| Gate | Proposed acceptance and evidence |
| --- | --- |
| Deterministic safety | Every existing regression passes; zero avoidable own-bomb deaths in authored feasible-escape fixtures; early-chain, active-fire, blocked-route, negative-speed/input and unsupported-effect controls fail safely |
| Motion and objectives | Zero permanent stuck cases in authored reachable-route fixtures; collect each safe reachable fixture item; no A↔B cycle lasting over two seconds without logged hazard/occupancy justification |
| Fairness | Zero hidden-information differential failures; zero illegal accepted commands; paired hidden-drop/private-input changes leave decisions unchanged; identical effective reaction bounds for the declared profile |
| Held-out quality | Begin with at least 200 unseen seed groups per cohort, rotating seats; frozen baseline and several opponents; report score, draw/timeout rate and 95% intervals; require positive paired improvement on the declared primary metric and no material safety/mode subgroup regression |
| Load | On a named 60 Hz target host, initially target all bot/perception work together at p95 ≤2 ms and p99 ≤4 ms per tick for twelve active seats; report full-tick tail cost, memory and budget exhaustion across concurrent matches; lower supported load if the measured host cannot satisfy the reviewed budget |
| Experience | Blind playtests across beginner, regular and expert cohorts; record perceived fairness, readable intent, challenge and repeated exploits; a win-rate gain alone cannot pass this gate |
| Lifecycle and distribution | Real default startup with one human, full mixed room, explicit zero, small map, repeated rounds, next-round replacement and reconnect cases; actual desktop/browser path and two compatible custom-content fixtures |

Partition map families and seeds into development, validation and a locked final
holdout. Rotate spawn seats and team assignments, pair candidate/baseline runs,
and keep per-mode results. Use seed-group bootstrap intervals for paired scores;
Wilson intervals are appropriate for independent binary rates. Do not repeatedly
tune against the final holdout or declare zero failure probability from a finite
clean sample. Safety regressions block promotion even if overall win rate rises.

Cache identical public hazard work by observation revision; avoid repeated full
map scans for every candidate item. Limit expanded states, candidate actions,
rollout horizon and work per bot, with deterministic tie breaks. Use wall time
for profiling and an emergency watchdog, not as an unrecorded source of policy
variation. Under load, preserve bounded legal movement/survival processing and
defer optional tactical work predictably. Measure the cost of this change's
route-per-item search before scaling it to large custom maps.

## Saturn policy and completion boundary

The enhanced Neptune policy must remain an explicit lineage. Recover Saturn
CPU decisions, cadence, perception, RNG and difficulty from pinned original
code and repeatable original-game experiments under #430 and the existing
Saturn research pipeline. Require the applicable exact state/event, native-pixel
and sample-timed comparisons in [SATURN_FIDELITY.md](SATURN_FIDELITY.md).
Stronger tactics or similar-looking movement are not Saturn parity evidence.

The code accompanying this report addresses default bot availability,
safe-interval routing and specific collection, positioning, reaction and
intelligence defects. Complete moving/special-hazard prediction, tuned difficulty,
team/objective roles,
human replacement, held-out promotion and load/experience gates above remain
separate work until their stated evidence exists.
