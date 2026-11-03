# Original NLSND fixed-data clear at0780

[#682](https://github.com/elgansayer/Neptune-Bomberman/issues/682) qualifies one
constructed original helper,3530..3540, in the pinned USA MK81070 V1.003 NLSND
sound68000 lifetime. [Derived evidence](../evidence/2026-11-03-original-low-reset.json)
binds the source, native tool, static inspection and repeated original reports.
Parent665 remains open; no natural execution or complete command10 claim follows.

## Why this bounded data region is declared

The complete23,920-byte NLSND source is checked against its accepted SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296` before any
native library is loaded. Its vectors identify reset1000 and exception entries
154A/17C4/17CE/17D8/17E0/17E8. Reset1000 waits on a source signature, initialises
registers and establishes A6=7000, SP=A000 and the SCSP base A5=100000. Static
global traversal and the independently selected1E68 handler traversal do not
overlap0780..078F. Those16 initial source bytes are zero. Neither absence from a
traversal nor zero bytes alone establishes data.

The positive evidence is two separate direct writers:3530 explicitly loads
A0=0780 and issues four postincrement longword zero writes; the reset-like19D8
path independently repeats that exact clear at19FA..1A06 between state save and
restore. The latter first calls34A4/35DE. No natural reset/boot/caller experiment
is claimed: the19D8 interpretation is a static lead. Linear disassembly of the
unused low range or embedded text is not classified as executable code.

Together these direct operands justify a narrowly declared writable object for
the constructed clear/command experiment in this exact module. They do not
prove the region's natural meaning, global exclusive data lifetime, absence of
dynamic code, or applicability to SND/XBSND/SH-2. Those modules retain separate
identities and lifetimes. The harness still rejects data overlays overlapping
declared executable ranges and verifies the entire original code buffer unchanged.
Sixteen-byte canaries on each side are compared, not assigned new semantics.

## Complete helper contract

Seven original instructions set D0=0, set A0=0780, write zero longs in order at
0780/0784/0788/078C, then RTS through the original caller stack. A0 ends0790.
All other D/A registers are preserved apart from SP advancing4. SR retains X and
upper bits; Z is set and N/V/C clear. The comparison checks all18 visible register
values, exact PCs/instruction count, every data transaction, all declared RAM and
stack bytes, neighbouring canaries and the complete unchanged frozen device state.
The model reports76 cycles; this is not measured hardware or sample timing.

The294-case selection includes every byte seed, five wider seed boundaries,
four initial SRs and two register variants. Two fresh processes produce identical
complete reports, SHA256
`24f1fd340cfa24478ff31bc4d0e352d30dca429df561d245b88f0427815135b1`.
Changed zero value, omitted final write and shifted destination controls each
return normally and fail4/4 comparisons:12 terminal mutation rejections total.
Early guards are rejected rather than counted as semantic controls.

## Guarded command10 continuation

The existing128 input scenarios are factored into a shared generator without
changing their contents. Re-executing the complete prior680 probe reproduces its
accepted report exactly except for the changed wrapper-source hash. Its639 helper
cases,24 controls and all prior command10 outcomes remain identical.

Adding only the declared low region to the new diagnostic preserves64 existing
outcomes exactly and extends all64 low-write prefixes. It yields64 diagnostic
returns and64 explicit longword-write guards at100800, original35B4. All low
neighbours and original code bytes remain unchanged. A newly returning scenario
does not establish an independent complete command10 contract. DSP longword/TEMP
semantics remain [#683](https://github.com/elgansayer/Neptune-Bomberman/issues/683).

## Execution and limits

ABIs1..7 and all preparation identities/caches remain unchanged. Original runs
reuse the previously qualified ABI7 binary
`597e2c4a3a74ab6af4f06a1c9784dc24f1ed10e577edf5708baf7ff3dbc82364`;
no new device profile or dependency is introduced. The frozen native component
does not execute DSP, key/envelope clocks or audio.

Source-qualified implementation head is
`1f574fe20562687447b764b03fdb6943c58b4f5f`. Private evidence is under
`/home/dev/neptune-research-private/682/original-003/`, with supervisor, logs,
baseline and both fresh reports; static leads are in `static-002/`. Source,
input and native tools are read-only; only loopback exists; broker, credentials,
signing authority and container sockets are hidden. Actual shared limit3,
lease300s and guard5s remain. Helper calls have16 instructions, command10 has8192;
original children have512MiB address space,40s CPU,45s wall and4MiB file limits.
All accepted guardians are terminal; no cancellation, timeout or truncation.

The384 research-tooling tests pass separately from emulator/game/factory health.
Retained failures include a secondary-disk preflight with no child and a cancelled
tooling attempt whose130MiB synthetic media-copy fixture crossed the root reserve.
The successful run's requested external TMPDIR is masked by the existing sandbox;
a separate actual namespace probe confirms Python falls back to private tmpfs
`/tmp`. Its4GiB tooling address-space/150s CPU/90s wall limits remain unchanged.
Do not describe the unused external directory as observed disk-backed scratch.
Both host filesystems retain5GiB reserves. Duplicate tracked addon copies in three
inactive owned historical checkouts were reversibly omitted with complete manifests;
branches, Git objects, prepared binaries and private inputs/captures remain.

```sh
python3 tools/saturn_lab/probe_netlink_low_reset.py \
  --source-file "$NEPTUNE_NLSND_SOURCE" \
  --prepared "$NEPTUNE_ABI7_PREPARED" \
  --report "$NEPTUNE_NEW_PRIVATE_REPORT"
python3 tools/saturn_lab/check.py
```

Run original commands through existing shared admission and the offline runner,
not an unguarded shell. Test model requests0; account/review/CI spend unknown.
No provider policy, quota, service, scheduler or continuity changed. Preserve669
and Gemini487. Natural callers, timing, PCM, production Godot state/pixel/audio,
campaign/battle parity and the whole-original-code denominator remain open.
