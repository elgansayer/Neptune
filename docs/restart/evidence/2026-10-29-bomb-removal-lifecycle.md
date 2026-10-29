# Bomb removal lifecycle evidence

Issue #456, related legacy contracts #50 and bot work #30. Base main `fd413a7`.
Runtime: hash-pinned Godot4.5.stable.official.876b29033 and existing native addon
manifest. This is an actual engine-lifecycle repair, not reference-parity evidence.

## Reproduction

An isolated real ServerBomb scene completed its expansion, started its existing
half-second removal, and was destroyed before the delay elapsed. Verbose shutdown
reported one leaked `SceneTreeTimer` after the bomb itself was freed. Waiting an
additional0.7 seconds did not release it. Original logs:
`lifecycle-bomb-disposal-original-valid.log` and
`lifecycle-bomb-disposal-expired-control.log` under the private host evidence root.
The removal implementation is unchanged between2553be6 andfd413a7, so this leak
predates the public-observation change; earlier clean runs did not disprove it.

The committed native regression destroys actual isolated GameInstance rooms. After
two warm-ups, eight pre-explosion disposals retain zero extra engine objects, but
eight disposals during bomb removal retain eight objects. Original-source native
result:2pass/1assertion failure, no engine/script errors. Verbose exit identifies
ten SceneTreeTimers: two warm-up leaks plus eight measured leaks. This establishes
an ownership problem without assuming a plugin or observation-record cause.

Temporary ignored probes also ran all17 short suites and405 repeated assertions.
They showed no orphan-node growth and counts plateaued after warm-up. The repeated
probe reused result IDs, so its aggregate summary was correctly rejected by the
supervisor. It is diagnostic inventory only, not a valid passing suite. An earlier
one-bomb probe had a Variant-inference parse error; only its corrected run supplies
reproduction evidence. None of these ignored probes enters required test selection.

## Repair and acceptance

The half-second idle timer is now a one-shot child of the bomb, with explicit
pause-always processing matching the old SceneTreeTimer. Parent destruction owns
its cancellation; no suspended GDScript await retains a detached timer. Repeated
scheduling cannot create multiple removal timers. Blast growth, fuse timing,
public observations and command rules are unchanged.

Three native cases check ordinary room disposal, disposal during removal and the
existing half-second removal while the tree is paused. Candidate3/3 passes at
30/60/144 FPS caps. Both disposal batches retain zero objects after warm-up. The
same immediate-exit one-bomb probe is clean after the fix. Existing timing and
survival assertions are preserved; the complete required suite is not filtered.

Project import and actual null/true/native-addon contracts pass. Saturn-lab28
checks pass independently; these validate tooling, not emulator/game/factory health.
The complete native suite passes143 cases/23files in242.491 seconds with no
engine/script errors or ObjectDB warning. Actual default/explicit headless and
graphical ClientMain startup/ping-pong pass, alongside server ownership, bind
failure and invalid role/port cases. These are not full online-match/browser checks.
Final exact-head/current-base CI and merge identities belong in the PR/#456 evidence.
A clean full run alone does not establish lifetime correctness; the native retained-
object regression is the acceptance gate. Other asynchronous content scripts and
long-running server capacity remain unaudited by this focused repair.

```sh
bash run_bot_tests.sh --godot <pinned-binary> --run-specific test_bomb_lifecycle --max-fps 60 --timeout 45
bash run_bot_tests.sh --godot <pinned-binary> --timeout 300 --max-log-mib 16 --log <engine-log>
python3 tools/godot/check_runtime.py --godot <pinned-binary> --graphical --evidence <directory>
```

No new provider job or infrastructure purchase. Provider-job spend$0; account-wide
spend unknown. Private media/release and live-factory provider policy remain separate
inputs. All original branches, worktrees and diagnostic logs remain preserved.
