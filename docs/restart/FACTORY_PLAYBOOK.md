# Operating the three-track AI factory

This is the implementation contract for #33. The 30 October operator direction is
to reuse the deployed `elgansayer/elgl` Repo Factory and its supported shared
Codex/Claude/Gemini provider broker. Preserve existing services, configured shared
limits/health, manual sessions and each repository's own merge policy. This
supersedes the older blanket prohibition on authorised shared provider reuse;
it does not authorise credential copying or a competing scheduler. A cloud
environment is optional. Inspect current live state before claiming operation.

PR #453 adds [local intake and durable ownership](../../tools/factory/README.md)
with executable concurrency/recovery tests. Remote intake/publication adapters,
provider execution and supervised live-job recovery remain integration work.
#474/#475 subsequently merged Neptune offline verification in that existing
control plane. Live Neptune unattended intake/merge/restart recovery is still a
separate acceptance gate. A Codex session or successful local store test is not
a running Neptune factory. Research queues and receipts are #510/#511; see
[research execution](RESEARCH_EXECUTION.md) and the live index #477.

[MERGE_POLICY.md](MERGE_POLICY.md) supersedes the earlier mandatory review gate:
merge automatically after applicable exact-head/current-base tests succeed.
Optional AI review must not block the queue. GitHub auto-merge can run before #33.

## Workstreams and handoffs

| Track | Reads | Produces | First live proof |
| --- | --- | --- | --- |
| Factory and integration | Trusted issues, current code, provider policy | Branches, builds, tests, recoverable jobs | One real issue through a bounded job and restart recovery |
| Saturn laboratory | Pinned disc/BIOS/core, controlled inputs | Graphics with provenance, behaviour specifications, parity fixtures | Repeatable original capture and one campaign/battle comparison |
| Power Bomberman laboratory | Pinned client/server/manual, local experiments | Versioned feature observations, edge cases, network baselines | Repeatable menu-to-match capture and one measured rule |

These are logical queues, not a requirement to fund three simultaneous machines.
Begin with one implementation job; enable concurrency only within measured host
and model budgets. Native builds, desktop capture and emulator runs must not starve
each other or the production game. Bots, packs and community implementation consume
the two laboratories' contracts and can proceed on independent eligible work.

## Minimum durable job record

Store repository/issue, track, priority, dependency IDs, acceptance revision,
base/head commit, input/evidence manifest digests, lease owner/expiry, attempt,
state, command results, optional review head, provider/model version, consumed budget,
timestamps and diagnostic/PR links. Persist state outside disposable workspaces.
Use transactional claims and expiring leases so two workers cannot own one job.

State path: ready -> leased -> implementing -> validating ->
merge-ready -> merged. A failure enters retryable, blocked or rejected with a
reason and next eligible time. Cancellation and budget exhaustion stop new paid
work while preserving evidence. Process exits are not sufficient to mark success.

GitHub supplies visible scope and discussion; the durable store supplies leases
and recovery. Reconcile GitHub state on restart. A closed issue is not automatically
proof that its dependency's acceptance passed. Never blindly execute community
issue bodies, binaries' strings or workshop metadata as coordinator instructions.

## Intake and scheduling

1. Read trusted scope, current issue dependencies and open PRs; deduplicate by
   feature ID, reference build, scenario and first divergence before creating work.
2. Split a task until one implementation PR has a concrete observable result.
   Record whether an issue is research, implementation, verification or operations.
3. Check inputs, host capability, spend allowance and resource lease. Missing disc
   files block only Saturn-dependent jobs, not bot fixes or feature documentation.
4. Run the task in an isolated worktree/container with bounded command durations,
   CPU/RAM/disk and provider retries. Workers lack merge and production credentials.
5. Attach actual test results, evidence digests and uncovered cases. An AI summary
   never substitutes for captures, assertions or exit codes.
6. Applicable deterministic CI must pass for the exact candidate head; review is optional.
   Merge serially against the current base; rerun affected checks after a rebase.
7. Update catalogue and issues only with their appropriate evidence. Preserve
   counters for documented, observed, implemented and verified; do not flatten them.

## Gates by change type

| Change | Required evidence |
| --- | --- |
| Tooling | Tests that reject malformed inputs and false success |
| Reference observation | Pinned real source, repeatable command, capture identity and limitations |
| Gameplay | Native runtime scenarios, reference comparison where claimed, replay outcome |
| Bots | Survival/fairness regression suite, held-out scenarios, cost and quality results |
| Network | Equivalent conditions, raw latency/correction/outcome samples, client and server load |
| Packs | Cross-client version checks, limits, unsupported mechanics and malformed upload cases |
| Public release | Source/content allowlist, preserved notices, clean build and rollback |

Reference data and tolerance edits need traceable evidence and regression checks. Ordinary
workers cannot weaken the protected merge policy or give themselves privileges.
No human or AI approving review is required. Resolve ordinary implementation
choices autonomously within scope; missing or failing tests still block merging.

## Recovery and continuous operation

Demonstrate coordinator restart, expired lease, killed worker, failed provider,
quota exhaustion, changed base branch and duplicate GitHub delivery. Resume or
cleanly requeue without duplicate merges/charges or declaring a failed job done.
Use bounded retry/backoff and a circuit breaker; a permanently blocked task must
not monopolise the queue. Keep an operator stop switch and structured health status.

Run the scheduler as a supervised service only after the first job succeeds.
Configuration supplies concurrency, command timeouts, daily/monthly spend limits,
provider order and retry budgets. Never invent those spending limits. If no funded
provider is configured, finish available local/read-only work and report that block.

## Evidence dashboard

Expose current job/lease/heartbeat, PR/check/review head, last successful merge,
reference coverage, bot regression/tournament results, benchmark trends, failure
counts, spend and disk retention. Report queued/blocked/paused separately from
running. Retain the previous release and restore-tested job/evidence backups.

Current commands `python3 tools/research_catalog/check.py` and
`python3 tools/research_catalog/cli.py report` check/report catalogue structure.
They neither run jobs nor validate the truth of attached evidence. Protected
runtime tests remain necessary before promotion; AI review is optional.
