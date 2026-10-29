# Legacy scenario contract migration (#50)

Continues PR #51 (`793a52e`) in `/home/dev/neptune-tests`, branch
`restart/legacy-test-contracts`. Earlier worktrees and raw evidence are preserved.
The updated foundation instructions, including COMMUNITY_CONTENT.md/CODEX_START.md,
were read at `0c5d0ab82839e6f3b493189c285eb9b85e6bb955` in the separate
`/home/dev/neptune-foundation` documentation checkout. Foundation #39 remains open;
the new creator requirements do not wait for full reference extraction.

## Change and scope

The eight legacy scenario files now have explicit Node-suite contracts. Each owns
its GameInstance. Two standalone scripts no longer quit the runner or print PASS
without reporting assertions. The trapped-state tests call the production method
instead of a copied algorithm. Collision verifies real owner/bystander exceptions.

Legacy survival scenarios instantiate real bot controllers through the production
manager. Spawning is awaited, the requested tile/controller is checked, and both
the manager and native controller are paused during setup. Bomb helpers use the
actual bomb dictionary, real scene and production explosion callbacks. Own-bomb
and corner cases place actual bombs; empty/inconclusive runs fail. Death checks
read the actual property. Scenario observation bounds use physics ticks and a
fixed setup RNG seed. Fixture games omit global UI command registration to avoid
cross-suite console state; gameplay/physics remains production code.

These changes preserve the legacy gameplay assertions. They do not establish
deterministic bot policy timing or that every historical assertion is an appropriate
promotion criterion. Multi-bot death attribution was previously inferred from
proximity; output now labels that heuristic. A death in the multi-bot survival
diagnostic is reported as a death, not automatically as a proven self-KO.

## Actual evidence

Engine/addon identities remain pinned in tools/godot/toolchain.json. Commands:

```sh
python3 tools/godot/check_runner.py --godot <pinned-binary>
python3 tools/godot/check_project_contracts.py --godot <pinned-binary>
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bomb_collision_fix
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_trapped_algo
bash run_bot_tests.sh --godot <pinned-binary> --timeout 360 --max-log-mib 16
```

- 24 infrastructure checks pass, including new tests for log overflow and rejection
  of an unbounded output budget. Actual project suite/addon probes pass.
- Collision: one real assertion passes. Trapped states: three assertions pass.
- A real own-bomb escape scenario passes after the helper repairs.
- The complete repaired run executes eight files and eleven assertions/results,
  initially **nine passed, two failed, exit 1**, with no engine/script errors.
  It exposed one death in the multi-bot survival diagnostic and the existing
  open-area escape-distance assertion (distance two rather than greater than two).
  Those failures are retained as bot-audit evidence, not hidden as infrastructure
  success or automatically classified as avoidable self-KOs.
- Native introspection reports BTPlayer update modes IDLE=0, PHYSICS=1, MANUAL=2.
  Production bot_manager sets zero while also manually updating. Controllers moved
  while the manager was paused. The focused follow-up is #58 under #30.

Logs live in `/home/dev/neptune-evidence`: `legacy-complete-suite.log`,
`legacy-runner-boundaries.log`, `legacy-project-contracts/`, standalone-test logs,
and `bt-update-mode.log`. Intermediate failures are preserved. One combined run
hit the default 8 MiB log budget and failed correctly; subsequent long runs use
an explicit 16 MiB budget within the supervisor's 1..32 MiB hard range. Gameplay
durations, assertions and error detection were not relaxed.

The updated foundation's 18 input-tooling tests and 9 catalogue tests also pass;
36 catalogue entries validate as metadata. None of those checks proves feature
implementation, reference observation, extraction or factory operation.

## Remaining work

#30/#58 must resolve update ownership, then investigate shortened fuses/chains,
active flames, blocked routes, oscillation and fair observations with controlled
runtime evidence. #31 room filling and #32 evaluations follow their dependencies.
PRs #49/#51 are open with passing exact-head CI, not independently approved or
merged. This migration likewise needs exact-head CI and independent review.

Reference media/release, explicit provider spending policy and off-host backup
configuration remain unresolved in #48. No live Neptune factory, reference run,
browser match, complete campaign or creator workflow is claimed. New paid-provider
calls initiated: zero; account-wide spend is unknown. The full thread goal remains
active beyond this bounded migration.
