# Native bot tick ownership (#58, child of #30)

Branch `restart/bot-physics-ticks`, worktree `/home/dev/neptune-bots`, based on
PR #59 at `8bad2a33e42653756a7bedcc6c6f75071d37302c`. The updated community/factory
contract was read from foundation `0c5d0ab`. All earlier evidence is preserved.

## Reproduced defect and change

The production manager set BTPlayer.update_mode to zero, labelled it manual, and
also called update from its physics loop. Native introspection and the pinned
[LimboAI 1.5.2 source](https://github.com/limbonaut/limboai/blob/v1.5.2/bt/bt_player.cpp)
identify zero as IDLE and two as MANUAL. That made tree updates depend on both
physics and idle/render callbacks, including updates while the manager was paused.

The manager now obtains the native MANUAL constant through ClassDB. It remains
the sole physics-tick owner. No fuse, movement, aggression or safety threshold was
changed. A small fixture factory hook allows an observation-only manager subclass
to count callbacks while always invoking production super behaviour.

## Native counting regression

The test spawns a real controller through the real manager, installs a counting
BTAction, pauses only the manager and then observes twenty active physics calls.
It checks actual native task executions rather than a mocked enum or a copied loop.
Both phases are recorded before assertion evaluation so zero/extra executions
cannot masquerade as success. Before measurements used the original mode zero;
the candidate code was restored afterward and verified at all cadences.

| Configured idle FPS cap | Before: paused ticks | Before: ticks for 20 manager calls | After: paused ticks | After: ticks for 20 calls |
| --- | --- | --- | --- | --- |
| 30 | 3 | 30 | 0 | 20 |
| 60 | 6 | 40 | 0 | 20 |
| 144 | 13 | 68 | 0 | 20 |

Each original-mode run exits 1 with an explicit assertion failure and no parser/
runtime error. Each candidate run exits 0 with one passing assertion. These are
configured frame caps, not a netplay or renderer performance benchmark. The native
engine/addon identities remain those in tools/godot/toolchain.json.

```sh
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bot_physics_ticks --max-fps 30
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bot_physics_ticks --max-fps 60
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bot_physics_ticks --max-fps 144
```

The supervisor accepts bounded cadence values 1..240; invalid zero fails. Its
25 infrastructure checks pass, as do the actual project null/true/native-addon
probes. Real own-bomb escape, chain survival and corner survival each pass one
bounded post-change run with their existing gameplay assertions intact. The three
counting runs do not emit the earlier ObjectDB leak warning.

Raw before/after artifacts: `/home/dev/neptune-evidence/bot-ticks-measured-*`;
scenario logs: `bot-ticks-escape-after.log`, `bot-ticks-chain-after.log`,
`bot-ticks-corner-after.log`; infrastructure: `bot-tick-runner-checks.log`;
actual suite/addon probes: `bot-tick-final-project-contracts/`.

## Limits and next dependencies

This is a concrete update-ownership fix, not a promotion of complete bot quality.
#30 still requires short-fuse/hypothetical-chain, active-flame, blocked-route,
oscillation, observation/fairness and simulation-time evidence. Root native agent
binding and the full-suite ObjectDB warning also remain audit leads. Full policy
determinism, held-out quality and ten/twelve-seat load are unverified; #31 room
filling and #32 evaluations follow their dependencies. Public packs/profiles
#35/#43 and original #52/#53 fixtures remain in the accepted goal and do not wait
for full extraction. #54-#57 retain their dependency order.

PR #59 CI passed at its exact head; its full run remains red (ten passed, one
escape-distance failure, plus an ObjectDB warning). The earlier multi-bot result
varied despite seeded setup, reinforcing the need for further timing/evaluation
work. Neither that result nor this counting probe establishes Saturn/Power parity.

No PR was merged without independent review. The external #48 media/release,
provider/spend policy and off-host backup prerequisites remain. No live Neptune
factory or recovery result is claimed. Additional paid-provider calls initiated:
zero; account-wide spend unknown. The full thread goal remains active.
