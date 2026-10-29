# Startup CI diagnostics and current integration blocker

Issue #62; PR #51. Inspected failed run 40850624847 at head `46fa817`: both
headless clients passed, then the graphical Godot process exceeded the Python
supervisor's ten-second external guard. The workflow did not upload the runtime
logs, so a precise original driver/startup cause cannot be recovered from that run.

The candidate pins the graphical test to X11, compatibility OpenGL and Mesa software
rendering under Xvfb. Each engine invocation records command, external bound,
elapsed time and exit/timeout status next to its log. External startup/execution
guard defaults to 30 seconds (configurable only within 5–60); the actual probe's
five-second connection timeout and ping/pong assertion are unchanged. This is a
bounded startup smoke check, not a network latency tolerance or game timing change.
Timeout failures retain diagnostic tails rather than only a Python traceback.
Both the required gate and informational native workflow upload failure evidence.

```sh
python3 tools/godot/check_runtime.py --godot <pinned-Godot-4.5-binary> \
  --graphical --evidence <output-directory>
python3 tools/godot/run_bot_tests.py --godot <pinned-Godot-4.5-binary> \
  --timeout 240 --max-log-mib 16 --log <full-native-log>
```

Local real default/explicit headless and graphical client/server ping-pong, bind
failure and invalid configuration checks pass. Graphical client: 2.990 seconds;
headless clients: 1.635/1.553 seconds. Evidence:
`/home/dev/neptune-evidence/runtime-startup-diagnostics/`. These are Linux native
checks, not browser cross-play or complete matches. Exact-head CI remains required.

The full native run retained under `pr51-full-current-gate.log` executed eight files
with eleven results: nine passed, two failed. The three-bot diagnostic observed one
death, and the open-area own-bomb test stopped at Manhattan distance two instead of
the existing strict greater-than-two assertion. No engine/script error was found;
the supervisor correctly exited non-zero for failed assertions. The earlier
ObjectDB warning also remains recorded. These failures block gameplay integration;
no assertion/tolerance was removed. #66 isolates a bounded refuge/commitment repair
under #30 while #62 remains active. The three-bot death cause still needs diagnosis.

Current-base #49 was revalidated by local native/tooling checks and required run
40854796228, then merged automatically as `1773f020`; branch and old worktrees were
preserved. Required gate #64 previously merged automatically as `50c5cb92` after
run 40854537754 passed. Main requires the GitHub Actions app-pinned gate with strict
base checks, zero required approving reviews and admin enforcement. No admin bypass
or new reviewer/factory dependency was introduced.

Correction to an early probe report: #65's second run 40854678482 used event base
`44c5c10` and ran its intentional failure; it did not reject before test execution.
GitHub separately marked the queued probe BEHIND after main advanced, so it stayed
unmerged. Local actual-Git contracts establish stale merge-parent/event rejection.
The probe is closed without merging. Distinguish these observations from each other.

No continuously running Neptune factory/recovery or reference extraction claimed.
Additional paid-provider calls: zero; account-wide spend unknown. Private selected
release/media, provider-cap policy and off-host backups remain #48 dependencies.
