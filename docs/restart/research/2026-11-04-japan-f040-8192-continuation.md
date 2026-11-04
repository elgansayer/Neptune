# Japan F040 continuation through the 8,192-instruction bound

The F040 probe now accepts only four explicit instruction limits: 1,024
(default), 2,048, 4,096, or 8,192. Kernel/state identity, source-matching code
fetches, captured WorkRAM data fences, and selected register snapshots remain
in force.

Two fresh runs at the 8,192 limit produced byte-identical reports with SHA-256
`2f1e7364af722285ce2d47645e5a87b2a6ab84368dc2f31f0a72f86bee2ba459`. Each
constructed seed executes exactly 8,192 original instructions, records 868
reads and 288 writes, completes 35 calls to `0x06095C24`, and begins a 36th
call. Execution stops at `0x06095C6A`, before that call returns. PC/read traces
and write address/width shapes match across seeds; stack values vary with the
constructed seed.

This extends the same direct-entry experiment; it is not a natural A20E return,
full function return, or hardware wait observation. The repeated call train
remains unresolved and may depend on state beyond the CPU/WorkRAM model. Do not
assign a service or helper name from this evidence alone. The original
functions, other game modules, gameplay, audio/DSP, and all assets remain open.

The reproducible tool is
[`probe_japan_f040_entry.py`](../../../tools/saturn_lab/probe_japan_f040_entry.py)
with `--instruction-limit 8192`. Probe SHA-256 is
`ecd12a00d7436154dc12dca35117746cba33f89980a68a7ae391bb8b7797c756`. Private
reports remain on the VPS under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-326/`.
