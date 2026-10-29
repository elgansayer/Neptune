# Required aggregate

`Neptune merge gate` runs on every pull request (including retargets) and main push,
without workflow/job path filters. Its token is contents-read only; checkout does
not persist credentials. It never merges, changes settings or calls a model.

`run.py` records event base/head and the tested merge commit, checks both merge
parents, and requires the head to include the event's current base. Strict branch
protection is additionally required so a later base change invalidates eligibility.
The GitHub Actions app (15368) must be the configured required status source.

All changes run the 18 input-tool tests, catalogue rejection tests and validation,
and `check.py`'s gate contracts. An explicit infrastructure-only allowlist additionally
requires pinned Godot installation, real runner boundary tests and actual suite/native
addon probes. Unknown paths, game scripts/scenes/assets/configuration, new tests and
runtime probes additionally require headless/graphical native startup/connection
tests and the full discovered bot suite. New files default to this stricter class.
There are no skipped subjobs or optional-success fallbacks. A missing script fails.

The infrastructure allowlist lets the reconciled runner bootstrap before old gameplay
fixtures have been repaired. It does not certify those fixtures or allow gameplay
changes to bypass them. The older path-filtered Godot workflow is informational;
this always-running aggregate covers its missing gameplay paths. Full bot failures
must be fixed without deleting assertions or relaxing tolerances to enable merging.

Commands, exit status, duration, classification and identity are saved in report.json;
logs are uploaded on success or failure. A report missing a required command, carrying
an unexpected identity or marking any command skipped/neutral/failing is rejected.
The workflow has a 15-minute bound and commands have shorter bounds. Diagnostics
contain test output only; private media, model keys and production secrets must never
be passed into this job.

The full bot supervisor writes `native-bots.log`; Godot writes the distinct
`native-bots-engine.log`, bounded at 16 MiB. The initial eight-MiB default was hit
by the legacy forecast's verbose output in #51 run 40855908555. Both the original
failure and artifacts are retained. Separate files prevent two writers corrupting
the same log; the larger finite cap does not change a gameplay assertion or timeout.

```sh
python3 tools/merge_gate/check.py
python3 tools/merge_gate/run.py --event <github-event.json> --kind pull_request \
  --evidence <output-directory> --toolchain <pinned-Godot-directory>
```

`run.py` requires a real matching merge checkout. `check.py` creates temporary real
Git repositories to verify stale head/base/checkout rejection; its report tests reject
missing/empty/skipped/failed checks. These are merge-tool contracts, not game health.
Repository auto-merge settings, strict protection and a real automatic merge must be
verified separately under #62. No scheduler/OpenHands/factory-recovery result follows
from a green gate. Follow `docs/restart/MERGE_POLICY.md`.
