# Resumable VPS code recovery checkpoint, 2 November 2026

The primary objective remains **all original Saturn Bomberman game code**. This
is a continuation record, not programme completion. Unknown module/function/
dynamic-target denominators stay unknown. Original gameplay, timing, Godot parity,
slave SH-2, overlays, bootstrap, regional network/save paths, sound self-modification
and DSP remain active research.

## Accepted and published slices

- #591 / [PR593](https://github.com/elgansayer/Neptune-Bomberman/pull/593): accepted
  merge `e117b1161ffa54866df6c48a9a2bf0dd78ff7a43`, tested publication head
  `1b9ed40` against base `2e7d2bb`, required CI run `41434022376`. Two original
  runs, 1,980 cases per run, entries A3E0/A3FA, six rejected instruction controls.
  [Contract and evidence](../research/2026-11-02-original-position-bounds.md).
- #594 / [PR595](https://github.com/elgansayer/Neptune-Bomberman/pull/595): accepted
  merge `a8cbc796cdef88959eba056977fde8ff125416d2`, tested head
  `5dbed5a85bc32ff3970da0c234f33ade01aa2670` against base `e117b116`, required
  CI run `41434645968`. Two original runs, 1,120 cases per run, entries A25E/A2D8,
  ten rejected instruction controls. [Contract and evidence](../research/2026-11-02-original-split-add.md).
- #596 / [PR598](https://github.com/elgansayer/Neptune-Bomberman/pull/598): accepted
  merge `95e28ffb781a549b30359725937534b600b6599e`, tested head
  `784eb019b1803259e23fb9f88cee9281fa99e0ec`, base `a8cbc796`, required CI
  run `41435704857`. Check live successor work before resuming. Three
  original driver identities, two identical static reports per module, exact
  SND/XBSND byte equality, retained static conflicts and NetLink indirect target.
  **Zero original 68000 instructions executed.** [Contract and evidence](../research/2026-11-02-original-sound-code.md).

Private original reports: `/home/dev/neptune-research-private/591/position-002/`,
`/home/dev/neptune-research-private/594/split-add-001/`,
`/home/dev/neptune-research-private/596/sound-001/`. Supervisors/commands/logs:
`/home/dev/neptune-evidence/code{591,594,596}-20261102/`. Earlier reports remain
immutable. The accepted kernel/interpreter inputs retain the identities in those
reports; do not re-extract or ask for discs. Original full media/states and code
containers remain host-private.

## Ownership, workspace and limits

Owner of the completed slices: this existing Codex app session. Workspace
`/home/dev/neptune-code-recovery-20261102`; current branch
`research/saturn-sound-code-596`, based on accepted main `a8cbc796`. No existing
checkout was reset; the original restart checkout's untracked UID files remain.
Host leases were released by each completed supervisor; no foreign lease or
provider admission was changed. Existing current host shared limit was observed
as 3, not raised. No model session, paid fallback, scheduler, continuity activation
or new allowance was launched. Existing provider/account/CI spend is unknown.

Preserve the VPS coordinator's active #597 original-SH2 caller instrumentation,
its separate core/locks/states, and Gemini/Antigravity #487 sprite paths. #590/592
B934 stack evidence is accepted and must not be replaced by the older synthetic
smoke or repeated as new work. Shared manual-session continuity #536 remains
open; do not start another scheduler or claim live Neptune continuity.

## Exact next commands and eligible work

First reconcile accepted publication and preserve new active claims, without a new provider call:

```sh
gh pr view 598 --repo elgansayer/Neptune-Bomberman \
  --json state,headRefOid,mergeCommit,statusCheckRollup,autoMergeRequest
```

Then continue selected sound code inspection with the prepared read-only recipe
(the accepted native decoder cache already exists):

```sh
timeout 60s nice -n 10 python3 \
  /home/dev/neptune-evidence/code596-20261102/inspect-next-sound.py --subroutine
```

Concrete next sound question: the five original NetLink wrappers set A2 to
4124/414C/4138/4160/4174 and branch to4104, which calls4B00 before the4122 jump.
Derive `0x4B00`'s actual call/return and A2/A6/memory contract before propagating
those bases across it. Preserve the unresolved transfer until that evidence
exists. Natural validation needs a bounded 68000 register/memory observer; the
present tool is a disassembler. Do not map devices as flat RAM to force execution.

Independent next SH-2 entries are `0x06006B38`, `0x0600940A`, `0x0600942E`.
Selected original disassembly already shows signed 16-bit record-offset behavior,
a conditional flag/countdown update and a 16-entry caller loop. That is a lead,
not tested scheduler semantics. Before claiming, recheck live issues/PRs/owners,
derive exact controlled data/stack/read/write contracts, take existing host
admission, run twice with meaningful mutations and publish tested evidence.
RNG taps remain unknown. Continue module/function/range/caller accounting after
every bounded result; none of these children closes #464/#477/#515.
