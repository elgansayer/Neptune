# Bounded original Saturn kernel RNG draw

This is one CPU-only original-kernel slice toward issue #492. It does not close
RNG recovery, issue #492, or the all-original-code programme.

## Source and captured state

The source is the unchanged USA MK-81070 V1.003 `0KRNL.BIN`, SHA-256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`, mapped at
`0x06006000`. The bounded draw entry is `0x0600A0EC` (range through `0x0600A10C`,
SHA-256 `0c06dc97c0196171a1bdade84af11c63b459fd4259747fdbd88962905c4bc1c8`); it
calls the next-index helper at `0x0600A08C` (range through `0x0600A0B4`, SHA-256
`21e8bd6d7c0b4fe77ae5b53b1181df88a8b36e734db870edd5919395273f107f`). Both
ranges match in the original kernel file and the retained frame-1800 high Work
RAM. The same checkpoint independently matches the 64-byte residency witness at
`0x0600A4B0`.

The checkpoint is
`/home/dev/neptune-research-private/707/reference-window-frame1200-1800/capture/checkpoint.json`;
its state SHA-256 is
`54af2c95d530b7d34349406da8a37806d6472ac6caf27ac78b1b0ebc9fc4c799`. Its index
at `0x060BF4F4` is 55 and the word at `0x060BF5D4` is `0x000074E8`.

## Actual original-byte replay

With the captured index 55, the first direct call entered the original table-wrap
helper and did not return within the existing 512-instruction limit. The failed
report remains private at
`/home/dev/neptune-research-private/707/rng-entry-replay-001/report.json` (SHA-256
`47d01f738c2020cf03438800b50b4bc27a884fc524f088031f364bed0768b67f`). It is not
reported as a completed wrap.

For the non-wrap path, six fresh CPU instances used constructed `r4` bounds
`0, 1, 2, 10, 255, 256`, `r15=0x060FF000`, and a constructed predecessor index54
so the original helper advanced it to 55. Remaining high Work RAM, including the
selected table word, came from the retained checkpoint. The pinned
`saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9` interpreter executed 33
SH-2 instructions per case. Returns `0, 0, 1, 9, 231, 232` match the independent
calculation `((word & 0xff) * bound >> 8) & 0xff`. The index is the only lasting
RAM write; stack saves are restored.

A changed-shift control replaced original `shlr8` at `0x0600A102` with `shlr2`;
for bound 10 it returned 68 and failed the independent formula as intended. The
formal private report is
`/home/dev/neptune-research-private/707/rng-entry-replay-005/report.json` (SHA-256
`61f5b45039076bd9afa06d489c6e7c51fbe3e2c8fb4e060efd84fe695c58a02a`). The
versioned probe SHA-256 is
`2d2043f351cebb64b473ff8db65718fe3ee31842c399d7bcde7b88a1defa7b8d`.

## Reproduction and limits

Run from the repository root with the already supplied private originals and a
fresh report path:

```sh
python3 tools/saturn_lab/probe_kernel_rng.py \
  --kernel /home/dev/neptune-research-private/483/0KRNL.BIN \
  --checkpoint /home/dev/neptune-research-private/707/reference-window-frame1200-1800/capture/checkpoint.json \
  --saturn-recomp /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --report /home/dev/neptune-research-private/707/rng-entry-replay-NEW/report.json
python3 -m unittest tools.saturn_lab.tests.test_probe_kernel_rng -v
```

The probe verifies kernel, checkpoint, interpreter and resident-helper identities,
limits each call to 512 instructions, and guards writes to the declared index and
stack only. Three focused formula/input tests pass. The register ABI and index54
pre-wrap state are constructed, and the emulator lineage is not an independent
oracle. No natural RNG caller, call order, seed routine, complete recurrence,
wrap behavior or regional difference has been recovered. Next, capture a natural
`A0EC` call with its full register context under the existing observer/resource
gate; then resume the wrap helper in bounded checkpoints without increasing the
512-instruction limit.
