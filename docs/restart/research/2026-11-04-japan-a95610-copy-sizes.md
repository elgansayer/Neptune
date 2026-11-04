# Japan A95610 copy-size paths

The probe executes original Japan `0KRNL.BIN` A95610 from a constructed direct
entry using captured frame-1200 WorkRAM-H. It fences instruction fetches to the
dispatcher, unrolled short-copy bodies, and long-copy body; reads are limited to
the literal, selected jump-table entry, source arena, and stack. Writes are
limited to the destination arena and stack.

It runs 69 lengths twice each (two constructed register seeds): all 17 aligned
short lengths `0,4,...,64`, all 48 nonmultiples of four from `1..64`, and long
path samples `65,67,68,88`. The aligned short path copies exactly the requested
bytes and returns. The 48 nonaligned short values select targets outside the
bounded code window before destination stores. The long path copies
`floor(length/4)*4` bytes and reads one additional longword as its exit
lookahead: the observed `(requested, copied, read)` byte counts are `(65,64,68)`,
`(67,64,68)`, `(68,68,72)`, and `(88,88,92)`. A mutated length-four jump-table
entry adds an unintended destination write and is detected.

The paired private report is
`execution-244/japan-a95610-run-pair.json` (SHA-256
`e0042a143bc3c43c09e685116430a89234c7dffb07a8fce715f45ff030288f74`). The
reproducible tool is `tools/saturn_lab/probe_japan_a95610_copy_sizes.py`.

This is direct constructed CPU execution with aligned, disjoint source and
destination buffers. It does not establish natural caller behavior, overlap
semantics, unaligned hardware behavior, the entire greater-than-64 length
domain, device timing, or whole-game recovery. The nonaligned short targets are
reported as bounded code-fence stops; no hardware exception is asserted.
