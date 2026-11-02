# Original NetLink packed-byte writer

Issue [#604](https://github.com/elgansayer/Neptune-Bomberman/issues/604), under
#483/#488/#480/#464. Original sound68000 entry `0x4C2A` now passes **9,136
constructed cases twice**, with byte-identical reports, SHA256
`247a9cb596cb30e4e858dcc10e0d867215146b381cb5ab4089671fbc2bc2254d`.
This continues [the accepted record routines](2026-11-02-original-netlink-records.md).
It is isolated original-instruction evidence, not naturally observed sound commands.
The [derived receipt](../evidence/2026-11-02-original-netlink-command.json)
retains source/tool/range/report identities, case variants, paths and controls.

## Source and recovered byte contract

USA MK-81070 V1.003 original `NETLINK/SNDDRV.BIN`,23,920bytes, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`,
sound68000 candidate load0, NetLink sound-driver lifetime. Full original length/
hash is checked before execution. File/address extent `[0x4C2A,0x4C9A)` contains
the inspected routine. Other driver lifetimes and regional variants stay separate.

Let `s` be initial D0.low8, `p` initial D2.low8, `f` initial D3.low8,
`d` initial D1.low8, `tag = read8(A6+1)` and `b = read32(0x450)`:

```text
if (s & 0xF0) == 0x90:
    amount = read8(A6+0x22)
    if read8(A6) & 0x10: amount = read8(A6+0x24)
    p = max(0, p - amount)              # unsigned byte subtraction with underflow clamp
old = read8(b+0x1840)
write8(b+0x1840, (old+1) modulo256)
destination = b+0x1A00 + 4*old
write four bytes at destination:
    ((s >> 4) & 7), ((s & 15) | ((f << 4) & 255) | ((tag << 5) & 255)), d, p
```

The primary amount is read even when the alternate field is selected. The
counter is read twice in the pinned observer: once for the index, once for its
read-modify-write increment. Exactly four queue bytes are written in order; no
other counter slot or descriptor byte changes. Tests initialize only the pointer,
37 descriptor bytes, one counter byte, four selected output bytes and18 stack/
return bytes. Every unaffected mapped byte and full instruction buffer is checked.
No SCSP/device mapping exists. “Queue/command” describes the structure; actual
sound events, instrument meanings and consumer protocol remain unvalidated.

D0.low8 becomes `s & 0xF0`, D2.low8 becomes the adjusted byte, D3.low8 becomes
`(f << 4) & 255`; their upper24bits are preserved. A0=b, A1=b+1840 and A2 points
just past the four output bytes. D1,D4-D7,A3-A6 are preserved for the initialized
states. RTS increases SP by4 and reaches the explicit sentinel. D5-D7 are saved/
restored in12 stack bytes; SR has its own halfword slot.

Returned SR is `(initial_SR & ~0x1F) | 4 | (16 if tag & 8 else 0)` in these
supervisor states. The routine saves SR after CLR.L D7, retaining the preceding
tag shift's X bit, then masks interrupts while writing. Restoring that saved SR
differs from preserving the incoming CCR. Both X states, initial masks/flags and
the zero/clamped payload paths are exercised. Exact accesses, visible registers,
stack contents, return and executed PCs are compared to a separate scalar/byte
contract. Calls execute32,37,38 or39 original instructions including all branches.
Model cycles are in the receipt; they are not measured Saturn or audio timing.

## Cases and actual controls

The union contains every status byte0..255 at counter0/1/127/255, and every
counter byte0..255 for statuses0F/80/90/9F/FF, each under four declared variants.
Duplicates are removed, yielding9,136 cases. Variants exercise primary/alternate
amount selection, borrow/equality/positive subtraction, zero/high payload bits,
packed bit overlap, both tag-X states, differing upper-register bits, four SR
states and two base pointers. This is not all possible byte/register/memory
combinations or a measured gameplay input domain.

| Altered original instruction | Rejected /48 cases |
| --- | --- |
| remove subtraction underflow clear | 8 |
| remove counter increment | 48 |
| narrow group mask7 to3 | 24 |
| remove tag-bit OR | 12 |

These changes fail actual register or output-byte comparisons; unchanged-result
cases stay recorded. Mutations alter private copies only. No expected bytes,
mapped bounds or tolerances were weakened. All four controls distinguish wrong
behavior using the same pinned CPU lineage, not independent hardware.

Actual private reports: `/home/dev/neptune-research-private/604/nlsnd-command-001/`.
Supervisors/scripts/logs: `/home/dev/neptune-evidence/code604-20261102/`.
Execution head `90ba548e115789d98f8169e4ba1a7cf4dd7af0bf`, intake base
`ba2933314b7a9434c0e21f008853782d5fec5f18`. The accepted prepared binary
`cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c` was
reused unchanged; no build/new emulator is claimed. Each call is bounded to64
instructions and the original native layout remains256 instructions/128 events.
Read-only source/prepared and hidden-broker assertions passed. Both original runs
finished within60-second command deadlines under existing host admission, observed
shared limit3 unchanged. Own leases were released. No provider job, scheduler,
allowance, paid fallback or other owner changes; account/CI spend remains unknown.

Six synthetic contract/selection/failure tests and all188 input-tooling tests
passed. They do not replace original execution or prove natural sound/SCSP/DSP,
self-modification, hardware timing, other modules or whole-program completeness.
Exact-head/current-base CI remains the publication gate.

Repeat twice after existing admission with fresh report names and compare files:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_netlink_command.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code600-001/prepared \
  --report /home/dev/neptune-research-private/604/NEW-command-run1.json
python3 tools/saturn_lab/check.py
```

Next is the full32-record caller at4B1C, including32 active matching records and
optional flag clearing. Static bounds predict up to1,572 instructions and967
observer events: this exceeds the accepted short-call layout. Preserve that
accepted generation and prepare a separate explicit longer-call profile with its
own ABI/bounds/synthetic overflow tests; do not pass a smaller consumer subset as
full recovery. Natural sound use and other-code/function denominators remain open.
