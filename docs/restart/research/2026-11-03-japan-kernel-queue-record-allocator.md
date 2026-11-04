# Japanese kernel queue-record allocator

This result uses the unchanged Japanese kernel `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Original-byte execution

The leaf at `0x060A753C` has range `[0x060A753C, 0x060A7564)`, including its
RTS delay-slot instruction. Original literals identify global pointer
`0x060FB580` and slot offset `0x44C`. For a constructed slot whose occupancy
word at `+16` is nonzero, the function returns zero without reading the input
context or writing the table. For a free slot, it reads context fields at
`+8` and `+0`, writes their wrapping sum at slot `+0`, writes 1 at `+4`, the
incoming R5 value at `+8`, and 1 at `+16`, and returns the slot pointer.

The paired reports in private `execution-102` each contain 128 free/busy
cases (64 input pairs in both slot states), each executed twice. Both reports
have SHA-256
`af3c28cfad4aa66bb7a3746dc52c4f3819b9e43930bb31d3e8dff628da1f358e`; the
ordered results digest is
`92076c9ff38e7f7669bd84aeb7517ce630eb00c9cfab6b4beb8a3dbb4189bb8a`. The
executed code and literal hashes are
`927fe0a8d56b58f9651403de6b94becad28cd6ff51638426afba748c2a2b4a0a` and
`9f8acf0887da6d36fc8ca0aaf37885324ad8d4eff4c7d30566bca6f3290447fe`. The
probe hash is
`7add28b2048f9b0eec07219b2dd0e1ccadc38b12b1551f289264ab9e3b145eda`.
Replacing the occupied-marker store at `0x060A755E` with `nop` is rejected.

This uses a constructed global pointer, table and context. The allocator's
natural callers, queue lifetime, service effects, device timing and gameplay
are not established. Earlier retained reports `execution-100` and
`execution-101` contain harness expectation failures; the corrected paired
run is `execution-102`.

## Request-service follow-up

Static state-zero code at `0x060A6FFA` calls the arithmetic leaf at
`0x060A750A`, this allocator at `0x060A753C`, a global indirect dispatcher at
`0x060A6C94`, and an SH-2 division-MMIO helper at `0x06095C8C`. Only the two
bounded leaves have been executed here; callback-table provenance and
division-device behavior remain unresolved.
