# Common player command runtime evidence

Issue #450, SIM-004/#91 and parent #30; base main `5b01779`. Actual command contract
and remaining work: [PLAYER_COMMANDS.md](../PLAYER_COMMANDS.md). Engine/addons remain
hash-pinned to Godot `4.5.stable.official.876b29033` and existing toolchain manifest.

## Reproductions

- Original eight-case suite: one valid movement control and seven assertion
  failures without engine/script errors (`actions-original.log`). Unchecked
  movement, malformed packet side effects, dead/inactive pickup/throw and continued
  movement after the active phase are actual production-path failures.
- Original native kick branch:0pass/1fail with the genuine four-argument call to
  two-argument `ServerPlayer.set_input` (`actions-original-kick.log`). This is
  expected failing diagnostic evidence, not a candidate pass.
- Candidate helper impersonation regression:22pass/1fail without engine errors
  (`actions-helper-identity-before.log`), fixed by checking helper object identity
  against the actual authority roster before submitting its peer ID.

The remote-drain fixture initially left the bomb's physics disabled; that failed
run is retained (`actions-expanded.log`). Corrected fixture runs actual expansion
callbacks and also verifies later owned and foreign remote bombs remain intact.
Contact-kick diagnostics are retained separately: fixtures now clear the real
owner-overlap exception by moving away before returning to contact. No collision
rule or assertion was bypassed to pass those fixtures.

A pre-rapid-tap full run passed127/21, retained as `actions-pre-fast-tap-full.log`.
Final input audit then reproduced a real fast tap that was incorrectly rejected
(`actions-fast-tap-before.log`:23pass/1fail, no engine errors). The actual Input
singleton produces both documented edges; processing press then release fixes it
without accepting malformed values. Earlier paired-edge rejection was a design
mistake, corrected before merge. The final full suite must rerun after this change.

## Verified candidate at this revision

- 24/24 player-command cases plus3/3 native kick cases at FPS caps30/60/144, without
logged engine/script errors or warnings. Operator `actions-final-<suite>-<cap>.log`.
Actual human dispatch/native helper trace matches for movement, placement, pickup
and throw. The tests check world/bomb state, ownership, real trajectories, cooldown,
phase, malformed packet atomicity, buffer copy/injection and inventory/contact
requirements, not printed pass strings or mocks of gameplay primitives.
- Existing RNG11, refuge9 and clock/publication13 all pass without errors/warnings
  (`actions-verified-<suite>.log`). Those fixtures now establish the newly required
  active phase before nonneutral movement, retaining their original assertions.
- Actual default/explicit headless and graphical ClientMain/ServerMain probes pass,
  including single-server ownership and bind/config failures (`actions-runtime/`).
- Actual project import, suite null/true and native-addon probes pass. Input18,
  catalogue14 and merge-contract16 checks pass; these are tooling/metadata checks,
  not emulator, parity, complete game or live-factory certification.

```sh
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_player_commands --max-fps 30 --timeout 50
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_native_kick_command --max-fps 30 --timeout 30
# Repeat both with caps60 and144.
python3 tools/godot/check_runtime.py --godot <pinned-binary> --graphical --evidence <output-dir>
bash run_bot_tests.sh --godot <pinned-binary> --timeout 240 --max-log-mib 16 --log <full-engine-log>
```

The full native suite is running at this evidence revision. Final exact head/base,
required applicable CI, complete results and automatic merge must be attached to
#450/its PR before acceptance. A green focused suite alone is insufficient. The
required gate discovers both new suites; the native workflow additionally runs
both at all three cadences and includes the command-module path for future changes.

No new network ACK/sequence protocol, authenticated online match, public observation
boundary, browser support, full replay/factory recovery or reference fidelity is
claimed. Public/mod tile-query work under #90 remains distinct from the existing
live tile/physics contracts exercised here. Previous #50 lifetime diagnostics are
not declared resolved by warning-free runs. Research/provider/backup inputs remain
#48; no paid provider job started, incremental provider spend$0, account-wide unknown.
