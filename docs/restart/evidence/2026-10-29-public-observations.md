# Public observation integration evidence

Issue #452, parent #92/#90/#30. Base main `2553be6` includes independently merged
factory-intake #453 and trace-contract #454; neither proves a live scheduler or
original-game extraction. See [PUBLIC_OBSERVATIONS.md](../PUBLIC_OBSERVATIONS.md).
Godot remains pinned to 4.5.stable.official.876b29033 and the native addon manifest.

## Reproductions and corrections

`observations-original-confirmed.log`: corrected original-source native run had
three assertion failures and one supported native-agent control pass, with no
engine errors. It detected authority game/actor references, absent snapshot API
and direct position snapping. Earlier invalid probes assigned an unsupported
native `agent` property or forgot the fixture blackboard; those are diagnostics,
not valid gameplay regressions. Actual LimboAI uses `agent_node: NodePath`.

The candidate's twelve-case native suite exercises observed agents/blackboards,
equal human/bot data visibility, nested export isolation, unknown-viewer rejection,
covered/exposed item selection, input-buffer/private-fuse/future-hurry perturbation,
seeded ambush choices, no RNG consumption by capture, stale original-actor binding,
typed bomb overlap/airborne occupancy, ordinary physics before throwing, unsupported
terrain rejection and actual twelve-controller updates. The ambush comparison is
a real native policy task, not proof that every possible tree path is equivalent.

`observations-privacy-first.log` retained two fixture errors: its helper had no
registered fixture game and returned null bombs. Adding the fixture group fixed
those errors; `observations-privacy-second.log`, `observations-cached-queries.log`
and `observations-shared-capture.log` each passed12/12 without engine errors.
The native item condition also required iterating dictionary values, not IDs.

Existing tick/clock fixtures now record their callback metadata on the observed
native agent. Paused-zero/one-per-physics and clock/deadline assertions are unchanged.
The movement test preserves the original centering tolerance and asserts that the
authority position is not snapped even inside that tolerance.

## Performance and incomplete runs

`observations-first-full.log` hit the unchanged240-second supervisor timeout.
`observations-optimized-full.log` was deliberately stopped after progress still
showed excess query overhead. Neither is a passing suite. Cached property lists,
versioned terrain/dimension queries and one manager-owned capture removed repeated
work; explicit fixture/perception refresh still observes changed public state.
No test selection, assertion, reference tolerance or individual scenario duration
was weakened. `observations-cached-full.log` exposed stale raw/observed fixture
interfaces in two RNG checks; they retain the original sequence assertions and
now use refreshed observed agents (11/11 in isolation).

`observations-vector-full.log` reached the final clock suite at the240-second
aggregate limit. It reproduced a stale time read when controlled experiments
advanced authority time outside normal manager ticks. The public time getter now
refreshes at that boundary; the unchanged thirteen-case clock suite passes.
The full suite grew from128 to140 cases, including twelve-actor native probes.
Its aggregate supervisor budget is explicitly increased from240 to300 seconds,
with330 seconds for the containing merge-gate subprocess. It remains bounded;
all missing, skipped, failed and timed-out required checks still block merging.
The next full run is measured, and the existing long scenario durations remain.

On this Debian13 x86_64/4vCPU host, the last twelve-actor frozen-physics probe had
20 native decision batches: p50=13125us, p95=17964us, max=41347us; capture p95=874us.
These are noisy local measurements including initial tree planning and logging,
not twelve-seat room-capacity, real-time or held-out evaluation acceptance. Keep
capturing comparable measurements before selecting budgets under #32.

## Commands

```sh
python3 tools/godot/check_project_contracts.py --godot <pinned-binary> --evidence <directory>
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_public_observations --max-fps 60 --timeout 55 --log <engine-log>
bash run_bot_tests.sh --godot <pinned-binary> --timeout 300 --max-log-mib 16 --log <full-engine-log>
```

The latest full suite is pending at this evidence revision. Final acceptance must
include its result, native startup/ping-pong probes and exact-head/current-base CI;
record final identifiers in the issue/PR evidence rather than self-report success.

No public packets, browser transport, downloaded script sandbox, advanced hazard
coverage, observer-specific profile quality, room-fill quality, Saturn parity or
continuous factory/restart milestone is certified by this slice. Incremental paid
provider jobs$0; account-wide spend unknown. Original worktrees/logs are preserved.
