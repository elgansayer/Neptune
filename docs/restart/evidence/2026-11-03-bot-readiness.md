# Enhanced bot readiness, 3 November 2026

Scope: the current authoritative Godot battle game, under #30/#31/#32. The owner
explicitly requested strong working bots and authorised replacement where useful.
The change extends the current public-observation, native LimboAI, command and
room-reservation paths. It does not claim recovered Saturn CPU behaviour.

## Implemented

- Default hosted casual rooms fill to four total participants, bounded by actual
  map/preset capacity. Explicit zero remains human-only. Initial-countdown
  provisioning preserves humans and reservations and retains transactional rollback.
- Safe-interval A* accounts for real route length, off-centre departure, actual
  speed, full edge occupancy, inclusive flames and explicit safe waits. Budgets
  fail conservatively. Movement still uses the ordinary authoritative physics.
- Public fuse bounds, progressive patterns, shortened chains, possibly cleared
  soft blockers, kick envelopes and observed flight/landing geometry feed shared
  hazards. Hidden random fuse samples remain private. Nearby unresolved carried
  trajectories prevent intentional planting instead of silently implying safety.
- Reachable firing positions replace greedy chase flanks; bounded cached farming,
  real item selection, corrected opponent history and stable tactical priorities
  retain useful existing behaviours. Final planting requires a verified refuge,
  respects occupied routes and returns finite transit safety margins. Stale tactic
  names and distant Manhattan proximity no longer justify unrelated bombs.
- Strategic reaction timing is active while the hazard reflex and motor remain
  at physics cadence. Actual kicks require observed contact. Remote bombs trigger
  through the normal validated command after reaching a refuge and reacting.
- Shared current forecasts, bounded exact-revision query caches, immutable public
  snapshot payloads and lazy isolated view records reduce repeated work. Public
  exports remain detached and mutable. Diagnostic motor/path/farming output is opt-in.
- Policy metadata is versioned as `neptune-heuristic-v2`. Original rule, inventory,
  movement, damage and fuse values are not changed to strengthen bots.

## Reproducible evidence and honest limits

Official upstream Godot was checked on 3 November: latest stable is
[4.7.2](https://github.com/godotengine/godot/releases/tag/4.7.2-stable), matching the
repository lock. This workspace instead supplies 4.6.3. The installed SQLite
extension requires 4.7 or later, and the strict supervisors correctly reject its
startup. No extension compatibility requirement or test gate was bypassed.
Local assertion execution is diagnostic evidence, not a passing native build.
The pushed PR's exact-head/current-base required CI must provide the pinned
engine validation; retain its logs and result separately.

Short live matches use the production clock, collision, actors, commands and
bombs on unchanged four- and twelve-seat JSON maps, without inventory boosts.
Every bot moved and actual bombs were created. The last local publication-profile
excerpts recorded four/eighteen bombs respectively, no command refusals and no
eliminations. Their source identity and full causal event records are retained
under `/tmp/neptune-live-evaluation-publication-final/` in this workspace; these
are failed supervisor artifacts because of the engine mismatch. Earlier twelve-
bot excerpts did include a causal self-KO, with avoidability unknown.

The last twelve-bot sample measured manager p95 15.24 ms and p99 34.57 ms on this
shared host. This is not a reliable 60 Hz tail budget or an isolated benchmark
comparison: policy changes and host load affect trajectories. Observation work
was reduced, but tactical decision spikes remain a measured performance gap.
No wall clock is used to change policy decisions.

`tools/godot/evaluate_bots.py` creates new immutable evidence directories, records
source/map/engine/policy identities and command/movement/causal/timing metrics,
and preserves nonzero failures. Its three Python evidence-contract tests pass.
Focused native scenarios execute assertions for room defaults, route schedules,
actual flame waiting, hypothetical and live chains, flight landing, kicks,
remote detonation, occupied escapes, item collection, observation mutation,
reaction timing, RNG lineage, bounded farming and query invalidation. The full
native suite, actual server/client admission matrix and export probes remain
required in CI. Do not equate a per-scenario assertion count with a clean native run.

The [research report](../BOT_QUALITY_RESEARCH.md) records primary papers and
inspected implementation revisions, implementation choices and proposed quality
promotion gates. Full held-out tournaments, reliable target-host tail budgets,
long-session human evaluation, team/objective/campaign competence, browser mixed
matches and Saturn CPU parity are not certified by these short liveness runs.
“AAA” is a product-quality target; this change must not relabel unexecuted gates
as passed. Related broad issues remain open.

A twelve-bot run also exposed a real egg-hatching query-flush error. Collection
now claims an egg immediately and defers scene/physics registration safely,
without retaining a deleted egg as the mount callback owner. Actual body-entered,
full hatch/mount and disappearing-collector controls execute two assertions.
The final four/twelve-bot excerpts contain no script or physics-query errors.
The native-suite supervisor budget is explicitly bounded at360 seconds after
the expanded suite reached late temporal tests at the old300-second limit;
scenario timings and error/assertion requirements remain unchanged.

## Accepted pinned CI result for the first release

PR690 subsequently passed pinned Godot4.7.2: **555 native tests in62files,
zero failures**, plus all required tooling/native/runtime checks, for head
`bcd488f3c821796a2162b587bf9e07e97b827be0`, then-current base
`f46ad9d2896619bec943969e59c5d973a6c61cd3` and tested merge
`0f0743860e0cdb96145c00bf65a6f40e946ab7a9`. Both required aggregates completed
before GitHub auto-merged at08:43:17UTC as
`e6bc43980e197e1b14db6be3ff12b29c1b9a4438`.
[Exact CI run](https://github.com/elgansayer/Neptune-Bomberman/actions/runs/41604394029).

The pinned four/twelve-bot cohorts all moved and placed4/18bombs with no command
refusals or eliminations in those excerpts. Twelve-bot manager p95/p99 was
8.483/21.672ms; reliable target-host tail performance is still a separate gate.
The automatic e6bc Web release also connected two real Chromium visitors and
observed three default bots placing seven bombs without server errors. Its
previous smoke allowed682missing-animation browser errors; the follow-up
fixes mounted Tirra animation queries and makes recorded browser errors fail.
Only later actual follow-up CI may certify that browser repair. Image publication
and an accepted202deployment webhook do not prove production rollout completion.
