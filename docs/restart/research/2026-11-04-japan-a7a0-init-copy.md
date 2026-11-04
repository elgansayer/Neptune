# Japan A7A0 startup record initialization

The probe executes original Japan `0KRNL.BIN` at A7A0 with the actual A164
context-save helper and A95610 copy helper. It uses frame-1200 WorkRAM-H, checks
the original code bytes at all three ranges, fences instruction fetches to those
ranges, folds cache-through aliases onto WorkRAM-H, and rejects stores outside
the bounded stack, global words, frame, and destination table.

Each of two constructed register seeds runs twice and returns after 2,431
instructions with SP restored. Each execution observes one A164 entry, eighteen
A95610 entries, 459 writes (456 longwords and 3 bytes), 591 reads, and eighteen
identical 88-byte rows copied from the initialized frame at `0x060BDD24` into
`0x060BCEEC..0x060BD51B`. Changing the original `0x630` row-span literal at
`0x0600A8C2` to `0x5D8` reduces the observed copy to seventeen rows and is
rejected by the contract. In these runs R8–R15, MACH and MACL are preserved;
only the SR T bit changes, from 0 to 1, at the final bound comparison.

The private paired report is
`execution-241/japan-a7a0-run-pair.json` (SHA-256
`b4e12f565904fa13cc875897dd1ffd1ee12d376dac4c672ab29c605593055039`). Initial
exploratory and ABI-check attempts remain in `execution-237/` through
`execution-240/`; the early incomplete reports are superseded by this final
source-bound run.

Entry registers and the startup/task context are constructed. This establishes
the bounded behavior of these original bytes, not natural A7A0 reachability,
startup timing, device effects, or game-wide behavior. A95610's short-size jump
table and behavior outside this caller's 88-byte copy remain open; Japan/USA
module and asset inventories also remain incomplete.
