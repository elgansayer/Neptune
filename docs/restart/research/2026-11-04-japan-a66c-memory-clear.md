# Japan A66C/A5CE memory clear

## Original-byte execution

The probe executes Japan `0KRNL.BIN` A66C and its A5CE helper using the captured
frame-1200 B3D44 pointer `0x25E80000`. The original threshold literal is
`0x1FFFC`. Two register seeds each ran twice under the pinned
`saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9` interpreter.

The two reports in
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-226/`
are byte-identical with SHA-256
`e0a5f3bad15ce9608800bfec3138b2e66b3465f786caa23024b49f028a498360`.
Normalized result SHA-256 is
`ca60bac7b94d7cde3759995c22a78dc653ec0e618bd584f9cab3ce22be0f1e63`; probe
SHA-256 is
`618330c29629bcbe91696d9bea9c7b5d974e7280c4e35c51f66a9c03d9c5f76b`.

## Recovered loop contract

A5CE initializes its word index from `R4 & R6`, then increments that index by
four before each store and loops while the index is not greater than `R6`.
For threshold `0x1FFFC`, this emits 32,768 zero longword write intents from
`0x25E80000` through `0x25E9FFFC` (131,072 bytes). The returned end pointer is
`0x25EA0000`, which A66C writes back to B3D44. Mutation controls reject a
destination shifted by four and a threshold reduced by four.

The first retained attempt expected 32,767 stores and failed at the final
address `0x25E9FFFC`; its immutable failure report is
`execution-225/japan-a66c-memory-clear-run1.json`, SHA-256
`236fcabf02f471968cd770a7631084e5996e5280bdfcffff77a00ebb1e1aa7c1`.
Inspection of the original CMP/GT and delayed increment corrected the contract
to the inclusive bound before the paired successful run.

These are explicit memory-write intents, not established hardware writes or
device effects. A546 reachability, repeated-loop pointer behavior, display
semantics, timing, and natural startup remain unverified.
