# Trustworthy native test execution

These tools pin the existing Godot 4.5 Linux x86_64 baseline and test the runner's
failure boundaries. They do not implement emulation, extraction, cross-play or a
factory. No API model calls are made.

```sh
python3 tools/godot/install.py --directory /tmp/neptune-godot-4.5
python3 tools/godot/check_runner.py --godot /tmp/neptune-godot-4.5/Godot_v4.5-stable_linux.x86_64
python3 tools/godot/check_project_contracts.py --godot /tmp/neptune-godot-4.5/Godot_v4.5-stable_linux.x86_64
python3 tools/godot/check_runtime.py --godot /tmp/neptune-godot-4.5/Godot_v4.5-stable_linux.x86_64 --graphical
bash run_bot_tests.sh --godot /tmp/neptune-godot-4.5/Godot_v4.5-stable_linux.x86_64 --run-specific survival_test
```

The installer verifies the pinned archive, extracted executable and repository
Linux addon hashes. It needs no root, container socket or package manager. Hashes
identify builds; the actual project checks separately instantiate the real suite
and check that SQLite and BTPlayer native classes are registered.

`check_runner.py` creates minimal projects and executes real Godot subprocesses.
It verifies discovery, exact selection, categories, empty/invalid tests, parse and
runtime errors, inconsistent counts, timeouts and early zero exits. These fixtures
test the test infrastructure, not survival, oscillation or Saturn mechanics.

`check_project_contracts.py` imports the actual project, checks its native classes,
and subclasses the actual `BotTestSuite` with no-op setup/teardown. A null-returning
method must fail; an explicitly true-returning method must pass. Temporary probes
are removed afterward. This is a contract probe, not a simulated bot match.

## Test contracts

- Discover `test_*.gd` and `*_test.gd` recursively in sorted order. The existing
  `tests/test_helpers.gd` support library is explicitly excluded. Hidden directories
  are not suites; symlinked test directories fail instead of recursing forever.
- `--run-specific` accepts an exact filename, filename without `.gd`, or full
  `res://tests/...` path. Missing/ambiguous names fail. `--run-category` selects a
  directory relative to `tests`, including nested descendants.
- A Node suite's `run_tests()` reports nonnegative integer `passed`/`failed` and
  a result dictionary with one `PASS` or `FAIL...` entry per reported test. Empty
  suites, missing properties and inconsistent counters fail.
- An `execute()` Node may return a bool. Existing legacy Nodes may instead use
  optional `setup()`/`teardown()` and an explicit `test_result` starting `PASS:`.
  Null without that explicit result, `WARN`, empty results and failures fail.
- `BotTestSuite` test methods require explicit boolean `true`. Null is a failure.
  Returning true is the suite's explicit assertion contract; it does not establish
  that a scenario exercises the intended gameplay. Scenario quality needs review.

Always use `run_bot_tests.sh` or the Python supervisor rather than trusting a raw
Godot exit status. The supervisor invokes the Node runner scene (not an invalid
`--script` entry point), removes provider credentials from the child environment,
bounds wall time/log size, and rejects logged engine/script errors and absent,
duplicate or inconsistent machine summaries. It preserves non-zero outcomes.
Default timeout: 120 seconds; configurable up to 600. Default log:
`test_results.log`; use `--log /private/evidence/run.log` to retain runs separately.
Runtime configuration/cache stays in ignored `.godot/restart-runtime` directories.
The default output budget is 8 MiB. Long stress runs may explicitly select
`--max-log-mib 16`; accepted values remain bounded to 1..32 MiB. Overflow is a
failure and its artifact must be retained. This setting does not change gameplay
assertions, durations or engine error detection.
Termination or interruption of the supervisor reaps its Godot process group;
this failure boundary is checked with a real hanging Godot fixture.

## Native startup roles

The server scene selects `server`, the bot runner selects `test`, and ordinary
client scenes select `client`; rendering/headless mode does not select a role.
User options `--runtime-role=server|client|test` and `--server-port=1024..65535`
override these choices. The test supervisor explicitly selects the test role.
One ServerMain autoload owns the socket; bind/configuration errors exit non-zero.

`check_runtime.py` imports the real project and starts a bounded server on an
available test port. It verifies a second bind fails, tests default/explicit
headless clients, and requires an actual ping/pong through ClientMain/ServerMain.
With `--graphical`, it also starts an isolated Xvfb display and a real graphical
client. Xvfb is required for that option; xauth/root/package installation is not.
It checks both process logs and confirms server-side connection events. These
probes do not log in, play a full match or establish browser transport support.

## Known project failures

The full existing suite currently fails correctly: five legacy scenarios cannot
find their game instance, one `_ready()` script lacks a suite contract, and one
standalone `SceneTree` script is not a Node suite. Migrate these with real scenario
assertions; do not exclude or reinterpret them to obtain green CI.

Startup role/duplicate-binding work is tracked in #47. CI is explicitly named as
infrastructure/addon validation, not full game health or Saturn parity.
