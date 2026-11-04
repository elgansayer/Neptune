# Japan A208 through AB94 in one CPU instance

This continuation extends the original Japan kernel path beyond its captured
AB94 PR. It begins at `0x0600A208` and executes original `AE3A`, `ACE8`, `A164`,
`A186`, then continues in the same SH-2 CPU and memory instance through `AB94`,
`AB30`, the later `A186` restore, and `AD38`. It continues the AB94 row scan and
stops at the declared 8,192-instruction bound in the `AC26–AC70` loop, with the
next PC `0x0600AC60`.

The source is Japan T-14302G V1.000 `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped at
`0x0600A000`. The initial WorkRAM-H image is from frame 1200, state SHA-256
`c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`, normalized
WorkRAM-H SHA-256
`3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff`. The code
ranges are checked against both the original kernel and captured resident bytes
before execution.

Two executions use VBR slot 0 and different constructed register seeds. Each
records 8,192 executed instructions, 1,190 reads and 60 writes. Both reach the
captured AB94 continuation, execute the later `A186`/`AD38` path, and follow the
same repeated `AC26–AC70` scan up to the instruction cap. Their PC traces, read
events, and write address/width sequences match; stack and task-table write
values differ where the seeded registers differ. Two fresh reports are
byte-identical, SHA-256
`8b5a92f177317047d50dae8ba32e5ebd4fe5571962336676cdc13ad9a76ed78b`. Probe
SHA-256 is
`f8c36c3252f21f9ab667615c05792df41395e8f51a8a64c6ad981ffa2db4c2f6`.

The separate VBR slot 1 attempt is retained as a guarded failure: at original
`AD10`, the selected input leads to a longword write at address `0x4` with
`R2=0`. No memory region was invented to make that case run. The test harness
also retains earlier bounded-stop and seed-comparison assertion failures; they
are excluded from the paired successful report. The existing `AE6C` branch
mutation belongs to the earlier A208 edge experiment and is not a mutation
control for this extended continuation.

Initial GPRs, stack and VBR-slot choice are constructed; frame-1200 WorkRAM-H,
task rows and saved context bytes are captured. This is not a natural full
scheduler cycle or hardware trace. The 8,192-instruction stop leaves the scan
completion and later task return unresolved. BIOS/device timing, gameplay,
other modules, assets and whole-program coverage remain open. Execution uses the
pinned SH-2 interpreter; the configured Beetle observer allowlist and limits
were unchanged.

The reproducible probe is
[`probe_japan_a208_ab94_same_instance.py`](../../../tools/saturn_lab/probe_japan_a208_ab94_same_instance.py).
