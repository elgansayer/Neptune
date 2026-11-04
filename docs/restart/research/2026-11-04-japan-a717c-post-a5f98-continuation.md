# Japan A717C continuation after A5F98

## Scope

This bounded probe resumes at the captured A717C boundary `0x060A7244`, after
the separately probed A5F98 call. It executes original Japanese kernel bytes
through the RTS delay instruction at `0x060A727C`. The staged return target is
`0x060A71A8`. It does not claim natural caller reachability or complete A717C
control-flow coverage.

The private frame-1200 state is
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/continuation-002/boot-002-next-600frames/checkpoint.state`
(SHA-256 `c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f`).
The Japanese `0KRNL.BIN` is retained privately; its SHA-256 is
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`. The
captured WorkRAM-H bytes at `0x060A7244..0x060A727D` match those kernel bytes.

## Results

Across 64 constructed register/stack combinations, each executed twice, the
original code writes three words at `0x060FCD30`, `+8`, and `+4` in that order:

- `0` at `0x060FCD30` (`R12 & 3`)
- `base + 4*R8` at `0x060FCD38`
- `saved_R7 + 4*stack_word_at_SP_plus_92` at `0x060FCD34`

The original PC trace includes the RTS delay slot and returns through the
constructed saved PR. Saved R8–R13, PR and R14 are restored; SP advances from
`0x06007FA4` to `0x06008000`. Every other byte of the 1 MiB WorkRAM-H snapshot
was compared after execution. This is CPU-level original-byte evidence with a
constructed stack/register boundary, not hardware timing or a naturally
observed task return.

Paired reports are retained privately under
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-168/`.
The paired report SHA-256 is
`0efe283114ba9e9d82b32394d2c86f995b63fa8723e0f1ac7b64ce560d988efc`; the
result digest is `9bcf83ec9878513d588e41dc84e31eec32e017919d99df66330578f2c62a3123`,
and the executed source-window digest is
`fa433d47f9a7cbf062506d1def2cf18ce3d2566487576499d5f6474038836ab0`. Failed
earlier probe attempts are also retained under executions 163–165 and are not
counted as successful evidence.

## Continuation

Continue from the returned caller target by validating natural A717C context and
caller paths, then cover other Japan/USA kernel functions and modules. Cache
purge effects, unresolved helper semantics, complete code recovery, and all
assets remain open.
