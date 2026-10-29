# Public fuse bounds and hypothetical chains

Issue #61 is a bounded child of #30, based on PR #60 (`48e2857`). These are
actual Godot/ServerBomb/native LimboAI tests of Neptune, not original-game
measurements. Godot is `4.5.stable.official.876b29033`; native addon identities
remain pinned in `tools/godot/toolchain.json`.

## Implementation

AIManager and HazardPredictor now share a forecast using public fuse lower bounds
minus observed elapsed time. The queue is reordered when a chain shortens a bomb.
A hypothetical placement rebuilds the connected forecast from current observations,
including incoming/outgoing chains, without changing simulation state or caches.
Normal hard walls stop before the wall; soft blocks are included and stop the ray.

Both actual placement paths retain the existing fuse sampler and store a separate
public bound. Normal/hasty bounds are exact (3/1 seconds); leisurely is conservatively
5 seconds while actual placement still samples 5–6 seconds. The pure planning query
does not consume gameplay RNG or reveal that private sample. Full bomb state exposes
`fuse_lower_bound`; compact state adds `f` in centiseconds. The client decoder accepts
the new field with the historical three-second fallback.

Active BT planting, attack and farming checks pass the actor's bound and effective
range. Safety buffers, travel speed assumptions and existing survival assertions
are unchanged. Legacy inactive utility code still uses the normal default.

## Before and after

The initial valid native fixture had eight cases: seven failed and one passed on
the original implementation, with no parse/runtime errors. It reproduced a 3000 ms
forecast for an actual short-fuse explosion at physics tick 15 (250 ms at 60 Hz),
a missed incoming hypothetical chain (13000 vs 10250 ms), insertion-order errors,
incorrect long-fuse wall cases, and native short-fuse planting approval (SUCCESS
instead of FAILURE). `forecast-before.log` is an earlier invalid-enum diagnostic;
only `forecast-before-valid.log` is the baseline regression evidence.

The final fixture has eleven cases. All eleven pass at configured idle FPS caps
30, 60 and 144, without engine errors or ObjectDB warnings. These are frame caps,
not performance benchmarks. Tests include fresh observations, state/cache immutability,
both hypothetical directions, multi-hop reordering, walls, native planting with
a successful normal control, and seeded RNG/private-sample isolation.

The actual advancing source/chain experiment predicts both deadlines at 250 ms;
the real explosion signals occur at physics ticks 15 and 18 at each cap. The model
deliberately uses an immediate conservative chain deadline. The test rejects late
predictions and allows at most two ticks for fuse quantisation, and
`3 * ceil(EXPLOSION_GROWTH_INTERVAL * physics_rate) + 2` ticks for this two-cell
chain's progressive travel (eight ticks at 60 Hz). This bound is specific to the
fixture. Real bombs must also finish delayed removal within two seconds. The
earlier cleanup warning was a pending SceneTreeTimer abandoned by fixture teardown;
letting both real explosions finish removes it without suppressing diagnostics.

```sh
python3 tools/godot/check_runner.py --godot <pinned-binary>
python3 tools/godot/check_project_contracts.py --godot <pinned-binary> --evidence <dir>
python3 tools/godot/check_runtime.py --godot <pinned-binary> --graphical --evidence <dir>
for cadence in 30 60 144; do
  bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bomb_forecast --max-fps "$cadence" --timeout 30
done
```

The runner's 25 infrastructure checks pass. Actual null/true suite and native addon
probes pass. Bounded default/explicit headless and graphical native client/server
ping-pong, invalid configuration and bind-failure checks pass. Existing own-bomb
escape, chain survival and corner survival each pass a bounded sample. These are
not browser cross-play, complete matches, tournament quality or determinism proof.
The workflow runs all eleven forecast checks at all three caps.

Host evidence is retained under `/home/dev/neptune-evidence/`: baseline
`forecast-before-valid.log`, final `forecast-final-{30,60,144}.log`, infrastructure
`forecast-final-runner.summary`, native probes `forecast-prerequisites/`, network
`forecast-native-runtime/`, and scenario `forecast-{escape,chain,corner}.log`.
`forecast-lifetime-verbose.log` preserves the timer diagnostic and
`forecast-lifetime-drained.log` the corrected lifecycle run.

## Limits and dependencies

This forecast is for stationary normal bombs against current map geometry. Moving,
carried, thrown, remote and special bombs, future destruction opening rays, pending
progressive arms, full flame intervals, simulation clocks, blocked routes,
oscillation, observation fairness and load remain work under #30. It is not a
complete safety guarantee. The full legacy suite's earlier distance failure and
lifetime warning remain separate; they were not weakened or declared fixed here.

Current main/foundation was fetched during the task: #39 merged at `44c5c10` and
#59 merged into #51 at `46fa817`. The new MERGE_POLICY.md supersedes mandatory
review with applicable exact-head/current-base tests. #62 configures that gate
after this bounded task, including investigating #51's failed runtime CI; this
report does not assert that auto-merge is configured or any runtime PR merged.

Next are #62 and remaining #30 diagnostics, then #31/#32, public packs/profiles
#35/#43, an original #52/#53 slice and #54–#57 in dependency order. No extracted
Saturn assets or live continuous factory are claimed. Selected private media/release,
Neptune provider/spend policy and off-host backups remain external blockers #48.
New paid-provider calls initiated: zero; account-wide spend is unknown.
