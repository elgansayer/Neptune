# Japanese kernel descriptor table update

This result uses the unchanged Japanese `0KRNL.BIN`, SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`, mapped
at `0x0600A000`.

## Original-byte execution

The bounded helper at `0x0600CD74` has range
`[0x0600CD74, 0x0600CDA0)`, including its return delay slot. It compares `r5`
unsigned against 4 and exits without data access when `r5 >= 4`. Otherwise it
uses the low word of `r4` as a record index, reads a pointer from the selected
type table at `0x060BEA3C`, loads the selected record longword, writes it to the
pointer result table at `0x060BEA4C`, and writes the type word to
`0x060BEA7C`. The caller at `0x0600CDA0` statically appears to repeat this for
12 record indices, but that caller has not yet been executed as a composed
sequence.

`tools/saturn_lab/probe_japan_descriptor_update.py` executes the original
helper and the three original literal words from the Japan kernel. It uses
constructed table contents and checks exact reads, writes, the resulting
tables, callee-saved registers, stack, and return linkage. Its 101 cases cover
all four accepted types and 12 indices with two different high-word patterns
in `r4`, plus five `r5` values at or above 4. Each case executes twice in each
of two identical reports. Replacing the original type-bound branch at
`0x0600CD78` with a NOP causes a rejected type to perform table accesses and
writes, so the mutation control fails as expected.

The reports
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-085/japan-descriptor-update-run1.json`
and `japan-descriptor-update-run2.json` are byte-identical at SHA-256
`fe43e2a73ceedc0eedbf4cbb9acd164612f72bb6b00edb7d04f6375dfc18c54e`. The
executed code range SHA-256 is
`1413c100678fe0f8edd796170fb382d677cf34a1327fad47796328ba2aea21f4`; the
three source literal words have SHA-256
`7b8bc29a21ae2ff09c1161df12c35de36d5a37b3fa9591090d59f8be14fd64ec`. The
probe SHA-256 is
`5bb3e8fc9761d99eb9c7d36e23bb62c0a05b7ba45f09e33015fad28bfe8db175`; the
ordered result digest is
`c3186a3262950dbb6d659e57ec9bb78d688ddec6d4d9dfc15b35c0d136048e98`.

## Static caller and service windows

Pinned SH-2 decodes of original bytes are retained privately:

| Window | SHA-256 | Observation |
| --- | --- | --- |
| `0x0600CCF6` | `eaa558c6174bd90b7365dac53d681402a31a02ffa303190093fde1ab58fc9174` | Initializes descriptor records and proceeds through calls to `96A38`, `978A0`, `96BF0`, and `96D8E`. |
| `0x0600CD74` | `9e62e4302792712f374e2b156c3c7d235c5021eeeb52e4b7f13d5b58b75822bf` | Shows CD74 and the repeated 12-index caller beginning at CDA0. |
| `0x0600CDF6` | `68f94e0fc6344012ff282812b522a6bed885d44993455b9e315a3c34d4b776b6` | Lookup and state paths enter 96E56, 97168, 9725E and 974F4. |
| `0x0600CE30` | `12b3108e55e903fc1966cc47b95364a01929b97e6644aaa581ff37cbf0ce260c` | Orchestration uses cache-through state and indirect service calls; service contracts remain unknown. |

The constructed execution does not prove that the caller naturally supplies
these type values or indices. It does not validate callback/library services,
device behavior, timing, gameplay, or independent-emulator agreement. Continue
with the composed CDA0 caller, then its service dependencies and other original
modules and assets.
