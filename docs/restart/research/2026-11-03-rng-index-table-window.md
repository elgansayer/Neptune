# Original kernel RNG table selections for captured indices 0–54

This is a bounded continuation of issue #492 and
[the table-refresh result](2026-11-03-rng-wrap-refresh.md). The earlier result
covers the index-55 refresh path. This result covers the other 55 table slots in
the same captured frame-1800 USA state. It does not recover natural call order,
seeding, the complete RNG, timing, or the all-original-code programme.

## Original bytes and state

The source is the unchanged USA MK-81070 V1.003 `0KRNL.BIN`, SHA-256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`, mapped
at `0x06006000`. The original frame-1800 checkpoint is
`/home/dev/neptune-research-private/707/reference-window-frame1200-1800/capture/checkpoint.json`;
its state SHA-256 is
`54af2c95d530b7d34349406da8a37806d6472ac6caf27ac78b1b0ebc9fc4c799`. Its
captured index is 55. Each independent CPU case constructs one index value
from 0 through 54; all table words and other WorkRAM bytes come from that
checkpoint. Kernel bytes for the bounded draw, next-index helper and 64-byte
residency witness match the original file.

## Original-byte execution

[probe_kernel_rng_indices.py](../../../tools/saturn_lab/probe_kernel_rng_indices.py)
executes the original `0x0600A0EC` draw and nested `0x0600A08C` helper with
`r4=10`, `r15=0x060FF000`, one fresh CPU for each index, and a 512-instruction
limit per call. It guards writes to the index and stack; table reads use only
captured original WorkRAM. The pinned `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`
interpreter verifies all three source hashes before loading.

Two separately gated, offline runs each executed all 55 cases. Every call took
33 original SH-2 instructions; each advanced the index from `i` to `i+1` and
returned the value computed from the captured table slot `i+1`. All 55 returns
matched the independent formula `((word & 0xff) * 10 >> 8) & 0xff`. A changed
instruction control replaced original `shlr8` at `0x0600A102` with `shlr2` for
index 54; it returned a different value and was rejected. The two complete JSON
reports are byte-identical.

- `/home/dev/neptune-research-private/707/rng-indices-formal-002/report.json`, SHA-256 `7bebb10d0096a8c30752b2c996854dfe601a5f114aafc9960517deff64f3ea39`
- `/home/dev/neptune-research-private/707/rng-indices-formal-003/report.json`, SHA-256 `7bebb10d0096a8c30752b2c996854dfe601a5f114aafc9960517deff64f3ea39`
- Versioned probe SHA-256 `4cac8220757f8d36f3ea77fd9e066568f137f6fddf7c7d60018fff5a78c6e94f`

A first guarded setup failed before original execution because isolated Python
did not include the research-tools directory on `sys.path`; its receipt remains
at `/home/dev/neptune-research-private/707/rng-indices-formal-001/`. The versioned
probe now adds its own directory explicitly.

## Limits and continuation

These are constructed independent index inputs against one actual USA table
snapshot. They do not establish that gameplay visits indices in this order, how
the table was seeded or refreshed before frame 1800, any natural call site, or
regional/release behavior. The negative control verifies the previously
recovered shift for one selected case; it is not hardware validation.

Next, observe the natural `0x0600A0EC` call site with a target-specific native
source-call observer. Existing observers cover `0x0600B934` and the command
service root, not this RNG entry. Then continue through seed initialization,
other kernel helpers, gameplay modules, sound drivers, overlays, boot code and
all remaining original code; issue #492 and the parent programme remain open.

## Reproduction

Run the probe under the configured host gate and offline namespace, using a
fresh private output directory for each independent run. The guarded supervisor
used for the retained reports is
`/home/dev/neptune-evidence/code707-20261103/run-rng-indices-formal.py`:

```sh
timeout 60s nice -n 10 /usr/bin/unshare --user --map-root-user --net \
  /home/dev/hellotalk/automation/.venv/bin/python \
  /home/dev/neptune-evidence/code707-20261103/run-rng-indices-formal.py \
  --output rng-indices-formal-NEW
```
