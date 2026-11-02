# Original NLSND initializer and command13 returns

This is one recovered dependency of [#665](https://github.com/elgansayer/Neptune-Bomberman/issues/665),
under #483/#488/#496. It extends the original command dispatcher and complete
returning scans, rather than replacing them. The other three control handlers
remain unresolved. [#666](https://github.com/elgansayer/Neptune-Bomberman/issues/666)
records an actual unsupported SCSP access. Neither issue is completed by this slice.

The [derived receipt](../evidence/2026-11-02-original-nlsnd-initializer.json)
records source/native identities, complete-domain digests, repeated report hashes,
controls and bounds. Original module bytes and complete private reports stay on
the research host.

## Recovered memory and return contract

The original USA MK-81070 V1.003 `NETLINK/SNDDRV.BIN` is23,920 bytes, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`.
This is the separate NLSND lifetime at sound-68000 load address zero. It is not
the common SND/XBSND driver or a SH-2 mapping.

The initializer at `[510E,51B2)` executes40 original instructions. It saves
D0-D7/A0-A6, reads its context pointer `p` from absolute longword0412, and writes
the following defaults. Offsets below are relative to `p`:

| Width | Destinations | Value |
| --- | --- | --- |
| Byte |08,09,0B,0C,0D,0E,10,11|00|
| Byte |0A,12|20|
| Word |2C,38|2000|
| Word |Every other even address28..54 inclusive|0000|

The probe checks the exact original ordering, not just the final bytes. Its word
writes visit offsets4E/50/52 before34 and visit54 before42. All other bytes in
the declared context/canary window remain unchanged. The meanings of these
fields and the natural0412 pointer domain remain unverified.

All15 saved registers are restored. RTS consumes the explicit outer return and
advances SP by four. The last zero word write leaves Z set and N/V/C clear;
MOVEM and RTS preserve those flags. X remains as it was on initializer entry.
Restoring a negative D0 does not recompute the flags from that restored value.

The command13 handler `[1E62,1E68)` actually calls510E and returns, for42
instructions. The full17F2 dispatcher path for byte13 executes55 instructions,
including its real indexed call, handler call, initializer and all three returns.
The caller's D7 index shift clears X, so this complete path returns with CCR04.
D7 retains its original upper halfword and low word004C; A4 retains the caller's
original A6. Outer A5/A6 are restored. The separately initialized0412 context
pointer deliberately differs from that caller A6 in every case.

Deepest stack use is60 bytes for direct initialization,64 through the handler,
and76 through the dispatcher. The complete declared stack/canary region is
compared, including saved words left behind after restoration. The pinned Musashi
MOVEM predecrement callbacks write each low word before its high word. All18
initialized visible registers, ordered reads/writes, PC paths, unaffected mapped
bytes and the complete original source buffer are checked.

## Original execution and controls

Two fresh guarded processes each pass12,800 cases:4,096 direct initializer,
4,096 handler and4,608 complete dispatcher calls. Each main run executes589,312
original instructions. These are instruction counts, not Saturn cycles or video
frames. The declared union covers all256 context seed bytes, two explicit context
addresses, four supervisor SR values, two register poison variants, all three call
profiles and additional D0 boundary words in the dispatcher profile. It is not
all machine states or naturally observed traffic.

Every case contributes its complete compared observations to the aggregate hash.
Fifteen full observations are retained in the bounded report. Both complete
reports are byte-identical, SHA256
`d43b844ae11136d90c125c1eecea977aa3f91025d2eea08468a37a2de0895201`;
the all-case observation digest is
`7a42b9bad208fd9c72d77adb1c8336d11608bf42d6e2bfe5c38a47c96e8c80cb`.

Each run executes three altered copies: byte default20 to21, word default2000
to2001, and word-destination displacement28 to2A. Each rejects48/48 selected
cases after reaching the terminal semantic comparison. A guard/budget failure
cannot qualify as a semantic rejection. No source original or reference fixture
is replaced. The eight new owned tests are tooling tests; the full320-test
research tooling suite passes separately from these real original executions.

The unchanged accepted ABI1 library is
`cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c`.
It uses the pinned Musashi source already prepared under #600. No new native
generation, emulator download or provider request is needed. The shared lineage
is not an independent emulator or hardware oracle. Actual read-only mounts,
network isolation and hidden broker/auth/authority paths pass their runtime
assertions. Guard identities remain private. Per process:512MiB address space,
45CPU/60wall seconds and4MiB output-file limit. The configured three-slot host
gate and180-second own lease are unchanged. Only the owned lease was released.

## Device boundary and continuation

A separate original command12 diagnostic executes34 instructions through
`17F2 -> 1E4C -> 4188 -> 41C8`, then the unchanged native memory guard rejects
a word write at100700. Its explicit result is `completed_original_call:false`.
This is a real unsupported-device boundary, not a passing handler. No SCSP
register is supplied as ordinary RAM. The decoded control10 path has further
calls requiring separate validation; control11 also has an unvalidated callee.

Keep #665/#666 and the all-code programme open. Validate applicable real SCSP
effects before completing device-bearing branches. No natural command, sound
event, DSP programme, sample timing, Godot parity, whole-module coverage or
continuous factory operation is claimed here. Preserve SH-2 observer660 and
Gemini487 ownership.

After the existing shared admission and guarded read-only setup, reproduce with
fresh report names:

```sh
python3 tools/saturn_lab/probe_netlink_initializer.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code600-001/prepared \
  --report /PRIVATE/NEW-initializer-run1.json
python3 -m unittest discover -s tools/saturn_lab/tests -p test_probe_netlink_initializer.py -v
```

Private execution and failure custody:
`neptune-research-private/665/initializer-001`,
`neptune-research-private/665/device-boundary-001`, and
`neptune-evidence/nlsnd-control-20261102`. The first static inspection waited in
one bounded admission request; it was not restarted during observation timeouts.
The initial owned test had an incorrect stack-address filter; it was corrected
before original execution, and its failed log remains. Actual account/CI spend
is unknown; tests/probes make zero model requests and no purchase, quota reset
or Neptune-continuity change is made.
