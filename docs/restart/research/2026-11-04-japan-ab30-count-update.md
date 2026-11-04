# Japan AB30 count normalization

The original Japan kernel's `0x0600AB30..0x0600AB78` body computes an unsigned
32-bit delta from the current count and the previous count, scans 18 rows of 88
bytes, and stores the current count as the next previous count. When the delta
is nonzero, it considers a row only when byte 80 is nonzero and its longword
counter is greater than one. It subtracts the delta when the counter exceeds
the delta, otherwise it floors that counter at one. Inactive rows and active
zero/one counters are unchanged. Equal counts return before table reads or
writes.

The original bytes were executed in four constructed cases (equal counts,
subtract/floor, unsigned wrap, and a high-bit delta), twice per case with
different entry-register seeds. A private mutated branch was rejected by the
independent model. The run used the pinned SH-2 interpreter and captured
frame-1200 WorkRAM-H; it does not establish a natural AB94 caller, hardware
timing/cache behavior, gameplay semantics, or full-game coverage.

Private execution report:
`execution-260/japan-ab30-count-update.json` (SHA-256
`ac63770144a32a305e86db60f8f186c12c94fc38e6b21135b9a8b95934231d85`).

Three failed harness attempts (executions 257–259) are retained unchanged. The
first exposed seed-dependent stack-event comparison; the latter exposed an
incorrect independent model that floored zero counters. Correcting the model
to follow the original `counter > 1` branch produced the successful run.

Next, trace the complete AB94 call composition and caller context against the
original bytes, maintaining the configured owner and run limits. This bounded
result is one step in the continuing full-code and asset recovery programme.
