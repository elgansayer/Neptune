# Factory intake and durable ownership

## Existing Repo Factory integration

`verify.py` is the local entrypoint for the existing Elgl Repo Factory's Neptune
verification planner. It imports the same classifier, command builder and result
validator as `tools/merge_gate/run.py`; it does not introduce another scheduler.

```sh
python3 tools/factory/verify.py --changed-path game_instance.gd \
  --toolchain .factory-tools/godot --evidence .godot/factory-verification/run-001
```

Repeat `--changed-path` for every changed file. Empty, malformed and unbounded
selections fail. Metadata, runner and gameplay selections require the same 5/8/10
checks as CI. An offline pinned Godot binary plus matching native addons is
required before any native selection executes; this command never provisions a
missing cache. The existing install helper may provision it on the coordinator
before entering the no-network verifier. Missing, failed, timed-out or incomplete
results fail; source changes during a run and stale evidence directories fail.

The coordinator owns a primary Git clone with `.git` inside that canonical root
and `.factory-tools/godot` below it. Worker worktrees must belong to that clone,
so their Git common directory remains accessible through the sandbox's read-only
canonical mount. The factory links the ignored `.factory-tools` cache into each
worktree, as it already links other dependency caches. Do not point a worker at an
unrelated canonical checkout or a cache symlink outside the restored roots.

The existing factory must run this command inside its hardened verification
namespace: host login homes, coordinator configuration/state, sibling workspaces
and runtime sockets hidden; only the task worktree writable, canonical dependencies
read-only, private temporary storage and loopback networking. The CLI alone is not
a sandbox. Its one structured receipt includes source identity, plan and every
literal successful command result; exit zero without that receipt is rejected by
the factory planner. This local report never impersonates required GitHub CI.

This preparatory integration does not enable the Neptune daemon profile. The
shared factory still rejects live `neptune` configuration until the separate
tests-only lifecycle/merge path is implemented. Elgl/workout reviews and running
services remain unchanged. One actual issue, quota/failure handling, restart
recovery and continuity still require #33 acceptance. Raw research inputs and
other projects' credentials must never be mounted into ordinary game workers.

## Tests-only GitHub handoff

The shared factory's Neptune GitHub adapter is tracked by #77. It reads the
required `Neptune merge gate` as a GitHub Actions app 15368 check-run for the
exact head, rather than accepting a same-name commit status. Missing checks
wait; skipped, neutral, failed, cancelled and timed-out required checks block.
It verifies that current protected main is contained in the candidate head.
Retarget stacked children to main after their parent merges and rerun checks.

The coordinator validates the existing strict branch protection, app identity,
zero required approvals, administrator enforcement and retained-branch settings.
Use native `--auto --merge --match-head-commit` for the tested head. GitHub's
atomic protection handles a head/base change after the coordinator's read.
Already-enabled auto-merge is reconciled without repeatedly re-enqueuing it.
No approving AI or human review is required for Neptune. Preserve other projects'
review policies when reusing their factory.

This boundary is separate from provider execution and daemon activation. A real
merge through the adapter demonstrates publication, not a complete AI job,
restart recovery or continuous operation. #33 still requires those live tests
before enabling unattended continuity.

## Local ownership foundations

Implements the local foundations of #71/#72. No scheduler, provider, remote GitHub
adapter or supervised VPS service is started by these tools. A green suite proves
these contracts; it does not close #33's live issue-to-merge/restart gate.

Run `python3 tools/factory/check.py`. Python 3.11+ and standard-library SQLite are
enough. Tests include two separate processes racing for a claim, a process killed
inside a database transaction, restart recovery, stale-worker mutation rejection,
and an ambiguous publication that must remain blocked.

## Trusted intake boundary

`readiness.py` consumes a coordinator-produced snapshot. It never executes issue
text, model output or shell commands. The coordinator must obtain fresh issue/PR
state, authenticate dependency evidence and resolve the catalogue's feature IDs.
Schema validation cannot establish that a self-reported proof is true, that a
declared small scope is semantically small, or that a worker stayed within scope.
The later integration must compare changed files and actual tests to this contract.

Snapshot fields (all required):

| Field | Contract |
| --- | --- |
| `schema` | `neptune.factory-intake.v1` |
| `captured_at` | UTC Unix seconds; rejected after 900 seconds or if in the future |
| `base_sha` | Exact 40-character Git commit identity |
| `task` | The bounded task below |
| `available_capabilities` | Explicit list established by host preflight |
| `prerequisite_evidence` | Per-feature verified result with head/base, SHA-256 report and evidence reference; issue closure alone fails |
| `active_work` | Explicit PR/lease inventory with repository, issue, feature and literal scope paths |

Task fields: `repository`, positive `issue`, stable `feature_id`, `revision`
(SHA-256 of the trusted source issue/intake revision), `kind` (implementation,
research, verification or operations), `state=open`, nonempty `acceptance` and
`evidence` lists, `prerequisites` and `capabilities` lists, and `scope` containing
one observable `goal`, literal relative `paths` and `max_files` between 1 and 20.
An epic is rejected. Directory overlap is component-aware. Expired external claims
remain conflicts until the coordinator establishes what happened to their worker.

```sh
python3 tools/factory/cli.py readiness /private/intake.json
python3 tools/factory/cli.py enqueue --database /private/jobs.sqlite /private/intake.json
python3 tools/factory/cli.py show --database /private/jobs.sqlite example/game:FACTORY-001
python3 tools/factory/cli.py recover --database /private/jobs.sqlite
```

These commands do not contact GitHub. Missing parent directories and malformed,
stale or incomplete snapshots fail. Refreshing unchanged intake does not revive a
cancelled/submitted job. Changed issue revisions need deliberate reconciliation;
they cannot silently replace an active contract. The snapshot refresh must itself
reflect fresh external claims, dependencies and capabilities.

## Coordinator API

`JobStore(database_path)` exposes `enqueue`, `claim`, `heartbeat`, `checkpoint`,
`begin_publication`, `release`, `cancel`, `recover`, `reconcile` and `get`.
Close connections explicitly. Use an existing private coordinator-owned directory
on local disk; SQLite on a shared network filesystem is not supported here.

Each successful claim returns an owner, opaque token, increasing fencing epoch,
task digest, expiry, exact base and saved checkpoint. Every worker mutation checks
the live receipt in an immediate SQLite transaction. The database and audit events
survive coordinator restart. Failed transactions roll back. Backwards clock steps
fail closed instead of extending ownership invisibly. Deploy with a reliable host
clock; do not supply a worker-controlled clock or database path.

Checkpoint payloads require exact base/head and the next step, with a 64KiB cap.
Store large logs separately and retain their evidence references. Expired ordinary
claims can be reclaimed with a new epoch; stale receipts cannot mutate state.
Jobs in the same repository also reserve overlapping declared paths.

Publication is a separate boundary. Record immutable branch/head/base intent
before any remote effect. If a worker dies while publishing, recovery blocks the
job and retains its scope reservation. Cancellation also retains an existing
publication hold. The trusted coordinator checks GitHub and stops any old publisher
before calling `reconcile(..., 'clear', evidence_ref)`; a confirmed existing PR
must be resumed rather than duplicated. A submitted PR is not a merged result.

**Fencing is enforced at this local API boundary.** A future publication adapter
must be the sole holder of remote publish/merge credentials and honour the same
receipt. A token cannot prevent an independently credentialled stale process from
calling GitHub directly. `reconcile(..., 'accepted', ...)` trusts its caller's
external verification; it does not inspect checks/ancestry itself. Keep worker
processes away from the coordinator database and these privileged operations.

## Next integration on the VPS

1. Inspect active jobs and use an isolated Neptune state/workspace directory.
2. #73: build a dependency-aware selector and fresh GitHub intake adapter; reuse
   the existing catalogue validator for cycles. Skip blocked reference jobs while
   original gameplay/tooling work remains ready.
3. #74/#75: isolated workspaces and observed tool/input capability checks.
4. Attach the existing supported VPS Codex worker, or a configured OpenHands
   adapter. Keep one implementation job active initially. Provider policy and
   spending limits belong to configuration; this module invents none.
5. #77: reconcile current head/base/checks and remote publication intents with
   the existing tests-gated merger. Preserve zero required approving reviews.
6. #33: execute one actual job, interrupt/restart, reconcile and complete it;
   automatically select the next job. Only then supervise continuous operation.

Back up the database with SQLite's backup API (or a correctly quiesced snapshot),
not by copying only the main file while WAL writes continue. Test restoration and
reconcile remote state before permitting publication after a restore.
