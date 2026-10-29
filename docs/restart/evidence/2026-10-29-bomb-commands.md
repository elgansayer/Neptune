# Shared placement authority evidence

Issue #448; partial #91 (SIM-004), parent #30. Base main `2ff1d57`.
API and limits: [BOMB_COMMANDS.md](../BOMB_COMMANDS.md). Pinned engine
`4.5.stable.official.876b29033` and native addon hashes unchanged.

The original fourteen-case fixture gives **1pass/13assertion failures** without
engine/script errors (`commands-original-native-valid.log`). The valid real bomb
and collision control passes. Illegal direct placements and native false-success
assertions fail. Earlier typing/missing-blackboard fixture diagnostics are retained
separately, not counted as runtime behavioural evidence.

The expanded candidate gives **26pass/0fail at30/60/144 FPS caps** without logged
engine/script errors (`commands-final-{30,60,144}.log`). Before the final cadence
runs, a missing throw-direction predecessor fixture produced26 passing assertions
but logged native errors; the fail-closed supervisor correctly rejected that run.
It remains `commands-cadence-board-diagnostic-30.log`, not passing evidence. The
correct fixture supplies POWER_THROW and the direction that its real preceding
tactical task supplies. No production safety assertion or threshold was relaxed.

The five-step human dispatch/direct bot trace matches at all three caps:

```json
[[true,"placed",1,1],[false,"capacity",0,1],[false,"placement_disabled",0,1],[false,"dead_player",0,1],[false,"match_inactive",0,1]]
```

Entries are acceptance, reason, number of created IDs and actor bomb count. Tests
also verify actual world allocation, ID/capacity/RNG/cache rejection atomicity,
ownership, position, fuse and collision hooks. The human and bot fixtures retain
distinct participant metadata; the human path calls actual authority packet
dispatch. This is not an authenticated remote match or browser test.

Actual default-headless, explicit-headless and graphical ClientMain probes pass,
along with server ownership and bind/config failure checks (`commands-runtime/`).
Input18, catalogue14 and gate16 pass: these are tooling/metadata/merge-contract
checks, not emulator/factory/parity evidence.

```sh
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bomb_commands --max-fps 30 --timeout 40
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bomb_commands --max-fps 60 --timeout 40
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bomb_commands --max-fps 144 --timeout 40
python3 tools/godot/check_runtime.py --godot <pinned-binary> --graphical --evidence <output-dir>
bash run_bot_tests.sh --godot <pinned-binary> --timeout 240 --max-log-mib 16 --log <full-engine-log>
```

The full suite is running at this evidence revision. Final results, accepted
head/base, required run and automatic merge must be attached to #448/its PR before
acceptance. Focused green assertions alone cannot qualify the change. The required
aggregate discovers this suite in the complete native run; the Godot workflow
also exercises all three cadence caps.

Remaining: movement/payload and other ability command validation under #91, public
observations under #92, observer-specific intel, advanced hazard/special mechanics,
room filling/evaluation, client action acknowledgements, complete replays, reference
fidelity and browser play. No new Saturn/Power claim. No provider job started;
incremental provider spend$0, account-wide spend unknown. Missing private media and
provider/backup policy remain #48; native auto-merge is not a continuous factory.
