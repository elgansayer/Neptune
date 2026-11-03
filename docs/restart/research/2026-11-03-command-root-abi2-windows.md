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
1,811 transfers observed and one dropped record. It remains rejected. The cap
was not increased; the overflow evidence is retained for future instrumentation
work.

The natural trace also captures the wrapper at `0x06095992`, which calls
`0x060959CA` from `0x060959AA` and resumes at `0x060959AE`. Original bytes and
the captured SR values support the bounded interpretation that it saves PR
and the previous interrupt-priority nibble, raises the priority to `0xF` while
the nested service runs (`SR 0x0101` to `0x01F1`), then restores the saved
priority before returning. It is a static interpretation corroborated by
natural execution events, not a standalone wrapper replay. The evidence is at
`/home/dev/neptune-research-private/707/wrapper-recovery-001/report.json`.

A second CPU-only replay of original function `0x060959CA` used the captured
natural registers and stack, status `0x0BC5`, seven `0x0B84` polls then `0x0B85`,
and register words `0x0380, 0x4101, 0x0100, 0x367A`. It executed 171 original
SH-2 instructions, returned to `0x060959AE` with `R0=0`, reproduced all 13
device reads and five writes, and changed the captured global word from
`0x0FD4` to `0x0F94`. The four-word write buffer was reconstructed from the
observed device writes. The report is
`/home/dev/neptune-research-private/707/wrapper-recovery-001/replay-report.json`.
This remains one service path and does not establish timeout behavior, CD
hardware timing, complete outer-root semantics or gameplay meaning.

The observer validator now finds the root sequence by its observed source call
and following delay/entry events, allowing unrelated bus events earlier in the
same frame while still requiring transfers inside the root. A compiled
regression fixture covers leading unrelated transfers. Focused command-observer
tests pass (10 tests).

Private evidence directory:
`/home/dev/neptune-research-private/707/original-command-abi2-windows-002`
and `.../original-command-abi2-windows-003`. The retrospective accepted trace
summary is `.../original-command-abi2-windows-002/profile1-enabled/retrospective-validation.json`;
the profile 2 overflow diagnostic is in `.../original-command-abi2-windows-003/profile2-enabled/failed-command-records.json`.

Runs used the shared host limit of 3, a 180-second gate lease, offline network
isolation, read-only original inputs and prepared core, no provider calls,
60-second per-command limits, nice 10 and a 2 GiB address-space cap. All leases
were released.

Next: continue with the distinct timeout/error branches and adjacent resident
kernel functions, then expand into other code-bearing modules. The all-original-
code programme remains active and incomplete.
