# Japan A208 through AE3A to captured AB94 resume

This extends the paired A208/AE3A edge probe into one CPU and memory instance.
It executes the original A208 indirect callsite, the AE3A task-row loop, ACE8,
the A164 context save, and the A186 restore. Starting from captured
frame-1200 WorkRAM-H, it follows the captured task cursor and VBR-selected row,
marks row `+81=4`, saves the live frame into the row context, restores the
captured 48-byte context at `0x060BDD7C`, and reaches its PR target
`0x0600AB94`. The probe stops before fetching AB94.

Two original-byte runs use different initial register seeds. Each executes 119
instructions and records 29 reads and 27 writes. Both stop at AB94 and restore
the captured R8-R15, PR, MACH, and MACL values; the A186 RTS delay slot's R0
effect is checked separately. Inverting the AE6C branch changes the task words
stored by ACE8 and is rejected. Reports from independent executions 291 and 292
are byte-identical, SHA-256
`074c8fbcde8e3c45b190c3df4be8d8c22a2e4b8873348bcebc94b499b6dc8753`, each mode
0600. Probe SHA-256 is
`158dbbf945a8083cd42fb2e6d5b3800b52ac8c6b0a699b3915ba0e84e5325f9b`.

The source is the original Japan T-14302G V1.000 KRNL at `0x0600A000`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`. Frame-
1200 WorkRAM-H supplies the task cursor, selected table row, cache-through words,
and saved context. Remaining general registers and stack are constructed. This
composes a captured-state handoff, not a complete natural scheduling cycle;
AB94's body, device timing, gameplay behavior, other VBR slot's full transfer,
and broader module semantics remain open. The earlier boundary-only report and
failed harness attempts 289–290 are preserved privately. Continue the AB94 live
state path and the A208 caller's F040 continuation, then expand across remaining
original code and asset inventories.
