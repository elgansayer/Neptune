# Real Saturn checkpoint graphics acquisition

The preserved USA MK-81070 V1.003 checkpoint now yields reproducible VDP1 and
VDP2 graphics inputs. This is the original-host S06 slice of #485 and the repair
in [#527](https://github.com/elgansayer/Neptune-Bomberman/issues/527).
The [derived host receipt](../evidence/2026-10-30-saturn-state-host-proof.json)
records identities, output hashes, context, comparisons and controls. Full states,
graphics arrays, BIOS/discs and detailed process evidence remain host-private.

## Failure found by the real input

The accepted adapter from #526 failed with
`Missing/wrong-sized field: VDP1.TVMR`. Its synthetic producer had supplied
literal `TVMR` and `FBCR` keys. The actual full-core checkpoint instead contains
one-byte `VDP1_TVMR` and `VDP1_FBCR` records.

At the pinned core's `mednafen/state.h`, the outer `SFVAR` dispatch expands the
`vdp1_common.h` aliases before the inner macro stringifies them. The contrary
comment in `vdp1.c` is insufficient evidence. The fix reads the exact prefixed
records while preserving normalized `TVMR`/`FBCR` context names and required
widths. It does not accept a guessed fallback or mark original data synthetic.

The Python fixture now declares the producer layout independently of the adapter.
Regression tests require the real alias names and reject short-name-only records.
The optional actual-source C serializer fixture now invokes the same `SFVAR`
alias path, instead of supplying a literal guessed name. It again checks all
526592 uint16 elements, plus nonzero register values and wrong-order detection.
Its new synthetic state digest is recorded in the host receipt. The earlier #526
synthetic smoke remains historical evidence; it did not exercise these full-core
record declarations and did not establish original-checkpoint compatibility.

## Original inputs and repeatability

| Input | Observed identity |
| --- | --- |
| Checkpoint | Existing accepted USA frame 3000, 6323674 bytes |
| State SHA-256 | `a6f7f4adb7709b6f16584a54c2f87a3ce32d9f4cf170ed0bf1a5c88e23d5e2a9` |
| Core source | `01bc063fdd0fb5fc208850c9ecc658834df762ab` |
| Actual core binary SHA-256 | `c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e` |
| Input-lock identity | `56e594393834c99e782d83551cbf85313d7dbf5e8ed22c17006a672ce1a9beeb` |
| Producer | Accepted little-endian x86_64 VPS/profile |
| Original witness | USA kernel SHA-256 `20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7` |

Two adapter processes ran in the offline credential-free namespace against
unchanged private copies. They produced byte-identical files, including manifests.
The hash-verified original kernel's 64-byte code witness matched normalized high
work RAM at `0600A4B0`. Declaring the wrong producer byte order failed that witness
and created no output. The initial failing command and its diagnostic are retained.

## Separate direct memory comparison

Two fresh processes loaded the unchanged accepted core and restored that same
checkpoint using its locked frontend/settings/media. No new emulated frames ran.
The existing shared host resource gate admitted them under one bounded exclusive
lease, which was released. The namespace mounted accepted media/core/profile
read-only; only the new private experiment directory was writable.

A separate acquisition path resolved the loaded ELF base with `dladdr` and read
its actual uint16 arrays directly through `ctypes`. `nm` identified symbols in
that exact hash-verified binary. For duplicate `VRAM`/`CRAM` symbols, the local
`vdp2.c` group was selected explicitly, excluding `vdp2_render.c` mirrors.
Unique `VDP1_VRAM` and `RawRegs` symbols were also size-checked. Numeric memory
values were packed big endian independently of the adapter's adjacent-byte swap.
No serialized-field offsets were used to acquire this memory view.

| Array | Bytes compared in full | Normalized SHA-256 |
| --- | --- | --- |
| VDP1 VRAM | 524288 | `c8aa5050af405ef57b90a355d9cd1b1a59bc1218b6121e15e178173a1e65c0f5` |
| VDP2 VRAM | 524288 | `4919db561bcc20bbea9db169a1effab12c15df631b27b55e837d5775a6789bfc` |
| VDP2 CRAM | 4096 | `dc21279842c23cc79ccdfa2ef69d52bec765781109a78bed0287201ef5b2b08c` |
| VDP2 raw registers | 512 | `0d63074b0d24c2b9bc01e778de1b9b3198f11fdb7e5c62197395d1ba2a7d9425` |

All 1053184 bytes matched in both independently started processes; their derived
receipts were identical. A changed byte in each expected array disagreed with
the direct memory result. Comparing the unswapped native payload also detected
the wrong word order for each observed array. These checks detect acquisition or
normalization mistakes, not every future renderer bug.

Both acquisition paths use the same emulator implementation. The direct memory
comparison is independent of the state parser, not an independent emulator oracle.
It establishes this checkpoint's graphics acquisition, not Saturn hardware accuracy.

## Observed phase and remaining limits

VDP1 context was `DrawingActive=0`, `CommandPhase=6`, `CurCommandAddr=64` words
(`128` bytes), `RetCommandAddr=-1`, framebuffer 0, `TVMR=0`, `FBCR=3`, `PTMR=2`
and `EDSR=3`. VDP2 reported CRAM mode 0, HRes/VRes 0 and interlace mode 0.
These are captured context values, not proof of a specific player, animation or
scene. An inactive command processor does not establish which framebuffer or
palette combination produced the displayed image.

No player/effect was identified, no palette-resolved preview or spritesheet was
published, and no campaign/battle comparison or emulator timing was established.
Next select an observed textured command from a declared scene, retain its source
span and coherent palette/register context, and extend the existing exporter only
for the actual observed colour semantics. Preserve Gemini #484's archive work.
#485/#487/#512 remain open for those further results.

## Regeneration and retained evidence

Run the accepted adapter on the preserved checkpoint with fresh output names:

```sh
python3 tools/saturn_lab/state_graphics.py \
  --checkpoint /home/dev/neptune-research-private/27/continuation-accepted/checkpoint.json \
  --producer-byte-order little \
  --core-source-revision 01bc063fdd0fb5fc208850c9ecc658834df762ab \
  --kernel /home/dev/neptune-research-private/483/0KRNL.BIN \
  --capture-id SATURN-GFX-REAL-001 --output /PRIVATE/NEW-GRAPHICS-OUTPUT
```

Use the existing isolated runner around that command; it is not itself an OS
sandbox. Repeat into another fresh directory and compare every output. Repeat
with `--producer-byte-order big` and require the witness failure.

Private harness `/home/dev/neptune-research-private/485/direct_memory.py` and
`/home/dev/neptune-evidence/issue485/run-direct-memory.py` reproduce the separate
memory acquisition; the executed harness digest is in the receipt. The harness
uses the accepted configure receipt's root/lock, checks all locked identities,
loads that locked frontend, restores the checkpoint and performs the ELF-backed
array reads described above. Each native process has a 60-second external bound,
50-second CPU bound, 2 GiB address-space bound, disabled core dumps and bounded
output files. No production credential, provider call or unrestricted socket is
available in that namespace. Detailed logs/first failure are retained under
`/home/dev/neptune-evidence/issue485`; array/state outputs stay private under the
experiment/worktree's ignored directories.
