# Native refuge and active-flame regressions

Issue #66 under #30, needed for #62/#51 integration. This is original Neptune
behavior testing on pinned Godot `4.5.stable.official.876b29033` and native LimboAI,
not a Saturn/Power Bomberman measurement. Existing survival assertions are retained.

## Actual failures and changes

The full owned native run before this repair (`pr51-full-current-gate.log`) had
eight files and eleven results: nine passed, two failed. The open-area bot stopped
at Manhattan distance two; the three-bot diagnostic observed one death. Its log
shows the player walking into an existing explosion, not a proved self-KO cause.

Direct native BTTask execution against actual GameInstance, ServerPlayer,
GridSampler and HazardPredictor exposed four related defects:

- Commitment called inherited `Resource.get_path` with navigation arguments.
  That API expects zero arguments. Use tile-based `GridSampler.find_path` with
  the actor excluded from obstacles, without converting tile IDs from pixels.
- A closer tile that would explode could outrank the only permanently safe dead
  end. Keep that refuge as a valid fallback; prefer an available refuge with exits.
- In open space the nearest refuge stopped at a flame corner. An immediately
  adjacent refuge may replace it only when it has strictly fewer threatened
  neighbors and a reachable route with deadline checks. Strict improvement bounds
  repeated retargeting; the tight refuge is retained when no extension exists.
- Movement exempted escape waypoints from all hazard checks, including flames
  already present. Validate estimated arrival at escape waypoints and target
  centering too; stop input and release an unsafe commitment for replanning.
  A future blast with enough time to cross still passes the positive control.

Arrival estimates use current tile geometry, base/skate/virus speed and the existing
0.1-second hazard buffer. They are not a complete simulation of moving/special bombs,
all effect mechanics or collision/timing uncertainty. Existing last-resort behavior,
full observation fairness and simulation-clock work remain #30 responsibilities.

## Regression evidence

The final nine-case fixture run against original production source has one passing
control and eight failures, including genuine native API errors. It has no parser
failure or missing fixture/addon excuse. The same fixture against the candidate
passes all nine without engine errors:

1. Open refuge beyond the nearest two-cell flame corner.
2. Tight sole refuge retained.
3. Existing commitment using a real tile path.
4. Twelve repeated decisions stabilize instead of oscillating in the static fixture.
5. A directly observed live bomb cannot become the extended target.
6. An already-burning waypoint stops escape input and releases commitment.
7. A future blast with time to cross permits movement.
8. A blast before estimated arrival rejects movement.
9. Target-centering cannot bypass an active-flame check.

Original fixture source was restored from Git for the negative run, then the
candidate restored in a `finally` block. Logs retain both results:
`/home/dev/neptune-evidence/refuge-nine-original.log` and `refuge-final-nine.log`.
The initial `refuge-before.log` predates editor import and is only a setup diagnostic;
early fixture-variable diagnostics are not promoted as production regression evidence.

Unchanged strict open-area/corner survival and the existing chain survival checks
pass. The three-bot case fails before the movement guard (`refuge-multi-bot.log`)
and passes after (`refuge-multi-after-flame.log`). These are bounded samples and
static decision stability, not held-out competitive quality or universal determinism.
The complete discovered local suite now passes: nine files, twenty results, no
failed assertions or engine/script errors. It retains the pre-existing ObjectDB
lifetime warning, which remains an explicit follow-up. Exact-head CI is still required.

```sh
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_escape_refuge --timeout 30
bash run_bot_tests.sh --godot <pinned-binary> --run-specific survival_test --timeout 30
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_comprehensive_no_suicide --timeout 90 --max-log-mib 16
bash run_bot_tests.sh --godot <pinned-binary> --timeout 240 --max-log-mib 16 --log <full-log>
```

## Logging and integration

The first combined full run with repaired movement (`pr51-full-refuge-candidate.log`)
hit the finite sixteen-MiB log limit before completion. It is a failed tooling run,
not a passing suite. The old forecast printed every blast ray every physics frame.
Its diagnostics are now opt-in via `debug_forecast_logging`, sampled every 120 physics
frames, without changing forecast calculations. The limit and all assertions remain
intact. The quieter passing complete run is retained as `pr51-full-refuge-quiet.log`
(approximately 4.1 MiB, versus the earlier capped failure).

The required gate is enabled on main with strict current-base checks and zero
required approvals. #64/#49/#67 have demonstrated actual native automatic merges.
#51 startup passes actual GitHub native-runtime after the bounded graphical repair;
no failing full gameplay check is bypassed. #60/#63 follow after #51's exact-head
acceptance; all old branches/worktrees and failed logs are preserved.

No live continuous Neptune factory or reference extraction is claimed. Additional
paid-provider calls: zero; total account spend unknown. External selected release/
private disc and BIOS, Neptune provider/spend policy and off-host backups remain
#48 dependencies. Browser cross-play, full bot quality and creator interfaces remain
unverified follow-up work.
