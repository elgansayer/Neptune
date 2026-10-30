# Trustworthy native test execution

These tools currently pin Godot 4.7.2 Linux x86_64 and test the runner's
failure boundaries. Development must adopt the latest stable Godot under the
[dependency policy](../../docs/restart/DEPENDENCY_POLICY.md); update these pins,
native addons, export templates and examples together after compatibility checks.
The commands below use the current recorded pin. These tools do not implement emulation, extraction, cross-play or a
factory. No API model calls are made.

```sh
python3 tools/godot/install.py --directory /tmp/neptune-godot-4.7.2
python3 tools/godot/check_runner.py --godot /tmp/neptune-godot-4.7.2/Godot_v4.7.2-stable_linux.x86_64
python3 tools/godot/check_project_contracts.py --godot /tmp/neptune-godot-4.7.2/Godot_v4.7.2-stable_linux.x86_64
python3 tools/godot/check_runtime.py --godot /tmp/neptune-godot-4.7.2/Godot_v4.7.2-stable_linux.x86_64 --graphical
bash run_bot_tests.sh --godot /tmp/neptune-godot-4.7.2/Godot_v4.7.2-stable_linux.x86_64 --run-specific survival_test
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

## Current dependencies and exports

The [release inventory](dependency-releases.json) records the official stable
releases checked on 30 October 2026 and verified archive digests: Godot 4.7.2,
LimboAI 1.8.1, Godot SQLite 4.9 and LimboConsole 0.8.0. The local console alias
copy fix remains applied and covered by `test_console_aliases`. Resource UIDs
remain those of this project. The engine filename is read from `toolchain.json`
by CI, provisioning and offline verification instead of fixing it in each consumer.

Install the matching Linux x86_64 and web export templates in a writable data
directory, then use the root `Linux` and `Web` presets:

```sh
export XDG_DATA_HOME=/tmp/neptune-export-data
export XDG_CONFIG_HOME=/tmp/neptune-export-config
export XDG_CACHE_HOME=/tmp/neptune-export-cache
mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" /tmp/neptune-exports/web
python3 tools/godot/install_templates.py --directory "$XDG_DATA_HOME/godot/export_templates"
/tmp/neptune-godot-4.7.2/Godot_v4.7.2-stable_linux.x86_64 --headless --path . --export-debug Linux /tmp/neptune-exports/neptune.x86_64
/tmp/neptune-godot-4.7.2/Godot_v4.7.2-stable_linux.x86_64 --headless --path . --export-debug Web /tmp/neptune-exports/web/index.html
```

The template installer verifies the pinned official archive and version before
extracting the selected templates. `--archive /path/templates.tpz` reuses an
existing archive with the same integrity checks. Other export platforms need
their matching official templates and platform-specific validation.

Presets include external `.pck` content and enable single-threaded web native
extensions. Run exported Linux binaries directly beside their PCK, without
`--path`: official templates disable path overrides. Serve browser exports over
HTTP with the required isolation headers. Browser rendering/startup is a separate
check from networking: ENet browser transport remains the open cross-play work in
[#34](https://github.com/elgansayer/Neptune-Bomberman/issues/34).

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

`--max-fps 30|60|144` supplies a bounded idle/render cadence for native experiments;
the supervisor accepts 1..240. `test_bot_physics_ticks` installs a counting native
BTAction into a controller spawned by the production manager. An observation-only
manager subclass counts calls and always invokes production `super` behaviour.
The regression requires zero ticks while paused and exactly one native update per
active manager physics callback at every tested cadence. It does not establish
complete policy determinism or tactical quality.

## Historical project failures

The original runner-baseline audit found failures: five legacy scenarios cannot
find their game instance, one `_ready()` script lacks a suite contract, and one
standalone `SceneTree` script is not a Node suite. Migrate these with real scenario
assertions; do not exclude or reinterpret them to obtain green CI.

The current upgrade checks and compatibility findings are recorded in
[the upgrade evidence](../../docs/restart/evidence/2026-10-30-godot-upgrade.json).
Use current CI results for the full-suite status.

Startup role/duplicate-binding work is tracked in #47. CI is explicitly named as
infrastructure/addon validation, not full game health or Saturn parity.
