# Japan AB94 with A208 caller registers and prefix writes

The A208 prefix probe now records all GPRs and PR/MACH/MACL/VBR at its AB94
stop. In its two seeded original-byte runs, R0-R5 and R8-R15 are identical;
R6/R7 retain the declared seed values. Each report executes 119 instructions
and stops before AB94. The pair is archived in private execution 295 with report
SHA-256 `acc730d9610ab239bad5e8f515f988dcd41374f0d8d67ef44b0e5c76990b3d2b`.

A follow-up replays the A208 prefix's bounded stack/task-row/cache-alias write
events and caller registers into a separate CPU instance, then executes original
AB94, AB30, A186 and the AD38/ACE8 path. This is caller-derived input, but not a
single CPU/memory composition. R6/R7 remain seeded, and the run retains the
instruction budget of 8192. Both seeds execute 8191 instructions, take the same
loop through AC26–AC70, and stop at PC `0x0600AC46` when the budget is reached;
neither reaches A186's task-row restore in this continuation. Each run records
1177 reads and 33 writes. Across the trace every row's first longword and +80
byte is read: first words for rows 0–17 are `0,2,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,2`;
+80 bytes are `1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,1`. Original AC26 compares
the first longword against 1 before testing +80, so the caller-replayed table has
no row passing that first filter. This accounts for the observed scan under this
input; it does not establish the natural scheduler's selection policy. The final PCs are
`AC44, AC46, AC48, AC60, AC62, AC64, AC66, AC68, AC6E, AC70, AC26, AC28,
AC2A, AC40, AC42, AC44`, confirming the bounded scan loop at the stop.

Changing ABCC from `88FF` to `8800` changes the budget boundary to `AC48`, so
the mutation control detects a path/effect change. Two independent execution
299 reports match byte-for-byte (SHA-256
`78459dc34eee8f8e04bb067ba989ee71b7f1a7540e7ee0f15f01ed7989c18a4e`), each
mode 0600. Probe SHA-256 is
`ac7e0a438f2539a49b7824f85678ee09f18a896e0c866dc32f398f95d49f1031`.

This establishes a repeatable original-byte scan prefix under replayed caller
state. It does not establish scan completion, natural dispatch, the row restore,
hardware timing/effects, gameplay behavior, or full-game recovery. Next, account
for the missing same-instance state at the A208 boundary, trace the AC26–AC70
scan termination condition against all 18 captured task rows, and continue into
remaining functions/modules and asset inventories. The full programme remains
open.

Private source/report inputs are the original Japanese kernel and frame-1200
checkpoint documented in the local 0600 checkpoint. The A208 register report is
execution 295; the caller-state AB94 reports are execution 300. No raw ROM,
state, or run reports are committed.
