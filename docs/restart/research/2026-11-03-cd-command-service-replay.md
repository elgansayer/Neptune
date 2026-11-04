# CD command service CPU replay

**Scope:** one captured USA MK-81070 V1.003 SH-2 command-service path. This is
original-byte CPU execution, not a CD hardware model or a complete natural
service root.

The private frame-1800 checkpoint and subsequent actual transfer trace supplied
one input path. A guarded replay executed171 instructions beginning at`060959CA`,
returned to captured caller PC`060959AE`, and returned`R0=0`. The input global
word at`060FA8B8` was`0FD4`; this path left it at`0F94`. The replay consumed the
recorded status word`0FC5`, eight poll values`0F84`×7 then`0F85`, and register
words`0380, 4101, 0100, 3679`. It reproduced five actual device writes in order:
`FFBE` to`25890008`, then`3000, 0000, FF00, 0000` to`25890018/1C/20/24`.

The trace labels two RTS-delay-slot transfers at the preceding RTS instruction
PCs`06095906` and`06095ACA`; the pinned CPU executes those stores at`06095908`
and`06095ACC`. The private report retains both views.

The packet buffer was reconstructed from its four observed device writes. The
saved caller`R12` and`R14` were seeded as preservation canaries because their
natural pre-call values were not present in the selected capture. Consequently,
this replay establishes the original function's bounded behavior for that
captured path, including its return and transfer order, but not natural buffer
construction, timeout/error coverage, the complete outer command root, CD
hardware timing, or gameplay meaning.

Private execution report:
`/home/dev/neptune-research-private/707/cd-service-replay-001/report.json`
(SHA256`b6c09a61b08cb59887e4c91d9e9f2a23565d719adc3d60ef29524851e12c0979`).
The underlying captured state and transfer diagnostic remain private and are
identified by hashes in that report. The isolated supervisor used the shared3
gate, a180-second lease, a60-second command limit, nice10, a2GiB address-space
limit, offline networking, read-only original/source inputs, and hidden broker
credentials. The lease was released and provider calls remained zero.

The all-original-code programme remains active and incomplete. Next recover the
distinct timeout/error and outer-return paths, then continue into other kernel
functions and modules.
