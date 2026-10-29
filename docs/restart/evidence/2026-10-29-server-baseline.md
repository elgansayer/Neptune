# Server baseline evidence, 29 October 2026

Scope: child #40 of #24, based on foundation PR #39 at
`59aef5d2d228a8a2fd597e933ce01b009a48039b`. Existing game revision
`6da6f5f5f187cab272699603a7bc1bc09fe3c885` is preserved in Git and local tag
`restart/pre-restart-game-20261029`. Worktree: `/home/dev/neptune-restart`;
branch: `restart/server-runner-baseline`. No existing PR or service was merged,
restarted or replaced.

## Host and prerequisites

- Debian 13.7, Linux `6.12.105+deb13-cloud-amd64`, x86_64, non-root UID 1000.
- Four logical CPUs; 7,944,060 kB total RAM; about 5.2 GiB available at inspection.
- Root disk about 38 GiB with 13 GiB free; existing data volume about 74 GiB with
  26 GiB available. This is smaller than recommended initial lab sizing. No new
  infrastructure was purchased and these figures are not a capacity benchmark.
- Git, authenticated `gh`, Python 3.13, Docker, Podman, a C compiler and Xvfb are
  installed. Godot was initially absent from PATH; official 4.5 was installed
  without root in `/home/dev/.local/share/neptune/toolchains/godot-4.5`.
- Two existing `repo-factory` system services serve other repositories. Neither
  is evidence of a Neptune factory. They were left unchanged. No unrestricted
  runtime socket or production credential was mounted into a new worker.
- Host agent routing marks OpenHands disabled and emergency-only. No Neptune
  instance, explicit spending cap/paid-fallback policy or backup target was found
  in the inspected configuration. Existing provider credential names are present;
  their billing/quota is unverified and their values were not printed.
- `/srv/neptune`, a Neptune configuration directory, selected release and exact
  disc/BIOS paths were not found. A bounded scan of `/home/dev`, `/srv` and the
  empty secondary mount found no media-name candidates. A broader shared-storage
  scan was stopped after its time budget; this is not proof of universal absence.
- Missing operator prerequisites are tracked in #48. No media was invented or
  uploaded and no real input lock was fabricated.

## Implemented

Reconciled PR #18's recursive/both-name discovery and exact selection with PR
#20's CLI/category and legacy execute support. Added failure accounting, strict
suite results, null rejection, a bounded subprocess supervisor and reproducible
real-Godot checks. The shell entry point is independent of caller working directory
and preserves failure status. Linux engine/addon identities are recorded in
`tools/godot/toolchain.json`; no native binary was replaced in the repository.

## Validated commands and observations

`python3 tools/saturn_lab/check.py`: **18 passing tooling tests**. They use
synthetic bytes and establish neither emulation nor extraction nor factory health.

`python3 tools/godot/check_runner.py --godot <pinned-binary>`: **21 passing
real-runtime infrastructure tests**, including an intentionally failing nested
test, parse/runtime errors, timeout and zero exit without a completed summary.

`python3 tools/godot/check_project_contracts.py --godot <pinned-binary>`:
actual project import succeeds with isolated XDG directories; actual BotTestSuite
null probe fails with one failed test, true probe passes with one passed test,
and both native `BTPlayer` and `SQLite` classes are registered. A first import
without XDG settings emitted cache errors despite exit zero; it is retained as
a failed diagnostic, not the successful import evidence.

`bash run_bot_tests.sh --godot <pinned-binary> --run-specific survival_test`:
**two existing scenarios pass in one real Godot file**. This is a limited execution
result, not coverage of all bot hazards, oscillation, fairness or Saturn fidelity.

`bash run_bot_tests.sh --godot <pinned-binary> --timeout 45`:
**eight files executed; two passed assertions and seven failed results; process
exit 1**. Five nested legacy scenarios report no game instance; the collision
script lacks run_tests/execute; the trapped-animation script extends SceneTree.
No cases were removed to produce a green full suite.

Bounded original server/client launches used `--quit-after 120` and external
20-second timeouts. The server scene initialises twice and the second bind fails
while Godot exits zero. The headless client starts a server and declines client
connection. These are reproduced failures tracked in #47, not cross-play evidence.
`server.log` was absent; combined stdout/stderr was inspected instead.

Local raw logs and checkpoint records live in `/home/dev/neptune-evidence`;
no private disc/capture data is committed. CI supplies independently reproducible
runner/addon output after publication; its job name explicitly excludes parity.

## Still unverified, blocked and next work

No emulator was installed or run. No real-disc asset was extracted. No reference
mechanics or rendered frame comparisons have passed. No OpenHands job, recovery
test, independent exact-head review or continuous Neptune factory has run.
Additional paid-provider calls initiated: **zero**; account-wide spend is unknown.

Next eligible build work: #47 startup roles; then repair existing suite setup and
contracts under #24, followed by the survival/oscillation audit in #30. #25/#48
must resolve media, spend, isolation and backup prerequisites before live research
or paid factory jobs. #40 can enter review after its deterministic checks pass;
#24 and the research milestones must remain open.
