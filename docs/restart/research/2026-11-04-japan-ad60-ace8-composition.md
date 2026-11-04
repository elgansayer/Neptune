# Japan AD60 to ACE8 composed scheduler handoff

The original-byte probe now starts at AD60 and executes AD60, ACE8, A164,
and A186 in one CPU and memory instance. For each of two VBR-selected task
rows, two seeds begin with distinct R4 sentinels and a constructed nonzero
ready word. Original AD60 reads the selected cache-through alias, sets R4 to
one in the BRA delay slot, and transfers to ACE8. ACE8 stores the selected task
fields, calls A164 to save its live register frame, and enters A186. A186 loads
the captured 48-byte context at `0x060BDD7C`, restores registers and control
state, and resumes at the captured PR target `0x0600AB94`. The probe stops
before fetching AB94.

There are four composed executions per report, 93 original instructions per
execution. The probe also retains the earlier four ACE8/A164/A186 handoffs and
four ACE8/A164 prefixes, plus the A164 and A186 mutation controls: 12 original
executions total per report. Reports from independent executions 274 and 275
are byte-identical. Their SHA-256 is
`e56b691ced85e77c8128c220e3f87a22a57ae3024959b68cf0de7c19b9380d1b`; each is
mode 0600 under the private evidence tree. Execution 273 is retained as an
earlier successful run from before the report-permission hardening; it is also
mode 0600 now.

The exact AD60 edge and downstream code are original Japan kernel bytes, with
the captured frame-1200 WorkRAM-H base. The ready values, task rows, VBR slots,
and registers are constructed. This establishes the composed machine-state
contract, not ready-word provenance, natural scheduler reachability, task
lifetime, device timing, gameplay behavior, or full-game equivalence. The next
bounded step is to follow the AB94 continuation and its caller/state paths.

Probe source: `tools/saturn_lab/probe_japan_ace8_task_save.py`, SHA-256
`254423d67be359452b1efe62c893682f5846390b04585673d091c7989b3ad181`. Research test suite and exact-head
CI are recorded with the associated change. Full code and asset recovery remains
active and incomplete.
