# Original NetLink 68000 helper and bounded dispatch paths

Issue [#600](https://github.com/elgansayer/Neptune-Bomberman/issues/600) continues
#483/#488/#480/#464 after [the static sound-code discovery](2026-11-02-original-sound-code.md).
The original sound CPU helper at `0x4B00` now passes **88 constructed cases twice**.
Five original entry wrappers additionally pass **2,560 constructed dispatch cases
twice**, including the helper call/return. Complete reports are identical per
experiment. These are actual original 68000 instruction executions, not a static
instruction census or owned-byte smoke. Destination handlers are not executed.

The [derived receipt](../evidence/2026-11-02-original-netlink-m68k.json) retains
source/build/adapter/range/report hashes, counts and six altered-original controls.
Complete private reports and supervisor outcomes are under
`/home/dev/neptune-research-private/600/nlsnd-leaf-001/` and
`/home/dev/neptune-research-private/600/nlsnd-dispatch-001/`; preparation and
runner recipes/logs are in `/home/dev/neptune-evidence/code600-20261102/` and
`/home/dev/neptune-code-recovery-20261102/.factory-tools/code600-001/`.
No original module, raw memory dump, full disc or BIOS is included in Git.

## Source and CPU identity

USA MK-81070 V1.003, original `NETLINK/SNDDRV.BIN`, 23,920 bytes, SHA-256
`f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`.
This is the NLSND lifetime in the sound 68000 address space, candidate load zero.
Its original disc extraction/EDC/source identity is retained by #596. It remains
separate from the equal SND/XBSND driver slices and every SH-2 mapping. The
original full source hash/length must match before any execution.

The helper instruction extent is `[0x4B00,0x4B1C)` in both sound addresses and
file offsets. It contains seven original instructions. The wrappers occupy the
ten-byte ranges beginning `0x40C8`, `0x40D2`, `0x40DC`, `0x40E6`, `0x40F0`;
the common dispatch code is `[0x4104,0x4124)`. Every executed range has a hash in
the receipt. The full original instruction source buffer remains unchanged.
The helper uses its pointer at sound address `0x450` as data, not an instruction.

## Exact helper memory/ABI contract

For an explicitly initialized 32-bit value `b = read32(0x450)`:

```text
A4 = (b + 0x2000) modulo 2^32
A5 = (b + 0x2400) modulo 2^32
A6 = (b + 0x2100) modulo 2^32
RTS reads the caller's longword return address at SP; SP increases by four
```

The original path is `4B00,4B04,4B0A,4B0C,4B0E,4B14,4B1A`.
Exactly two data reads occur: four bytes at `0x450` and four at the explicit
return slot. No writes occur. All D registers, A0–A3 including **A2**, SR/CCR
and other initialized visible state are preserved except PC/SP and A4–A6 as
specified. Every source-buffer byte and every mapped data/stack byte is compared
unchanged. This is sampled state preservation, not every possible machine state.
The routine makes no device or SCSP access in these tests.

The 88-case product combines 11 pointer bit patterns (0,1,0x7FFF,0x8000,
0xFFFF,0x10000,0x7FFFFFFF,0x80000000,0xFFFFDFFF,0xFFFFE000,0xFFFFFFFF), four
supervisor SR states (0x2700,0x271F,0x200A,0x2015) and two register poison
patterns. Computed pointers are not dereferenced by this helper, so arithmetic
wrap cases do not invent memory at the resulting addresses. Each case uses a
reset CPU followed by explicit register setup and a four-byte return slot.
Original reset/startup code is not executed during that initialization.

Complete helper report SHA-256:
`8a89090f33da392098799219f11a157b77b29adc506d34f6197645bf825de9f4`.
Original-copy controls change the A4 immediate, remove the A6 copy, and replace
RTS with a self-loop. All three reject **88/88** cases: the first two fail the
independent register contract and the loop hits the 32-instruction limit.
Source originals stay unchanged; mutation hashes are distinct in the receipt.

## Original wrapper → helper → indirect target

The five wrappers set A2 to five distinct bases before branching to `0x4104`:

| Entry | A2 base |
| --- | --- |
| `0x40C8` | `0x4124` |
| `0x40D2` | `0x414C` |
| `0x40DC` | `0x4138` |
| `0x40E6` | `0x4160` |
| `0x40F0` | `0x4174` |

The original BSR at `0x4104` pushes `0x4108`; helper RTS returns there and
preserves A2. With initial D0 and initialized tag byte, the common original
instructions establish:

```text
i = initial_D0 & 7
A6 = b + 0x2100 + 96*i
t = read8(A6+2) & 7
D0 = (initial_D0 & 0xFFFF0000) | i
D7 = 4*t
A2 = wrapper_base + 4*t
PC = A2 after the JMP at 0x4122
```

A4/A5 retain the helper results. D1–D6, A0/A1/A3 and SP are preserved. Final
SR is `(initial_SR & ~0x1F) | (4 if t == 0 else 0)`: the byte shift clears X/C,
and N/V are zero for this masked range. In particular the word operation on D0
preserves its upper halfword; the explicit CLR.L on D7 is needed to avoid carrying
an earlier multiplication's upper bits into the address addition.

Each path executes exactly **20 original instructions**, including the seven
helper instructions. The instruction hook records the selected wrapper, branch,
BSR, helper RTS, return at4108 and indirect JMP. It stops when PC equals the
calculated destination, **before any destination instruction is fetched/executed**.
This establishes the transfer for the constructed states, not handler behavior,
a natural selector domain or a complete call graph.

Exactly one four-byte stack write saves4108 at SP-4; reads then fetch the pointer,
that return address and one tag byte. The saved return remains at SP-4 while SP
is restored. Every unaffected mapped byte, including the outer return slot, is
compared with its baseline. All other writes and undeclared data reads fail.

The 2,560-case product covers all five wrappers, indices0..7, tag low bits0..7,
two D0 upper-bit/tag-high-bit variants, two initial SR states and two explicitly
initialized pointer bases (0x8000/0x10000). Tag records are mapped one byte at the
selected address only; no invented device state or unspecified object memory is
provided. Final report SHA-256:
`ab7a545316a08d777874c5504471ec9ecc0380f61d1a87d8e3623c58f7adc5d5`.

For a complete 5×8×8 control subset, changing the first wrapper's table base
rejects64/320 cases, narrowing the tag mask to3 rejects160/320, and removing the
upper-D7 clear rejects200/320. Wrong destinations meet the instruction-access
guard instead of executing a handler with invented RAM. Unchanged cases are
retained rather than counted as rejected. These are original-instruction controls,
separate from the independent scalar/register/memory comparisons.

## Pinned native preparation and executable bounds

The new adapter reuses the **installed** Musashi CPU source from
`saturn-recomp@f20de940e8013fc84103a5b39c4069ed8071b1f9`. The source lock pins
all19 files under its Musashi directory, including dependencies and upstream
notices; no CPU implementation or vendor source is copied into Neptune. The
adapter compiles m68kcpu/m68kops/SoftFloat plus the small owned callback shim.
The source's plain68000 configuration remains intact; instruction hooks and
separate instruction/data callbacks are explicitly enabled. No SCSP/device model
is supplied. The resulting prepared library hash is
`cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c`.

Preparation was a separate guarded job with **original inputs and broker state
hidden**, read-only source/accepted tool mounts, one compiler process, 60-second
compiler timeout and 2GiB address-space cap. It retained build diagnostics and
then validated fresh installation and reuse on owned LEA/RTS instructions plus
loop, forbidden-write, unmapped-read and escaped-PC controls. A fresh successful
call after the failures must match its earlier result, testing per-case reset
recovery. Owned smoke receipts explicitly state original bytes were not executed.
No accepted core, state, source checkout or provider configuration was replaced.

Original execution then mounted both the prepared generation and original
container read-only, outside writable private report directories. Prepared
receipt/source-lock/backend/binary identities are checked before loading. Every
call rejects invalid/overlapping controlled regions, code/data overlay of an
executed range, PC escape, extra data reads/writes and instruction/event overflow.
Only the declared initialized data/stack regions exist. No fallback reads from
undefined memory are possible. The entire instruction buffer is compared for
changes. The native ABI is versioned and its register indices are checked against
the actual Musashi header at compile time.

`m68k_execute(1)` runs one instruction per call; the hook counts before execution
and the adapter verifies exactly one hook event per completed step. Initialization
uses synthetic vectors, consumes reset accounting without executing an original
reset instruction, then explicitly sets visible registers. No instruction is run
at the sentinel/dispatch stop. Native state is process-global, so the adapter is
serialized within a process. This tool does not establish safe concurrent calls.
Model accounting was88 for the leaf and238/240/242/244 for dispatch; these are
Musashi cycle units, **not measured Saturn timing, audio samples or hardware
parity**. No second CPU/hardware oracle is claimed.

## Reproduce and continue

Use existing host admission for preparation, with a fresh cache or an accepted
read-only generation. Preparation needs no original input:

```sh
python3 tools/saturn_lab/m68k_probe.py \
  --sources /home/dev/neptune-tools/saturn-recomp-f20de94 \
  --cache /home/dev/neptune-code-recovery-20261102/.factory-tools/NEW-prepared-m68k
```

The trusted coordinator prepares an isolated generation before mounting it
read-only into the original job. This is the bounded #600 preparation boundary,
not a claim that factory#518 automatically routes/recovers this tool today.
Existing prepared cache for this evidence is `.factory-tools/code600-001/prepared`.
Choose new reports, run each twice and compare complete files:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_netlink_pointer.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code600-001/prepared \
  --report /home/dev/neptune-research-private/600/NEW-leaf-run1.json
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_netlink_dispatch.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code600-001/prepared \
  --report /home/dev/neptune-research-private/600/NEW-dispatch-run1.json
python3 tools/saturn_lab/check.py
```

Source heads: helper/preparation `173bef4caf2bf12b95f67b962e40fbbcf13681c4`,
dispatch `9f792b88c70afec360fc8ad7f317ebc4d4501e99`, intake base
`be254b056bedacee086d84dd4b36ba25bbe7d631`. All actual jobs passed isolated
mount assertions under the existing shared host gate (observed limit3, unchanged),
180-second own leases, and 60-second original-command bounds. They released their
own leases; #597 SH2 instrumentation and Gemini#487 remain untouched. Native
preparation took about20 seconds; each repeated experiment pair finished in under
three seconds. No new model/provider session, paid fallback, allowance, scheduler
or continuity activation. Existing account/CI spend is unknown.

Eleven new owned synthetic tests cover ABI/guard rejection, signed/wrapped scalar
expectations, source/prepared tampering, selection and immutable private failures.
The full177-test input-tooling suite and warning-as-error syntax check of the
owned C backend pass. Native preparation smokes and original CPU runs are separate
host evidence, not CI fixtures. Exact-head/current-base CI is the publication gate.

The previously unresolved NetLink4122 jump now has tested constructed entry-path
contracts. Natural caller/selector values, destination handler semantics, sound
commands, SCSP/DSP, original reset handshake and source-driver self-modification
remain unvalidated. Next inspect and test one selected destination's actual data/
side-effect contract, reconcile static decode conflicts and expand sound/runtime
coverage. The whole code programme and unknown function denominator remain open.
