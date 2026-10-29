# Spawn admission native evidence

Issue #458 under #100/#121/#31; base mained5c088. Pinned Godot4.5 and existing native
addon hashes remain in tools/godot/toolchain.json. No reference media are required
for these original engine fixtures. Interface: [SPAWN_RESERVATIONS.md](../SPAWN_RESERVATIONS.md).

Original four-case native run:1control pass/3assertion failures, no engine/script
errors. Available declared starts were distinct, but exhausted selection wrapped
onto an existing start, a repeated peer replaced a live actor, and admission had
no explicit result. Commands/logs: spawns-original.log in the host evidence root.

The first expanded18-case run passed17 but exposed JSON restore refusing Godot's
integral floating-point JSON numbers. The corrected suite and seed/blocked-exit cases passed23/23; an additional
idempotent-leave regression brings current focused coverage to24 cases. It tests
geometry/exhaustion, duplicate identities, current hitboxes/flames, fractional
cross-cell overlap, malformed/overflowing coordinates, seeded canonical layouts,
gameplay RNG independence, real mixed human/native-controller admission, refusal
without controller/stream allocation, detached/atomic restored state, retained-key
rebinding and actual ServerMain membership refusal. A trusted empty-roster reset
keeps retained-reservation cases isolated between fixtures.

Existing fixtures explicitly declare their available interior starts. Bot helpers
admit at those starts rather than teleporting after an unsafe default allocation.
The collision-owner exception fixture approaches its overlapping position using
validated movement; all original collision/RNG/clock/survival assertions remain.
The clock callback fixture and independent-RNG second actor use separate starting
cells, preserving their timing and stream assertions.

Spawn23 (before the idempotent-leave case), collision1/RNG11/clock13/observation12 pass at30/60/144 FPS caps;
refuge9 passes at60. Actual project import/null/true/native-addon contracts pass.
The first complete166/24 run retained163pass/3fail: an intentional out-of-roster
command fixture left stale reservation bookkeeping, and the real Input fast-tap
control relied on the former admission yield. Canonical leave now clears bindings
idempotently even after trusted roster removal, and the fixture uses that path.
The Input test queues genuine events before physics and samples them in a real
physics callback, matching GameView; both edge/result assertions are unchanged.
An initial sampler free inside signal emission was correctly rejected as an engine
error; it now queues its deletion. These failures remain saved, not passing evidence.

Corrected command26, input24 and spawn24 pass locally at60FPS. Their final30/144
cadences, complete167/24 suite, actual startup and exact-head/current-base CI are
pending at this evidence revision.
No complete network reconnect, migration, room filling, twelve-seat capacity,
browser play, creator workflow, reference parity or continuous-factory health is
claimed. Whole #100/#121/#31/#108 acceptance remains open where not demonstrated.

```sh
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_spawn_reservations --max-fps 60 --timeout 55
bash run_bot_tests.sh --godot <pinned-binary> --timeout 300 --max-log-mib 16 --log <engine-log>
python3 tools/godot/check_runtime.py --godot <pinned-binary> --graphical --evidence <directory>
```

No provider job or infrastructure purchase. Provider-job spend$0; account-wide
unknown. The completed lifecycle worktree is reused on a new isolated branch to
conserve disk; its prior branch/commit, other worktrees, untracked artifacts and
all external diagnostics remain preserved.
