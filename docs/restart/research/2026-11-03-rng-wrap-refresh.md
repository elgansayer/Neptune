# Original kernel RNG table refresh at index 55

This is a bounded continuation of issue #492 and the earlier
[bounded-draw result](2026-11-03-rng-bounded-draw.md). It does not complete RNG,
task timing, any whole module, or the all-original-code programme.

## Original bytes and captured state

The source is the unchanged USA MK-81070 V1.003 `0KRNL.BIN`, SHA-256
`20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7`, mapped
at `0x06006000`. The captured input is the existing frame-1800 checkpoint at
`/home/dev/neptune-research-private/707/reference-window-frame1200-1800/capture/checkpoint.json`;
its state SHA-256 is
`54af2c95d530b7d34349406da8a37806d6472ac6caf27ac78b1b0ebc9fc4c799`. It
contains RNG index 55 and selected word `0x000074E8`. The checkpoint-resident
code matches the original kernel for the bounded draw, next-index helper,
refresh routine, and 64-byte residency witness.

The verified kernel-code and residency ranges were:

| Range, end exclusive | SHA-256 | Role in this replay |
| --- | --- | --- |
| `0x0600A0EC..0x0600A10E` | `de2d869392e860a358346b973f43e40070cc2ba7b6a7b0c0ecc2beada6d5afd4` | Bounded draw |
| `0x0600A08C..0x0600A0B4` | `21e8bd6d7c0b4fe77ae5b53b1181df88a8b36e734db870edd5919395273f107f` | Index and table lookup |
| `0x06009FA8..0x0600A08C` | `6e422fa2ee0227f82e1bdfacbe3facc173cbe757de7b406840c30cebfcb434b8` | Table refresh path |
| `0x0600A4B0..0x0600A4F0` | `4094a11659922a5ec8fc72a346db13f94b656df341fe426412ddae81fae01c21` | Residency witness |

## Actual original-byte execution

The versioned probe is [probe_kernel_rng_wrap.py](../../../tools/saturn_lab/probe_kernel_rng_wrap.py).
It invokes the pinned `saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`
interpreter, verifies its three source hashes, loads the captured WorkRAM, and
guards writes to the index, 55 table words, and the declared stack window. Any
other write or uninspected instruction address stops the call. Each invocation
executes at most 512 SH-2 instructions, counting delay slots, then writes a CPU
and WorkRAM resume checkpoint.

For two fresh report pairs, the original code completed in two separately
gated windows: 512 instructions followed by 349. The constructed inputs were
`r4=10` and `r15=0x060FF000`; the starting RNG index 55 and all other WorkRAM
came from the actual checkpoint. Both independent runs returned `r0=7`, reset
the index to 1, and produced table entry 1 `0x000051C1`. The independent
bounded-draw calculation `((0xC1 * 10) >> 8) & 0xff` also returns 7. Each run
recorded 65 writes: two index stores, 55 table stores, and eight stack stores.
No write escaped those regions. The final WorkRAM snapshots match exactly.

Formal private reports:

- `/home/dev/neptune-research-private/707/rng-wrap-formal-006/report.json`, SHA-256 `7dcefca480602a897edc922f57b78a567b1d92777c68022564f30cbb9734ca52`
- `/home/dev/neptune-research-private/707/rng-wrap-formal-007/report.json`, SHA-256 `ca4ad5e489403a53cba9e6dfcc97962d182e51202a113f8cbe31b2b3af40faf9`
- Both final `ram.bin` snapshots: SHA-256 `56802e9f9e21f948bab28dfc17f10e60982939826a4a29fdb1795b461385e595`

The replay ran through the existing shared host gate, offline loopback-only
network namespace, and read-only original/tool mounts. Each window ran in a
separate guarded worker process. An initial diagnostic counted 512 `step()` calls but actually executed 584
instructions because delay slots were not included; it is retained separately
and excluded from the result. The versioned probe fixes the count and stops
before a delay-slot instruction would cross the 512-instruction boundary. The
corrected probe SHA-256 is
`d852ebde53cc5a132c0fddf8bf284cb180795c074cac78c3202307d4c0e777be`.

## Scope limits and next work

This recovers one complete index-55 refresh-and-draw path for one captured USA
state. The bound and stack are constructed; no natural caller was observed.
It does not identify the seed source, explain why the captured table had its
initial contents, recover all index paths or call ordering, or compare releases
and regions. The interpreter is not an independent hardware oracle. A separate 600-frame original-core title-screen input window started from
frame 1800 and delivered an eight-frame Start pulse on port 0. It left the
captured RNG index at 55 and did not produce a natural call. Its retained result
is `/home/dev/neptune-research-private/707/rng-natural-navigation-008/start-pulse-600/result.json`
(SHA-256 `7248c98a2d28f6a993cee349ad527daf3817c3831e3200f31e4d87a1187ef76f`);
that input window is not counted as RNG recovery.

Next, use the native source-call observer to capture a natural `0x0600A0EC`
caller and complete register/stack context, then investigate seed initialization,
all index values, repeated calls, and release differences. Issue #492 remains
open.

## Reproduction

With the existing VPS inputs, run each window through the host's configured
shared gate and the offline `unshare --user --map-root-user --net` namespace.
The private guarded supervisor used for the retained runs is
`/home/dev/neptune-evidence/code707-20261103/run-rng-wrap-formal.py`:

```sh
timeout 60s nice -n 10 /usr/bin/unshare --user --map-root-user --net \
  /home/dev/hellotalk/automation/.venv/bin/python \
  /home/dev/neptune-evidence/code707-20261103/run-rng-wrap-formal.py \
  --output rng-wrap-formal-NEW

timeout 60s nice -n 10 /usr/bin/unshare --user --map-root-user --net \
  /home/dev/hellotalk/automation/.venv/bin/python \
  /home/dev/neptune-evidence/code707-20261103/run-rng-wrap-formal.py \
  --output rng-wrap-formal-NEW --resume
```

The first command starts at captured frame-1800 state; the second resumes the
saved CPU and WorkRAM after the first 512-instruction window. Use a fresh output
name for a new independent run. Do not resume a completed report.
