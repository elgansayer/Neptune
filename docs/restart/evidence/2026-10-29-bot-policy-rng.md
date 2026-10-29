# Native policy RNG isolation

Bounded issue #445, parent #30 and related #87. Base main `8ef4fdd`.
Implementation/API limits: [BOT_POLICY_RNG.md](../BOT_POLICY_RNG.md).
Godot `4.5.stable.official.876b29033` with unchanged pinned native addons.

Two focused original-source cases produced 0 passes / 2 assertion failures,
without engine/script errors: interleaved unrelated global draws changed the
native ambush action sequence, and the task consumed the global gameplay RNG.
Evidence: operator file `policy-before.log`, retained outside Git.

The candidate expanded suite has 11 passes / 0 failures at FPS caps 30/60/144.
These use actual native LimboAI tasks/controllers and owned ServerPlayer fixtures,
not mocked output or printed PASS recognition. They assert per-participant stream
independence, same-seed/action reproducibility, different seeds, global RNG
preservation including provisioning, nonconstant directional decisions, JSON
continuation, rejected restore atomicity, live-roster reseed refusal, missing-RNG
failure and despawn cleanup. Operator logs: `policy-final-{30,60,144}.log`.

The actual default-headless, explicit-headless and graphical ClientMain connection
probes, single-server ownership, bind failure and invalid-config checks pass.
Diagnostics: operator directory `policy-runtime/`. These are connection/startup
checks, not a complete match, web export or browser cross-play demonstration.

```sh
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bot_policy_rng --max-fps 30 --timeout 35
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bot_policy_rng --max-fps 60 --timeout 35
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bot_policy_rng --max-fps 144 --timeout 35
python3 tools/godot/check_runtime.py --godot <pinned-binary> --graphical --evidence <output-dir>
bash run_bot_tests.sh --godot <pinned-binary> --timeout 240 --max-log-mib 16 --log <full-engine-log>
```

At this evidence revision the full native suite is running. Final full-suite,
exact-head/current-base required gate and merge results must be attached to #445
and its PR before acceptance; the focused checks alone cannot authorise merging.
The required aggregate discovers this new suite and the informational Godot
workflow additionally runs its three cadence caps. No missing/failed/skipped
required work is treated as a pass.

Input tooling 18/18, catalogue tests 14/14 and merge-gate contracts 16/16 pass;
these are tooling/metadata checks, not emulator, reference or factory health.

Still unverified: general RNG partition (#87), hidden-input observation filter,
full replay/save/task-state restoration, competitive quality/cost, browser play,
Saturn/Power fidelity and continuous provider recovery. No paid model job was
started: incremental provider spend $0, account-wide spend unknown. Native
GitHub auto-merge is separate from the unproved OpenHands scheduler.
