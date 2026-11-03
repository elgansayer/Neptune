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

Profile 1's enabled run executed all 600 original frames and collected 1,774
logical events in 102 stored records with no drops. Its first validation was
rejected because older assumptions required source-call records at buffer
index zero and required two service PCs absent from this natural path. The
retained record diagnostic was revalidated after correcting those assumptions:
the source call, delay slot, root entry, observed command service calls,
transfers, root RTS/delay and return continuity all pass. This establishes one
bounded natural root trace; it does not assign device or gameplay semantics.

Profile 2's enabled run also executed all 600 original frames, but exceeded the
fixed 128-slot storage capacity: 1,810 logical events, 128 stored records,
1,811 transfers observed and one dropped record. It remains rejected. The cap
was not increased; the overflow evidence is retained for future instrumentation
work.

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

Next: build and locally reuse the updated recipe identity, rerun the corrected
profile 1 enabled trace directly, then trace other kernel functions and the
timeout/error branches. The all-original-code programme remains active and
incomplete.
