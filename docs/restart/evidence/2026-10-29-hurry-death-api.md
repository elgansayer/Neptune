# Hurry overlap API regression

Issue #68 under #62; exposed while validating #60 after #51 merged automatically
as `2e7900f2a9eebdd32f9fa79fe75e861c6dcc089c`.

The first combined #60 local full run had 21 passing assertions in ten files, but
the supervisor correctly rejected it for a native script error at
`GameInstance._spawn_hurry_block`: `player.die("Crushed by hurry block")` called
the real zero-argument `ServerPlayer.die()`. It occurred when a survivor reached
a hurry block during the 120-second battle. A green assertion summary alone was
not accepted. Raw log: `/home/dev/neptune-evidence/pr60-repaired-local-full.log`.

Correct the caller to `player.die()`. Do not add a new reference-dependent death
rule or bypass the existing immortality/Tirra behavior. Two real GameInstance/
ServerPlayer fixture tests reproduce the failure before the one-line repair and
pass afterward: an unprotected overlap enters stopped/dead/spectator state while
bystanders survive and block creation completes; an immortal overlap retains the
existing protection while block creation completes. This preserves current Neptune
behavior and makes no claim about original Saturn hurry rules.

```sh
bash run_bot_tests.sh --godot <pinned-Godot-4.5-binary> \
  --run-specific test_hurry_block_death --timeout 30
```

Before: zero passed/two failed plus actual API errors (`hurry-before.log`).
After: two passed, no engine errors (`hurry-after.log`). Evidence root is
`/home/dev/neptune-evidence/`. Existing full-suite assertions and runtime/log limits
are unchanged. Full rerun and exact-head/current-base CI remain required before
#60 merges. The #63 pre-fix local run was terminated through its owned supervisor
after this shared API defect was proven; its cancellation/logs are retained and
are not counted as a passing run.

No reviewer approval is required by current MERGE_POLICY.md. Preserve merge
ancestry for #51/#60/#63 and integrate in order. Broader bot quality, browser
cross-play, reference extraction and continuous factory/recovery remain unverified.
New paid-provider calls: zero; account-wide spend unknown. External #48 prerequisites
are unchanged.
