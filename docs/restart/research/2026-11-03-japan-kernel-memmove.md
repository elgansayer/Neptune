# Japanese kernel overlap-safe byte copy

This continuation uses the unchanged Japanese `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at the candidate address `0x0600A000`.

## Original-byte execution

The original helper at `0x06095AFC` has code range
`[0x06095AFC, 0x06095B3E)`, including the RTS delay slot. It compares
destination and source addresses, returns immediately for equality, copies
forward when destination is below source, and copies backward when destination
is above source. It returns the destination in `r0`. This is the byte-copy
helper called by the original VDP command builder at `0x0600CA42` through
`0x06095AFC`; that caller is not part of this execution.

`tools/saturn_lab/probe_japan_memmove.py` executes only those original bytes,
with a constructed 256-byte arena and no BIOS, VDP, or MMIO mapping. Its 120
cases cover both overlap directions, disjoint regions, equal pointers, zero
length, short copies, and varying lengths through 96 bytes. Every case runs
twice in each of two identical reports. The probe checks the final entire
arena, exact byte reads and writes in direction-specific order, preserved
registers, stack and return value. Replacing the backward source decrement at
`0x06095B2E` with an increment is rejected by an overlapping case.

The paired reports
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-081/japan-memmove-run1.json`
and `japan-memmove-run2.json` are byte-identical at SHA-256
`bf8a87aad4a2c10c83ee683308007c7cce2a6240cf665b81dfe3054f8d0d6ab7`.
The executed source range SHA-256 is
`173c81cfc1c8416019b78b8a6c66d52586b847bbc51d678cfc40e828fc360008`; the
probe SHA-256 is
`21886d352e7a601afd376c121b74f436f56c626d9654e425c2b7757f91aadde9`. The
helper preserves `r2`, `r4`, `r6`, `r8`–`r14`, and `SP` in these cases. It
changes caller-saved `r1`, `r3`, `r5`, `r7`, as well as the SR condition state.

## Caller and surrounding code, static only

Pinned SH-2 decodes of original bytes are retained privately:

| Window | SHA-256 | Observation |
| --- | --- | --- |
| `0x0600BFCA` | `00359adb1e0dbe2b9c1ba2483762656ef124e856070bbc4090c317f9c17fc613` | Startup path reaches input polling and state dispatch; includes cache-through reads and callbacks. |
| `0x0600C104` | `19c1fdeb7731e61990f3c566f739707fab17cee2e28bf8d1823260aeb3345a48` | Called from the controller loop; packs caller-derived state into a callback before returning. |
| `0x0600C242` | `4a12152817970f9d96e68016038a1aa3202636ca3eeb917ad9b61f30f163e6dc` | Tests controller bits and updates several counters and selector state. |
| `0x0600C380` | `0ffc189ae909d5c912f7600242dcef1071736b37d373bdfa09a149fba3a2ae82` | Continues controller-bit counter updates and returns through `0x0600C808`. |
| `0x0600C808` | `221f13ae991150c25ad3454a3f65f28695f116b7afbb909f0742ceab33c4cda5` | Dispatches into `0x0600EBAC`; adjacent code enters callback-heavy resource/state work. |
| `0x0600C946` | `e09fc20f3eb2eb876e33b6438e3f871b403ca0bf1fe3a0320e112f82212404f9` | Shows more callback/state transitions and `0x0600CA42` geometry/command setup. |
| `0x0600CA80` | `c765b73c8b124701cacd1b54c70bc11b26ad4f3091ec6b6e53e1a3ee1ec7b150` | `0x0600CA42` finishes a VDP1 command record and tail-jumps to the tested byte-copy helper. |
| `0x06095AFC` | `8570660793bdb9711dd31a79a6e74678254bfef515545280ab85b0ddaae29edb` | Original copy helper and following neighboring entries. |
| `0x0600CBB8` | `b3ca927d501c8de01b9478ab4808e7336bb0e098c4ba4a6f824cfdff3ac2fd1a` | Polling callback tests a cache-through sentinel and repeats the `0x0600CB96` handler until it becomes `0xFFFFFFFF`; following code initializes callback records. |

These static windows do not validate controller semantics, callback contracts,
VDP1 hardware behavior, natural caller reachability, or gameplay. The CPU probe
is not independent-emulator confirmation. Continue with the controller caller
and VDP command/data dependencies, then other original modules and assets.
