# VPS code600 continuation checkpoint

The all-original-code goal remains active and incomplete. This records the first
original 68000 execution slice, extending the accepted code591/594/596 record.
See [the full result](../research/2026-11-02-original-netlink-m68k.md) and
[derived receipt](../evidence/2026-11-02-original-netlink-m68k.json).

Owner: existing Codex app session, issue600; isolated workspace
`/home/dev/neptune-code-recovery-20261102`, branch `research/saturn-m68k-leaf-600`,
intake base `be254b056bedacee086d84dd4b36ba25bbe7d631`. Preparation/leaf source
head `173bef4caf2bf12b95f67b962e40fbbcf13681c4`; dispatch source head
`9f792b88c70afec360fc8ad7f317ebc4d4501e99`. Reconcile actual PR/check/main
state before a new claim; do not reset this or any existing checkout.

Module: USA MK-81070 V1.003 original `NETLINK/SNDDRV.BIN`, sound68000 mapping0,
NetLink sound-driver lifetime, SHA256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`.
The full original is already extracted privately and is rehashed by both CLIs.
Do not ask for the supplied discs or redo the completed FILM extraction.

Actual bounded jobs passed:

- Preparation and reuse, with all19 Musashi source pins, source-only isolation,
  2GiB address-space cap, native ABI/positive/loop/read/write/PC controls. Prepared
  generation `.factory-tools/code600-001/prepared`, library SHA256
  `cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c`.
- Original helper4B00..4B1C, two88-case runs, seven instructions/call, exact
  pointer/return reads, zero writes, A2/SR/other-register preservation, three
  rejected altered-original controls. Reports
  `/home/dev/neptune-research-private/600/nlsnd-leaf-001/`.
- Five original wrappers through4104/4B00/4108 to4122, two2,560-case runs,
  20instructions/path, exact bounded stack/tag effects, final registers/CCR and
  indirect targets, stop before handlers, three rejected instruction controls.
  Reports `/home/dev/neptune-research-private/600/nlsnd-dispatch-001/`.
- Eleven new synthetic wrapper tests; full177-test input suite; owned C backend
  warning-as-error syntax check. These tests alone are not original CPU evidence.

Every completed host supervisor released its own lease. Configured host shared
limit was read as3, unchanged; no foreign lease/provider admission was changed.
No new provider/model session, paid fallback, scheduler or continuity was enabled.
Preserve the other VPS coordinator's active #597 SH2 core/trace work and
Gemini/Antigravity#487. #536 manual-session continuity stays open; account/CI
spend remains unknown. Originals and prepared sources were read-only during
experiments, broker authority hidden. Runtime/hardware/SCSP/DSP/audio parity and
whole-program/function/dynamic-target denominators remain unknown.

## Exact next runnable command

The next selected code ranges have a prepared read-only source inspector:

```sh
timeout 60s nice -n 10 python3 \
  /home/dev/neptune-evidence/code600-20261102/inspect-next-queue.py
```

Its prior selected output is private
`/home/dev/neptune-research-private/600/next-queue-static-leads.json`.
Next derive/test the actual contracts at4BB6..4BE0 and4BE0..4C2A with the accepted
prepared CPU adapter. These are static leads, not recovered/executed routines yet:

- 4BB6 saves D0-D2/A0, reads pointer404 and record bytes at A6+1/+2/+3, then writes
  two bytes at the indexed pointer+80 destination. Derive exact indexed width,
  register/SR effects, stack reads/writes and unchanged bytes before execution.
- 4BE0 scans at most32 twelve-byte records using bit7, conditionally writes a
  selected record and restores saved D7/A5. Its explicit SR writes/restores may
  change caller state: derive and test the observed original behavior instead of
  assuming CCR preservation or a carry return. Natural queue/channel/voice role
  is still a hypothesis. No device RAM should be needed for those declared slots.

Check live ownership/PRs, create a bounded issue, use existing host admission and
fresh reports, run twice plus relevant mutations, then commit/push and use the
exact-head/current-base gate. Continue natural sound-handler/SCSP work, static
conflicts, SH2 gameplay/RNG/scheduler/loader and other modules after each slice.
Never mark #464/#477/#515 complete from these bounded results.
