# Runtime role and startup evidence, 29 October 2026

Scope: #47, a focused #24 dependency, stacked on runner PR #49 at
`e64a2e67fd74fa081b102d60755e2729db9689fc`. Worktree:
`/home/dev/neptune-runtime`; branch: `restart/runtime-roles`. The prior failure
evidence is retained in [the baseline report](2026-10-29-server-baseline.md).

## Implemented

- Runtime role comes from the entry scene or explicit validated user options,
  independently of the headless/graphical rendering driver. Client, server and
  test roles share one configuration parser and port value.
- Only the ServerMain autoload starts a server. The server scene no longer
  instantiates its script a second time; a guard also prevents other instances
  from owning the server socket. Bind failure exits 1; invalid configuration exits 2.
- Headless clients initialise the actual ClientMain and its RPC/ping handlers.
  Test runs explicitly use the test role and do not bind a server socket.
- Client startup exposed a pre-existing console lookup of nonexistent
  `res://_get_game_instance().gd`. Replaced it with an actual GameInstance type
  check, retaining console registration rather than hiding its errors.
- The runner supervisor now reaps its engine process group on termination or
  interruption. An interrupted early tooling run exposed an orphan, which was
  verified as belonging to this task and removed; unrelated processes were left alone.
- Root quick-start commands now point at the actual root server scene.

## Actual validation

Engine and unchanged native addon identities are those pinned in
`tools/godot/toolchain.json` (Godot `4.5.stable.official.876b29033`).

```sh
python3 tools/godot/check_runtime.py --godot <pinned-binary> --graphical
python3 tools/godot/check_runner.py --godot <pinned-binary>
python3 tools/godot/check_project_contracts.py --godot <pinned-binary>
bash run_bot_tests.sh --godot <pinned-binary> --run-specific survival_test --timeout 25
```

Observed:

- Actual project import: exit 0 without engine/script error records.
- One server startup and listener on the chosen test port.
- A second server on that port: actual bind error and non-zero exit.
- Default headless, explicitly selected headless and Xvfb graphical clients each
  complete a ping/pong through the real ClientMain/ServerMain RPC handlers.
  Server logs independently contain the three peer connection events; passing
  requires both client and server evidence, not a client-side connection message.
- Invalid role and port: both exit 2 as required.
- 22 runner infrastructure checks pass, including termination cleanup of a
  real hanging Godot process. The original 21 boundary cases still pass.
- Actual BotTestSuite null probe fails; true probe and native SQLite/BTPlayer
  registration pass. Two existing `survival_test` cases execute successfully in
  test role. These remain limited historical scenario results.

The first client probe quit on connection before the server confirmed the peer;
that run failed. The final probe requires a real RPC round trip. `xvfb-run` also
failed because xauth is absent; the checked tool starts installed Xvfb directly,
with no root or package installation. Graphical output uses Mesa llvmpipe under
the Compatibility renderer. Xvfb's local socket ownership warning is retained;
there are no Godot engine/script errors in successful connection logs.

Raw diagnostic and successful logs remain in `/home/dev/neptune-evidence`, notably
`runtime-roundtrip/`, `runtime-runner-final.log`, `runtime-project-contracts/` and
`runtime-survival.log`. The CI workflow repeats the real startup/round-trip check
and requires its graphical option. It is still explicitly labelled as runner and
addon infrastructure validation, not gameplay parity.

## Limits, blockers and next tasks

These clients do not log in or play a complete match. Browser/WebRTC transport,
bot oscillation/fairness, research media, extraction and Saturn comparisons remain
unverified. Existing full-suite failures need setup/contract work in #50, then
genuine bot regressions can proceed under #30. #24 remains open.

PR #49's exact-head CI passed:
https://github.com/elgansayer/Neptune-Bomberman/actions/runs/40828839981.
Neither implementation has independent exact-head approval or a merge. No
continuous Neptune factory, OpenHands job or restart-recovery test is claimed.
Missing operator media/release, spending policy and backup prerequisites remain
tracked in #48. Additional paid-provider calls initiated: zero; account-wide
spend unknown. Existing factory services were left running unchanged.
