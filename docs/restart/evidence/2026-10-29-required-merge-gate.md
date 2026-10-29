# Required tests-only merge bootstrap

Issue #62. Main's `MERGE_POLICY.md` authorizes native automatic merging after
applicable exact-head/current-base tests, with no mandatory approving reviewer.
This is separate from OpenHands #33 and uses no model provider.

## Observed configuration and checks

The host's existing credential could read and update repository administration.
Before setup: `allow_auto_merge=false`, no rulesets, main classic protection
returned `Branch not protected` (404). There were no existing protections to
remove. After setup: repository auto-merge is enabled; main requires
`Neptune merge gate` from GitHub Actions app ID 15368 with strict/current-base
execution; admins are subject to the rule; required approving reviews are zero.
Force pushes/deletions are disabled, merge commits and stacked branches preserved.

PR #64's first exact head `d890086d64edb050c66d66b7b13bc722f771181e`
passed run [40854157698](https://github.com/elgansayer/Neptune-Bomberman/actions/runs/40854157698).
The always-running aggregate and classification are described in
`tools/merge_gate/README.md`. All 15 contract tests passed, including real Git
stale checkout/head/base rejection and empty/missing/skipped/neutral/failing test
report rejection. Those are tooling tests, not gameplay certification.

Intentional negative PR #65 at `aee0bbc5cce651d20be7d6b9410e2271b8858620`
failed run [40854262402](https://github.com/elgansayer/Neptune-Bomberman/actions/runs/40854262402)
with an explicit failing unittest. It was enqueued using `gh pr merge --auto --merge
--match-head-commit <sha>`; GitHub reported OPEN/BLOCKED with the failed required
check and a pending auto-merge request. Auto-merge was then disabled on the probe
and it was closed without merging. Its intentional failure is never product work.

The current revision will be enqueued while its own check is pending to demonstrate
a real native automatic merge, and the resulting head/base/run/merge identity
will be recorded in #62. This document does not assert that future result.

## Boundaries and follow-up

Gameplay changes require the entire discovered bot suite, real native addon/runner
probes, and actual graphical/headless client/server startup/connection tests.
Known legacy gameplay failures therefore block gameplay integration. The explicit
infrastructure-only tier can bootstrap #49's runner without claiming those legacy
fixtures are healthy. No failed assertion is removed or relaxed.

PR #51's run 40850624847 was inspected: the graphical client exceeded the external
ten-second process bound after both headless clients passed. That workflow did not
retain artifact logs. Durable diagnostics and a focused investigation remain
required before integration; re-running unchanged failures indefinitely is not a
repair. The new aggregate preserves report/command/runtime logs on failure.

Branch setting snapshots and probe results are retained under
`/home/dev/neptune-evidence/merge-*`. Native runtime, bot policy quality, reference
extraction, browser cross-play and continuous factory/restart recovery remain
separate. External reference media/release, provider/spend policy and off-host
backup prerequisites remain #48. Additional paid-provider calls: zero; total
account spend unknown. Follow dependency order #49/#51/#60/#63, then remaining
#30, #31/#32, #35/#43 and the accepted creator/co-op slices.
