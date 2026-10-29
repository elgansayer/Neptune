# Twelve-seat native capacity evidence

Issue #121/ROOM-001. Base `b0b9f97cd134f8b5014eb85d6ef0c999466a9414`.
Contract and launch options: [ROOM_CAPACITY.md](../ROOM_CAPACITY.md).

Godot `4.5.stable.official.876b29033`, pinned by `tools/godot/toolchain.json`;
native LimboAI/SQLite addons; Debian 13 x86_64, 4 vCPU/~8 GB RAM. Checks use
credential-filtered environments and local servers. No production deployment or
reference media is used for this original geometry acceptance.

## Failures reproduced

The initial native control admitted twelve real human/bot actors. A thirteenth
human on a map with spare declared starts was also admitted: one pass, one fail.
The new protocol/room ceiling rejects it before mutation.

The expanded first run had eleven passes and one failure: a retained reservation
from the preceding test prevented reconfiguration of the next map. Fixture teardown
now calls the canonical reservation reset after removing actors. The geometry
assertion remains intact; no production failure/tolerance was discarded.

The JSON map path also exposed Godot's numeric representation: decoded terrain
numbers are floats. The loader now validates finite integral codes and builds
native integer rows before spawn/simulation validation. The original file bytes
are not modified.

## Commands and observations

With `GODOT` the pinned binary and `EVIDENCE` an absolute directory outside Git:

```sh
python3 tools/godot/check_project_contracts.py --godot "$GODOT" --evidence "$EVIDENCE/project"
bash run_bot_tests.sh --godot "$GODOT" --run-specific test_room_capacity --timeout 55 --max-fps 60 --log "$EVIDENCE/focused.log"
python3 tools/godot/check_runtime.py --godot "$GODOT" --graphical --evidence "$EVIDENCE/runtime"
bash run_bot_tests.sh --godot "$GODOT" --timeout 300 --max-log-mib 16 --log "$EVIDENCE/full.log"
```

Native project/import/null/true/addon contracts pass. Focused capacity cases pass.
The full local suite passed **195 tests across 26 files**, zero engine errors or
warnings. The local run preceded addition of policy identity to room receipts;
final focused/network checks and exact-head full CI cover that addition.

Full network/startup checks pass, including actual countdown activation in three
room configurations: twelve humans, six humans/six bots, four humans with preset
limit four. Every admitted human receives its map and full roster; each room
refuses an additional human without sending it map/state. A four-start map requested
for twelve fails before listening. Prior graphical/headless/protocol, bind and
invalid-role/port negatives remain required. Native policy seeds/versions are
retained in final room receipts rather than inferred from a filename.

Existing input/catalogue/factory/gate checks remain tooling/metadata evidence;
they do not prove emulation or a running continuous factory. The PR's required CI
artifact must record all applicable checks and final source/base identities.

Host logs are under `/home/dev/neptune-evidence/capacity-*`; the final manifest
records their digests and CI identity. Original failures are preserved. No assertion
or aggregate timeout was weakened. Other agents' branches/output are untouched.

Not verified here: browser transport, complete rounds, bot strength/load budgets,
automatic fill/replacement, reconnect expiry, production accounts/stats, reference
fidelity, public packs or continuous factory recovery. The operator's Gemini
research mission #464 is independent; Codex proceeds to #462/#27 after this merge.
