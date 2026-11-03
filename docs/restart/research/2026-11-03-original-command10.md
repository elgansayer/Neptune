# Original NLSND command10 composition

Issue686 continues665 with complete constructed1E68 and17F2 command10 contracts,
reusing qualified ABI8. Previous683 evidence established returning diagnostics,
not independently checked command semantics. This probe specifies descriptor,
channel, slot/reset and conditional volume operations independently and compares
the actual original instructions against that specification. No instruction
interpreter or candidate execution generates expected observations.

## Recovered composition

The USA1.003 NLSND container is23,920bytes, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`,
loaded at68000 address0 for the NetLink sound-driver lifetime. This is not a
SH-2 mapping or the common SND/XBSND lifetime.

The handler saves its incoming SR word, selects2700 for its body, and reads five
successive controls throughA0. Each triggers only for byte exactly1. The reads
are sequential and observe writes/clobbers from earlier operations.

| Control | Enabled operation |
| --- | --- |
| First |4412 clears eight96-byte descriptors, scanning32 active12-byte slots for each descriptor, emits matching four-byte queue records, clears descriptor fields and copies two bytes by tag through the separate404 global pointer.3540 sets all32 release bytes;3530 clears the16-byte low object. A0 is saved/restored around this group.|
| Second |Eight calls to1DEA examine paired channel flags. A negative byte clears bit7, clears a RAM channel field and writes its slot byte. The second byte can share a direct-return tail.|
| Third |Clears caller-relative slot lanes217/237; earlier groups can already have replacedA5.|
| Fourth |Resets send/volume slots and RAM volumes, all DSP program/MADRS/COEF/TEMP fields through accepted helpers, then calls1640.|
| Fifth |Clears16 volume slots and the16-byte RAM volume array. Its source address is the currentA0, not necessarily the supplied payload's fifth byte.|

Before the fourth read, A5/A6 are unconditionally set to100000/7000. The1640
gate byte atRAM+1832 decides whether that helper changesA0. With gate0 it reads
16 volumes startingRAM+187E, so the final control is atRAM+188E and A0 ends888F.
A nonzero gate retains the payload pointer. Therefore four external payload bytes
can suffice for a gate0 fourth-control call. A caller must not assume a five-byte
boolean packet. Aliases with RAM volumes, the low clear object and descriptors
are explicit cases and can change later controls.

The high-bit mode atRAM+1831 chooses direct orE0-masked volume stores. In this
command10 composition the previous volume reset has already cleared the16
source bytes. The test does not claim general standalone1640 input semantics.

The outer17F2 dispatcher retains its original indexed call, saves/restoresA5/A6,
initialisesA4 from the callerA6 and clearsCCR through its index arithmetic before
the handler savesSR. The first group can subsequently replaceA4 during pool setup. Handler SR restoration therefore differs from direct entry.
Slot helpers use MOVEQ and clear D7 upper bits; the DSP program helper's MOVE.W
has a different width contract. A real original comparison caught the initial
model's incorrect word-preservation assumption; its failure is retained.

## Declared comparison domain

The selection is a union, not the Cartesian product of every state. It includes
all32 old control masks, every byte value in each control with surrounding
controls0/1, four incomingSR patterns, two register/device seed variants, all256
redirect-control values, six input carriers, gate/sign cases and three valid
caller slot-base positions0/1/14. Six pool profiles exercise inactive, matching,
nonmatching and mixed slots, byte counter wrap, descriptor tags through255 and
negative/nonnegative channel flags. Globals450 and404 select shared or separate
pool/copy buffers, with untouched neighbours compared. Additional D0 word boundaries and valid
four-byte payloads are included. Natural input distributions remain unknown.

Each complete call must match all18 registers includingSR, every ordered RAM
and slot/DSP operand access, separate frozen-reference DSP word-bus events,
executedPCs and count, return addresses/stack contents, every mapped byte and
canary, all affected and untouched captured device fields, and immutable code.
No MMIO is supplied as ordinary RAM. Unsupported profiles retain ABI8 guards.
The reference-bus trace is emulator component order, not a physical bus timing
measurement. DSP execution and audio clocks are frozen.

## Actual original acceptance

Two fresh processes each pass9,476 complete calls:4,738 direct handler calls and
4,738 dispatcher calls. Direct entries execute21..4,414 instructions; caller
entries34..4,427. Maximum ordered data events are2,311, within the unchanged
4,096-event/8,192-instruction limits. Matching slot emissions range0..32.
The complete reports are byte-identical, SHA256
`ff200e74cb12059db4760091039a42aa59838bef4784fb99dbf9541ef5ceb505`. The all-case observation digest is
`7bf76d124a51e117ac6fc65b3a6941f751c80786a6a103f314be86c9181e8f97`.

Thirteen altered-original families run68 calls per process. Every altered call
reaches normal return and fails an independent observable comparison. Controls
change all five exact-one predicates, volume restoration, final pointer advance,
descriptor count, queue increment, slot-clear destination, tag scaling, the404
copy-global and SR restoration. A guard, timeout or early exception cannot qualify
as a successful semantic rejection.

The qualified executable source is`521501eaffb1fcaa184056d293e51250c8bda1f7`. The reused ABI8 binary
SHA256 is`82291cfcc35cbf6f24e326eb49f2fa01720e43bf62fc8c9a79ea89eb0e97e21f`.
The [derived receipt](../evidence/2026-11-03-original-command10.json) contains full
source/dependency/native identities, range digests, counts, small examples,
retained failures and supervision results. No previous native generation changes.

All five guarded child processes exit0, without cancellation, timeout, truncation
or surviving guardian. Original calls are bounded to512MiB address space,180s
CPU/210s wall and4MiB files per process. The one host lease is600s with shared
limit3 and guard5. Both filesystems retain their5GiB reserve. Tooling is separately
bounded to4GiB address space,150s CPU/90s wall, with fixtures in private tmpfs.
All409 research-tooling tests pass, including ten focused contract/guard/report
checks. These tests alone do not establish original or runtime acceptance.

## Operational boundary and remaining work

Run the probe with pinned private NLSND and the already qualified ABI8 directory
inside the existing supervised offline/read-only boundary. Reports require a new
mode0600 path. Original bytes/raw dumps remain private; public results contain
hashes, derived contracts and small observations only.

```sh
python3 tools/saturn_lab/probe_netlink_command10.py \
  --source-file "$NEPTUNE_NLSND_SOURCE" \
  --prepared "$NEPTUNE_ABI8_PREPARED" \
  --report "$NEPTUNE_PRIVATE_REPORT"
python3 tools/saturn_lab/check.py
```

Tooling tests are separate from actual original execution, emulator operation,
Godot native tests and factory health. No native generation, provider dispatch,
account/cap/circuit change, service restart or Neptune continuity is introduced.
Tests/probes request zero models; account/CI spending remains unknown.

Natural command traffic/roles/boot, hardware corroboration, sample-timed audio,
production-Godot campaign/battle/state/native pixels/PCM and whole-code function
or executable denominators remain open. Shared CPU/emulator lineage is not
independent hardware evidence. Preserve active669/Gemini487 and original media.
