# Japan A8E8 caller to A80E/AACC

The probe executes original Japan `0KRNL.BIN` from A8E8 through A80E and its
AACC callback, stopping at the A79C error-loop or ACE8 scheduler-handoff edge.
The five cache-through words used by the VBR-selected caller are explicit
aliases of the corresponding WorkRAM-H locations; the probe does not model
cache-maintenance effects. Four constructed caller cases run twice each, with
VBR slots selecting different table rows. Each output is compared with the
independent A80E byte-transition model, including the AACC latch store and
both global-count exits.

The paired private execution report is
`execution-251/japan-a8e8-caller-run-pair.json` (SHA-256
`5b27497e1c60ab18f274883dde8ffc6282cfa923a932fe6af0ff8be393ef6977`). It
contains eight original-byte runs, all with one A80E call; both VBR rows in the
callback case also enter AACC. The changed A80E immediate control
(`EDFF` to `EDFE`) is rejected.
The three earlier failed harness attempts remain privately retained as
execution-247 through execution-249; execution-250 is the successful initial
three-case run superseded by this four-case run.

This proves a constructed original-byte caller composition, not natural
reachability or scheduler behavior. The probe stops before either exit target
executes. No device timing, cache effects, gameplay semantics, other modules,
or full-game recovery are claimed.
