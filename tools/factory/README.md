# Factory intake and durable ownership

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
