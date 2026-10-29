# Initial bot-fill evidence — 29 October 2026

Issue #469 under #31; source base `96a445b993c0f16d6553c73ed7faf5716177c474`.
Exact accepted head/current-base CI and merge receipts are recorded on the PR and
issue. [Runtime contract](../ROOM_BOT_FILL.md).

## Implemented and locally validated

Trusted startup target/personality; immutable pre-admission policy; fill at the
initial countdown boundary; reservation-aware counts; structured failed-start
rollback; detached participant/fill metadata; default disabled behavior. Actual
bot observation, command and policy RNG paths are reused. Actor stat defaults
are unchanged: one bomb, range one, zero skates and no glove/kicker.

Pinned runtime: Godot 4.5 stable `876b29033`, LimboAI 1.5.2 and SQLite 4.6 from the
accepted toolchain. Host evidence `/home/dev/neptune-evidence/issue469/`:

```sh
python3 tools/godot/run_bot_tests.py --godot /home/dev/.local/share/neptune/toolchains/godot-4.5/Godot_v4.5-stable_linux.x86_64 \
  --run-specific test_room_bot_fill --log /home/dev/neptune-evidence/issue469/focused-002.log \
  --timeout 60 --max-log-mib 16
python3 tools/godot/check_runtime.py --godot /home/dev/.local/share/neptune/toolchains/godot-4.5/Godot_v4.5-stable_linux.x86_64 \
  --evidence /home/dev/neptune-evidence/issue469/runtime-001 --room-only
```

Eight native tests pass, with no engine/script errors: actual distinct actors,
controllers and matching starting stats; existing mixed roster; retained identity
and same-seat rebind; invalid/immutable configuration; no active/finished refill;
injected partial failure and immediate retry; detached explicit metadata; disabled
fill and capacity protection. Controller identities derive from actual allocation,
not an assumed reset between tests.

Actual ServerMain/native SceneMultiplayer clients pass all five scenarios:

| Room | Human actors | Bot actors | Automatic fill | Additional identity |
| --- | --- | --- | --- | --- |
| Twelve-seat control | 12 | 0 | Disabled | Refused |
| Mixed control | 6 | 6 | Disabled, explicit bot RPCs | Refused |
| Four-seat preset control | 4 | 0 | Disabled | Refused |
| Four-seat automatic | 1 | 3 | Target 4, DEFENSIVE | Refused |
| Twelve-seat automatic | 2 | 10 | Target 12, DEFENSIVE | Refused |

Every admitted human receives its actual initial map and active full snapshot.
Automatic cases require applied fill policy, explicit participant/personality
metadata, consistent policy version/seed and no spawn-bot RPC in server logs.
Refused peers receive neither map nor state. Unsupported map/capacity and invalid
fill targets/personality fail before listening. Commands/exit/time receipts and
each `server.log` equivalent are retained in `runtime-001/`.

## Initial failures retained

`import.log`: an ad hoc sanitized invocation omitted XDG directories and produced
editor cache path errors despite engine exit zero. Its supervisor rejected it.
The existing runtime helper sets dedicated XDG paths; its subsequent import passes.
Generated local files are preserved and excluded from the implementation commit.

`focused-001*`: four of eight newly authored tests initially failed because they
assumed bot IDs reset between tests and incorrectly assumed range two. Actual
allocation is monotonic and native human/bot defaults are range one. Corrected
those new fixtures against actual source/runtime; production stats and existing
assertions were unchanged. The final eight checks retain their behavior/rollback
assertions. This report does not treat the failed run as acceptance.

## Remaining gates and limits

The focused runtime run is not the full game suite. The PR must pass the required
full native runner/addon/server-client/bot checks at its exact head/current base
before ordinary automatic merging. No review or administrator bypass is needed.

No full-round replay, safe next-round human replacement, reconnect expiry, host UI,
difficulty/team selection, persistent participant/ranked results, browser cross-play,
reference CPU fidelity, held-out performance/quality or continuous factory recovery
is claimed. Those parent/product scopes stay open. No provider job launched for
this slice; account-wide cost unknown; paid fallback unchanged/off. Operator
Gemini retains #464; original media, branches/worktrees and prior diagnostics are
preserved.
