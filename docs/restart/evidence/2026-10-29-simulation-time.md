# Physics-driven bot and hazard time

Issue #70, a bounded child of #30 before room filling/evaluation #31/#32. Pinned
Godot `4.5.stable.official.876b29033` and repository-native addons are unchanged.
These are Neptune runtime measurements, not Saturn/Power Bomberman observations.

## Implementation and timebase

GameInstance accumulates physics delta and a session tick counter. Bot temporal
queries, public bomb/flame deadlines, placement grace, tactical locks, stuck
penalties, opponent tracking, virus and immortality expiry share that clock.
Zero is a real hazard deadline; mortal danger is invariant under a shifted clock
origin. Server state supplies simulation milliseconds and tick for the existing
client status countdown. Network latency and client visual clocks remain local.
See `docs/restart/SIMULATION_TIME.md` for the actual API and phase contract.

Physics priorities explicitly advance clock/status (-200), bombs (-150), then
publish hazards and decide bot input (-100) before player movement (0). The native
callback fixture verifies the same tick/clock in the blackboard and verifies live
bomb elapsed time agrees, with an unchanged 1000ms forecast deadline through six
real callbacks. This prevents a one-step forecast shift from updating time before
updating the observed bomb. This Neptune phase order is not measured reference
parity. Durations, fuse sampling, movement speeds and safety thresholds are unchanged.

## Actual regressions and controls

The original nine-case fixture failed all nine assertions on main `a5e154b` with
no engine/parser error (`clock-before.log`). The expanded twelve-case fixture,
run against restored original production source, passes the pause control and
fails eleven cases (`clock-original-twelve.log`). Candidate source is restored
after that negative run. Early import-order diagnostics and a cadence diagnostic
that overlapped the original-source run are retained, not counted as candidate
validation (`clock-after-first.log`, `clock-original-overlap-30.log`).

The candidate passes all twelve at configured FPS caps 30/60/144 without engine
errors. This includes actual native grace/escape tasks, zero-time flames, shifted
danger origins, frozen flame expiry, status boundaries, opponent velocity, real
callback ordering, SceneTree pause and the public clock snapshot.

Two forty-step experiments use actual production game/bomb/manager callbacks,
native grace decisions and observed opponent state: one with no wall delay, one
with a two-millisecond delay between each identical 20ms simulation step. Arrays
of clock/tick, bomb elapsed, flame/status deadlines, native statuses, opponent
observations and forecast entries are equal. All three caps produce trace SHA-256
`8b6c800538b741c52e44b12169b12577a1012980a00b4b03bdf588a43ab0b95a`.
The equality assertions, controls and actual inputs support the result; a hash
alone is not a game/factory/reference health check.

```sh
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_simulation_clock --max-fps 30 --timeout 40
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_simulation_clock --max-fps 60 --timeout 40
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_simulation_clock --max-fps 144 --timeout 40
python3 tools/godot/check_runtime.py --godot <pinned-binary> --graphical --evidence <output-dir>
bash run_bot_tests.sh --godot <pinned-binary> --timeout 240 --max-log-mib 16 --log <full-log>
```

Bounded default/explicit headless and graphical client/server ping-pong, occupied
port and invalid configuration checks pass (`clock-native-runtime/`). The first
complete local suite passes 46 results across 13 files (`clock-full-candidate.log`),
with original escape/chain/refuge/hurry assertions intact and no engine/script
errors. The pre-existing ObjectDB lifetime warning is retained, not suppressed.
This local full run predates integration of concurrent main updates; current-base
CI/revalidation remains authoritative for the eventual candidate.

Raw logs/command summaries are retained under `/home/dev/neptune-evidence/clock-*`.
The existing input18/catalogue9 checks passed again, tooling only. The workflow
adds all twelve clock cases at all three caps; the required aggregate also executes
the entire discovered native suite. Original fixture changes only express their
time inputs in simulation units and supply the already-required authority context;
none of their behavioral assertions is relaxed.

## Limits and next work

This proves bounded clock experiments. It does not prove complete policy RNG or
replay determinism, observation fairness, all special/moving hazard windows, browser
cross-play, accurate reference rules or competitive bot quality. Session restore
must later include clock/tick with the other state. Client wire snapshot construction
is implemented/tested; authenticated room lifecycle and browser status UI remain
their own #31/#34 acceptance beyond these native transport smoke tests.

The last_seen_pos aggression bug, shared observer profiling, RNG isolation and
native lifetime warning remain #30/#50 leads. Follow with #31 room filling and
#32 evaluations, then public packs/profiles #35/#43 and the accepted creator slices.
Private reference release/media, provider/spend policy and off-host backups remain
#48. No continuous Neptune factory/recovery or extraction is claimed. Additional
paid-provider jobs initiated: zero; total account spend unknown.
