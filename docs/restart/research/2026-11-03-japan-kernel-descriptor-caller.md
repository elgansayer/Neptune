# Japanese kernel descriptor caller composition

This result composes two original code ranges from the unchanged Japanese
`0KRNL.BIN` (SHA-256
`23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb`), mapped
at `0x0600A000`:

- caller `0x0600CDA0..0x0600CDC4`, including its RTS delay slot;
- helper `0x0600CD74..0x0600CDA0`, including its RTS delay slot.

## Original-byte execution

The caller saves its incoming `r4` value on the stack, then loops over indices
0 through 11. In each iteration it reloads that saved value as `r5`, passes the
current index in `r4` through the BSR delay slot, and calls the original CD74
helper. For type values 0 through 3, the composed path reads the matching
constructed type table, copies all 12 selected row longwords into the output
pointer table at `0x060BEA4C`, and writes the type words at `0x060BEA7C`. For
values 4, `0x100`, `0xFFFF`, and `0x80000000`, all 12 helper calls return
without table data access or table writes. The caller restores the saved PR,
`r13`, `r14`, and SP; the stack retains the exact spill values in its frame.

`tools/saturn_lab/probe_japan_descriptor_caller.py` executes both original
ranges with the original three source-backed literal words and constructed
tables and stack. It checks every read and write in order, both complete output
tables, preserved caller registers, linkage and stack state. Eight caller
arguments run twice per report. A mutation that replaces CD74's unsigned type
bound branch with a NOP makes type 4 write all 12 output records; the control
rejects that behavior. Failed attempts 086 through 089 are retained in the
private evidence directory; execution-090 succeeded before a no-behavior
cleanup to the probe and is superseded by the final source-matched pair below.

The successful paired reports
`/home/dev/neptune-evidence/code712-20261103/japan-kernel-study-20261103/execution-091/japan-descriptor-caller-run1.json`
and `japan-descriptor-caller-run2.json` are identical at SHA-256
`99aa57f5cd2e9f2afa19425166c741a2d3098bc24389554c1904e268798577e6`. The
ordered result digest is
`e24321ef22ce433116f339d637588923906a48a4e82a083277b78630c7638fd3`. Source
hashes are `1e5f49157415b58624c4ea398b4f5a18cee33710e7154dbd2c30fb7a38689b2d`
for CDA0, `1413c100678fe0f8edd796170fb382d677cf34a1327fad47796328ba2aea21f4`
for CD74, and
`7b8bc29a21ae2ff09c1161df12c35de36d5a37b3fa9591090d59f8be14fd64ec` for the
three literal words. Probe SHA-256 is
`2dded30cf0decaadefce340b301c0a5c206b7d9f8307de95235f0846b2e25327`.

This is a constructed caller invocation. It does not prove that a natural game
path supplies any tested type, nor recover the upstream source data, callback
or library services, device behavior, timing, gameplay, or independent-emulator
agreement. Continue with those dependencies and other original modules and
assets.
