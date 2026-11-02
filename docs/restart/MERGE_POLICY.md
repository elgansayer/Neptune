# Tests-gated automatic merging

Elgan's direction, 29 October 2026: do not wait for an AI reviewer. Merge eligible
PRs automatically when the required tests pass. This supersedes earlier mandatory
independent-review language in restart documents, issues and PR descriptions.
AI review is optional and must not become an unattended approval queue.

## Meaning of passing

- A non-draft PR is mergeable and has a known, non-empty set of required checks.
- All required checks succeeded for the exact candidate head and current base.
  Missing, skipped, neutral, cancelled, timed-out or failed tests are not success.
- Applicable runtime tests actually execute. Python input/catalogue tests alone
  cannot qualify gameplay or bot changes. Preserve existing behaviour assertions;
  do not remove failures or weaken fixtures merely to enable a merge.
- Dependencies are integrated in order. Preserve stacked branches until children
  are safely retargeted; merge commits preserve ancestry during this bootstrap.
- No manual or AI approving review is required. An actual failing check is a
  repair task, not an invitation to bypass the gate with administrator privileges.

Use GitHub's native auto-merge after required checks and the repository setting
are configured. A dedicated AI PR-review factory is not a dependency. A worker
enables auto-merge on each ready PR; GitHub waits for checks. A later sweep can
enqueue missed PRs without executing any PR code under a write-privileged token.

## Bootstrap observed in this session

- `allow_auto_merge` was false; no repository rulesets were returned.
- Classic branch protection could not be read through the connector (403), so its
  absence was not established. Preserve existing protection/settings when editing.
- Main had no workflow; PR #39 introduces input/catalogue CI.
- PR #49 introduces native runner/addon checks. PR #51's latest checked head failed
  native CI; inspect and repair the actual failure before merging it.
- Native runner checks are not a complete gameplay regression suite. Their current
  workflow also omits several gameplay paths. Do not advertise broad game auto-merge
  coverage until the required gate runs for those changes.

The policy alone does not enable a GitHub setting or start a background service.
Report those states separately. The one-time foundation integration may use the
GitHub merge API after its exact-head tests pass; that is not evidence of a running
continuous merger.

## Required preparation and native auto-merge

Issue #610 addresses an observed gap: PR608 automatically merged at 12:51:30 UTC
on 2 November after its native gate succeeded, while its applicable
`Pinned Godot and Saturn installation` check finished at 12:53:10. That check
eventually passed, but native auto-merge did not wait for it. The shared factory
merger's conditional supplemental-check rule does not configure GitHub protection.

Both literal checks must be required in GitHub, with the existing Actions app
ID15368 and strict/current-base protection:

- `Neptune merge gate`: applicable nonempty tooling and real native tests.
- `Pinned Godot and Saturn installation`: the always-present preparation aggregate.

The preparation workflow runs on every PR. Its first job verifies exact merge
parents/base/head, classifies complete changed paths with rename sources and
deletions included, and publishes a selection digest. The aggregate independently
recomputes that selection. Applicable core/OCR/Xvfb jobs must succeed, followed
by real Godot/core preparation and reuse. Only an explicit matching unrelated
selection permits the preparation children to skip. Missing, failed, stale or
skipped applicable dependencies fail the aggregate. An empty/malformed selection
is not proof of non-applicability. Explicit manual runs prepare all tools.

This keeps ordinary metadata PRs eligible without rebuilding unrelated tools or
waiting forever for a path-filtered required check. Read back actual protection
after configuration; source alone does not establish that both checks are required.
Keep all other protections and zero mandatory approving reviews intact. A queued
auto-merge demonstration must show both required checks completed before merge,
plus their exact head/base, enable/merge timestamps and resulting commit.

The corrected path was observed on [PR612](https://github.com/elgansayer/Neptune-Bomberman/pull/612):
auto-merge enabled at 13:02:59 UTC; native aggregate succeeded at 13:10:19;
preparation aggregate succeeded at 13:13:01; GitHub merged at 13:13:38. The
coordinator observed the PR still blocked while native tests were green and
preparation was running, and made no further merge call after enabling auto-merge.
The [exact-head/base ordering receipt](evidence/2026-11-02-native-auto-merge-ordering.json)
includes the two app-pinned statuses, real installation/dependency evidence and
438 passing native results in 45 files. This validates the applicable-preparation
path. The workflow's explicit non-applicability path requires its own live check;
unit tests alone do not establish that GitHub executes it correctly.

Keep [control alignment #613](https://github.com/elgansayer/Neptune-Bomberman/issues/613)
separate: the formerly deployed control preflight expects one literal check and
must adopt the two-check contract. Neither this GitHub merge nor local policy
tests establish updater adoption, manual-session enrolment or Neptune continuity.

## Configuration and acceptance on the server

1. Finish the active bounded task and fetch current main/foundation. Use an existing
   authorised GitHub credential with repository-administration permission. Do not
   print credentials or assume a connector's reported user role grants the app
   administration access.
2. Read current rulesets/classic protection. Set zero required approving reviews
   for the intended tests-only policy while preserving unrelated protections.
3. Establish an always-running required aggregate check, e.g. `Neptune merge gate`.
   Require current-base execution. Run input/catalogue tests; require native
   build/runner/runtime and relevant bot/gameplay tests for applicable changes.
   If required tooling is missing, fail clearly. Path filtering must never let a
   gameplay PR pass with no relevant tests; skipped subjobs need explicit proof
   that they do not apply. Pin status sources to the intended GitHub app.
4. Test a deliberate failing PR, an empty/skipped selection, a stale head/base and
   a real passing PR. Only the latter may become mergeable. Do not configure a
   status name that no workflow actually produces.
5. Enable repository auto-merge, then enqueue ready PRs with `gh pr merge --auto`
   and an expected head SHA. Use ordinary merge requirements, never `--admin`.
   Re-read head/check/base state after pushes or retargeting. Failed cases stay open
   for repair; avoid repeated unchanged reruns.
6. Merge the bootstrap stack in ancestry order, retarget children deliberately and
   rerun affected checks. Keep #18/#20 as overlap candidates until #49 is integrated;
   do not blindly merge both older runner implementations on top of it.
7. Demonstrate one automatically completed merge and retain workflow/run/head/base
   evidence. Then add a minimal event/scheduled enqueue sweep if workers miss PRs.

No provider spend, emulator inputs or OpenHands deployment is required to configure
GitHub auto-merge. Missing repository administration access is a concrete blocker,
not a reason to wait for another AI reviewer or to mark configuration complete.

## Evidence changes

Keep reference/tolerance changes traceable and verify their new captures and
regression-detection checks. Optional review can add confidence, but the accepted
merge gate is executable checks. Preserve source provenance, permissions and
production-secret boundaries; tests passing is not a claim of complete fidelity.
