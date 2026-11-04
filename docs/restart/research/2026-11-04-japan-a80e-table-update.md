# Japan A80E record-table updates

The probe executes original Japan `0KRNL.BIN` A80E and its AACC callback over
constructed 18-row, 88-byte WorkRAM tables. It checks original code identity,
fences instruction fetches to A80E/AACC, and permits data reads and writes only
within the declared table, literal, and stack regions. Five cases each run
twice with paired table/write results.

The observed contract treats R4 as a row index. If that row's field 82 is
`0xFF`, A80E clears other rows that reference the index and zeroes the row's
field 83. Otherwise it decrements the prior target row's field 83, clears the
selected row's field 82, transfers matching references from active rows to the
prior target, and increments that target's field 83. When the target count
reaches zero and field 81 equals four, A80E calls AACC; AACC writes longword one
at the target row start only when its field 80 is nonzero. A changed immediate
from `-1` to `-2` is rejected by the independent byte-transition model.

The private paired report is
`execution-246/japan-a80e-run-pair.json` (SHA-256
`7244867635bed6466d6218e92fe0422f0917974c808f4c8cabff3070516c62d1`). The
static A80E disassembly is separately retained at
`analysis/a80e-followup/a80e.txt` (SHA-256
`1470001599b64c55ef984c9f272c30c4f8e287a9dec5ad27a06bd86ce8aaed19`).

The table rows and incoming indices are constructed; natural callers and the
relation to A7A0 at runtime are not established. This slice does not cover all
table states, regional modules, gameplay, devices, timing, or full-game code
and asset recovery.
