# Original NLSND reset marker gate and register handoff

Issue #694 continues #665 with the USA NLSND phase from `0x1000` to `0x1080`.
This is a bounded conditional handoff, not a returning routine or complete boot.
The qualified executable head is `9b0e9f7a4db6492d50042676b518943e745a18de`.

The pinned USA MK-81070 V1.003 NetLink sound-driver image is 23,920 bytes,
SHA256 `f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`,
mapped at 68000 address zero for this load lifetime. It is distinct from the
SND/XBSND and SH-2 mappings. Its reset vector points to `0x1000` with SP `0xA000`.

## Recovered phase

Entry selects SR `0x2700`, compares the longword at `0x5D6C` with `0x53454741`
(`SEGA`), and returns to entry while unequal. In the declared memory view, this
matches a wait for the image-tail marker. The natural loading protocol and marker
write/visibility transitions have not been observed.

On equality, the phase clears D0..D7 and A0..A4, sets A5 to `0x100000`, A6 to
`0x7000` and A7 to `0xA000`, and transfers to `0x1080` with SR `0x2704`.
The clear sequence branches over embedded data at `0x1020..0x105F`; only
`[0x1000,0x1020)` and `[0x1060,0x1080)` are executable in this experiment.
There is one marker read, no stack access, no writes and no SCSP/DSP bus access.
The later instructions at `0x1080` are outside the accepted phase.

The source image also contains globals `0x404 -> 0x700`, `0x412 -> 0x480` and
`0x450 -> 0x7000`. These are static image values, not proof that they retain those
values in a natural runtime. In particular, the `0x404 + 0x80` copy-table address
aliases the previously recovered low `0x780` clear object, and the `0x450` pool
base shares the reset helpers' `0x7000` RAM area. Their initialization, lifetimes,
relocation and actual callers require further experiments. The earlier #686
constructed pool/layout domains remain limited to their documented selections.

## Independent contract and actual original execution

The independently written model declares every byte variation at each of four
marker positions plus zero, all-one and sign edges: 1,025 distinct tags. Combined
with four SR patterns and two poisoned register/SP/device variants, the union
contains 8,200 cases. The marker region is an explicit read-only constructed RAM
view; the source code bytes remain unchanged. Every case compares all 18 final
registers, SR, exact ordered PCs/counts and data accesses, mapped bytes/canaries,
unchanged original code, the full captured untouched device state and empty
reference bus trace. Expected values are not obtained from candidate execution.

Two fresh processes each pass all 8,200 cases:

- Eight matching-tag cases reach the declared handoff after 22 instructions.
- 8,192 wrong-tag cases stop at the 63-instruction budget after 21 complete wait
  loops, preserving D/A registers and comparing the final CMP flags. They are
  explicitly unfinished waits, never accepted completed reset/boot calls.

Both reports are byte-identical, SHA256
`b2f5c2a26755f3dfa6ff79142bcf308b469d03e0e35a7e2aaaa3036f172d2f69`.
The all-case observation digest is
`e7d7690cb951f9bbc7e543c66980d19ceb8a69dc3d81f8be2c8a487bce15ede1`.
Observed interpreter counts of 154 and 1,134 model cycles are recorded as
CPU-model diagnostics; they are not Saturn hardware or sample-timing evidence.

Six altered-original families each run all eight matching-tag variants: wrong
D0 seed, omitted D2 clear, skipped D7 clear, wrong RAM base, wrong SP base and
wrong SCSP base. All 48 mutated calls reach the same normal `0x1080` handoff and
fail the independent register comparison. A guard/budget failure cannot qualify
as a semantic rejection. Separately, a wrong branch into `0x1022` executes the
expected 11-instruction prefix and hits the fetch guard. That diagnostic is not
counted among completed handoffs or the 48 semantic controls.

The qualified ABI8 binary is unchanged, SHA256
`82291cfcc35cbf6f24e326eb49f2fa01720e43bf62fc8c9a79ea89eb0e97e21f`.
The [derived receipt](../evidence/2026-11-03-original-boot-gate.json) records its
complete identity chain, 28 source/dependency hashes, range digests, controls,
small positive observation, retained failures and actual supervision outcomes.

## Reproduce and operational boundary

```sh
python3 tools/saturn_lab/probe_netlink_boot_gate.py \
  --source-file "$NEPTUNE_NLSND_SOURCE" \
  --prepared "$NEPTUNE_ABI8_PREPARED" \
  --report "$NEPTUNE_PRIVATE_REPORT"
python3 tools/saturn_lab/check.py
```

Use the existing offline supervised boundary and a fresh private report path.
The actual five child phases all exited zero with no timeout, cancellation,
truncation or surviving guardian: isolation check, prepared-library feature smoke,
437 tooling tests and two original comparisons. Six focused contract tests are
included in that tooling suite. Tooling tests are not an emulator, game or factory
health check and do not independently establish original execution or fidelity.

Original comparisons are bounded to 63 instructions per case, 512 MiB address
space, 180 CPU seconds, 210 wall seconds and 4 MiB files per process. The shared
host lease is 600 seconds at limit three, with a five-second process guard.
Source, original input and prepared native files are mounted read-only; only
loopback networking exists and broker/auth/signing authority paths are hidden.
Both filesystems retain the unchanged 5 GiB reserve. Prepared ABI8 is reused with
no compiler or preparation phase; outputs are root-local and the secondary
scratch estimate is eight MiB. Tooling fixtures use private tmpfs with separate
4 GiB address-space, 150 CPU/90 wall-second and 2 GiB file limits.

The initial host attempt failed disk reserve before any child. An unstarted
second attempt was cancelled only after required CI established a stale base;
current main was integrated before the successful third attempt. All failed and
cancelled receipts remain private. No other agent lease or work was cleared.
Original media/raw dumps stay private. Tests/probes made zero model requests;
account/CI spending is unknown. No new native generation, provider allowance,
service restart, scheduler or Neptune continuity is introduced.

Natural boot/loading transitions, the remaining reset body and header-global
lifetimes, hardware corroboration, DSP execution and timed audio, production-Godot
campaign/battle/state/native-pixel/PCM comparisons and whole-code denominators
remain open. The installed factory transport proof under #536 is separate;
manual account enrolment and actual in-flight issue restart recovery remain open.
