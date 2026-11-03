# Natural command-root observer windows

**Scope:** six guarded 600-frame windows from the verified original boot
checkpoint at frame 1800, using the original Saturn Bomberman USA disc and
kernel. Profile 1 and profile 2 each ran reference, observer-disabled and
observer-enabled modes with the same eight-frame Start pulse. The prepared
Beetle Saturn observer core was reused locally without compilation; its SHA256
is `5ab8c9815b5ac4e1d0a78d73e201cb20cbb9d83774833456b1167abac0a9f041` and its
ABI is 2 (288-byte records, 128 storage slots, 424 witness words).

Both profiles produced identical reference and observer-disabled final state,
video and audio hashes:

- State: `207d3e58bbb24ad85791c131a91b3903ee0419242ff2988e446715fd0e252802`
- Video: `0939dcfcc86c6faae671b242573817477a7015acf574a5d829e5d1153fbe5e6e`
- Audio: `eafc18cc2ff4305e000446326d97be2a3a884cf8b114ec1ecf794d626a3b393d`

Profile 1's corrected enabled run executed all 600 original frames and collected
1,774 logical events in 102 stored records, including 1,672 lossless repeat
events, with no drops. Its final state, video and audio hashes match both
reference and observer-disabled controls. Validation confirms one complete
natural root: the source call and delay slot, entry at `0x060A4FAC`, the root
RTS/delay and return at `0x060AE698`, nested service calls and their observed
transfers. An earlier attempt was rejected because validation assumed source
call records began at buffer index zero and required two service PCs absent
from this natural path. The corrected validator finds the root within the
event stream and still requires rooted transfers and return continuity. This
establishes one bounded natural root trace; it does not assign device or
gameplay semantics.

Profile 2's enabled run also executed all 600 original frames, but exceeded the
fixed 128-slot storage capacity: 1,810 logical events, 128 stored records,
1,811 transfers observed and one dropped record. It remains rejected. A later
no-input scan clarified that these slots were consumed by pre-root transfers:
both profiles recorded 159 transfers and overflowed before any source-call/root
entry, while the reference and disabled 600-frame controls matched. This scan is
retained as a separate idle-path result, not a root. The cap was not increased.

The natural trace captures the wrapper at `0x06095992`, its call to `0x060959CA`
from `0x060959AA`, and continuation at `0x060959AE`. A guarded CPU-only replay
then started from the captured wrapper registers, SR, PR and stack; it executed
199 original SH-2 instructions across the wrapper and nested service and
returned to the captured caller PC `0x060A4FD0`. The wrapper raised SR priority
from `0x0101` to `0x01F1` around the nested service, then its restore sequence
returned to the caller state. The replay reproduced the captured 13 device
reads and five writes, returned `R0=0`, and changed global word `0x060FA8B8`
from `0x0FD4` to `0x0F94`. Its four-word output buffer was reconstructed from
the observed device writes, and no CD device timing was modeled. Evidence:
`/home/dev/neptune-research-private/707/wrapper-recovery-002/replay-report.json`
(SHA256 `0071681357d1fdccd90fcde0f8e29db1bd670780fa30e5bb8b8d144d10b97c4a`).

A second CPU-only replay of original function `0x060959CA` used the captured
natural registers and stack, status `0x0BC5`, seven `0x0B84` polls then `0x0B85`,
and register words `0x0380, 0x4101, 0x0100, 0x367A`. It executed 171 original
SH-2 instructions, returned to `0x060959AE` with `R0=0`, reproduced all 13
device reads and five writes, and changed the captured global word from
`0x0FD4` to `0x0F94`. The four-word write buffer was reconstructed from the
observed device writes. The report is
`/home/dev/neptune-research-private/707/wrapper-recovery-001/replay-report.json`.
This remains one service path and does not establish timeout behavior, CD
hardware timing or gameplay meaning.

The observer validator finds the root sequence by its observed source call and
following delay/entry events. The next instrumentation change arms transfer
recording only after that source call, so earlier unrelated bus events cannot
consume the fixed capacity; the 128-slot limit remains unchanged. A compiled
regression fixture checks that pre-call device reads and writes are omitted,
root transfers remain counted, and the existing overflow fence still rejects
the 129th uncompressible event. The focused command-observer suite passes (10
tests). At that point this source change had not yet been built into a matched
core or run against the original game.

Private evidence directory:
`/home/dev/neptune-research-private/707/original-command-abi2-windows-002`
and `.../original-command-abi2-windows-003`. The retrospective accepted trace
summary is `.../original-command-abi2-windows-002/profile1-enabled/retrospective-validation.json`;
the profile 2 overflow diagnostic is in `.../original-command-abi2-windows-003/profile2-enabled/failed-command-records.json`. The no-input scan is under
`/home/dev/neptune-research-private/707/original-command-idle-abi2-001`.

Runs used the shared host limit of 3, a 180-second gate lease, offline network
isolation, read-only original inputs and prepared core, no provider calls,
60-second per-command limits, nice 10 and a 2 GiB address-space cap. All leases
were released.

Next at that checkpoint: build and locally reuse the source-call-armed observer, rerun both profiles
with and without Start, preserve no-root/overflow diagnostics, then continue with
the distinct timeout/error branches and adjacent resident kernel functions.
Expand into other code-bearing modules afterward. The all-original-code
programme remains active and incomplete.

## Exact-head source-call gate execution

This follow-up supersedes the pending-build status above while retaining the
earlier overflow captures as diagnostics. Commit
`39ce8ace221d21a8e5cd937bf38e717ea68eaede` gates transfer capture until the
verified source call. Exact-head provisioning run `41665981073`, job
`126021492074`, built and smoked the separate matched core. The verified artifact
is `13244483723` (archive SHA256
`98af0769b66047c9dbdf7c715e44bbc8f094b2724390bbe136dc634d370aa686`); the
recipe SHA256 is `d9df493c790a8685d11ef89d7230d8e9d34e3576f0762cc953317b481d2ef7e5`
and native core SHA256 is
`0c44f52a40b1f9680034c0843e98faa9a6908caa6305fa191c8f3625709d5462`. Its
native smoke reports ABI 2, 288-byte records, 128 slots and 424 witness words.
A guarded local cache-only reuse succeeded with local compilation refused; its
report SHA256 is
`7c85077f28f38899523e07cd44beb801e4d25338df622f587728e8e6a2ece7ab`. The
accepted transfer receipt SHA256 is
`02861df99f7f522cd2853cc51714425520309ca74f846e5477f5b65f61a4ff03`.

Six fresh guarded 600-frame Start-pulse windows were run from frame 1800 with
this core. Profile 1 reference, disabled and enabled runs all match state
`207d3e58bbb24ad85791c131a91b3903ee0419242ff2988e446715fd0e252802`, video
`0939dcfcc86c6faae671b242573817477a7015acf574a5d829e5d1153fbe5e6e`, and audio
`eafc18cc2ff4305e000446326d97be2a3b884cf8b114ec1ecf794d626a3b393d`. Enabled
profile 1 accepted one complete natural root with 27 actual logical/stored
events, zero drops, and trace SHA256
`40bbd443fa20cb4fd4c2ac7650511e43651a44cda93b43b36d30a3dd20c111f1`. Profile
2 reference and disabled controls match those same output hashes; its enabled
window executed all 600 frames but had no source call or root (zero recorded
events, zero drops) and is rejected as an empty trace. This is now a no-root
result rather than the earlier buffer overflow. Full supervisor evidence:
`/home/dev/neptune-research-private/707/original-command-abi2-windows-005/supervisor.json`
(SHA256 `90f4b7b31934fd6fd21985bee782acdcdada3fd8bf980ed54f956a1647f4bd90`).

Six fresh 600-frame no-input windows were also run with the same exact core.
Within each profile, reference, disabled and enabled modes match. Profile 1's
enabled trace is empty and rejected (zero records, drops and transfers). Profile
2's enabled trace accepts one complete natural root with 27 events and no drops.
Both profiles' reference/disabled outputs match state
`97c9a1cbb7457b90d7064c9b8291f70959cb21cf5d87561a1737d7f850af08f4`, video
`fcc2a074c3341303a15a511b4fe3c09b2590559660711bca77df41a4d2d887b2`, and audio
`8798ce3b8ae561604beabb7aeaab788ec412db7fc7433e8534d94d99c88e4c85`. Full
supervisor evidence:
`/home/dev/neptune-research-private/707/original-command-idle-abi2-002/supervisor.json`
(SHA256 `7b9be640547f75e024187cfb72c90b38f3ad6fee84b274e805b3627a581603d6`).
Across the four enabled windows, no trace overflowed. The gate preserves natural
root evidence when a root occurs and leaves empty windows unaccepted. It does
not recover the command service timeout/error path or establish device timing
or gameplay semantics.

The runs used the existing Mednafen Saturn libretro reference and a separate
matched observer build from the same emulator lineage; no second emulator was
available locally as an independent oracle. These results provide
instrumented-versus-reference parity, not an independent emulator cross-check.

## Poll timeout source lead and bounded replay attempts

The natural wrapper input at `0x06095992` is now also used for bounded
counterfactual CPU replays of the timeout path. The first replay supplied eight
synthetic `0x0B84` no-ready words and failed when the original code requested a
ninth. A 32-word retry failed on request 33; a 36-word retry failed on request
37. The original SH-2 source was still inside its poll loop, and each failed
attempt, worker, stderr and supervisor receipt is retained under
`/home/dev/neptune-research-private/707/timeout-branch-replay-00{1,2,3}`.

The source bytes at `0x06095A84` load the loop limit from literal
`0x06095AF4`, whose original value is `0x00240000`, initialize the retry
counter, increment it for each no-ready result, and compare it to that limit.
The helper begins with its result register at `-3` and changes it on the
observed ready branch. This static source lead explains why a short injected
sequence does not reach the error exit. The full timeout path was not executed:
it would require 2,359,296 no-ready reads, beyond the retained 512-instruction
per-replay bound. These are synthetic response tests over original SH-2 bytes,
not a captured hardware timeout or proof of device timing. Continue first with
the natural success and error/caller-return dependencies around this helper;
do not present the counterfactual as a natural timeout result.

Continue from the retained `0x06095992`/`0x060959CA` natural service into the
distinct poll timeout/error and outer caller-return branches, then adjacent
resident kernel functions and other original code-bearing modules. Preserve all
empty/overflow diagnostics, owners and configured limits. The all-original-code
programme remains active and incomplete.
