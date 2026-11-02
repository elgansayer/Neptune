# Original NetLink state copy and bounded record scan

Issue [#602](https://github.com/elgansayer/Neptune-Bomberman/issues/602) continues
#483/#488/#480/#464 using [#600's accepted original 68000 adapter](2026-11-02-original-netlink-m68k.md).
Two additional original entries pass twice, with **8,456 cases per run**:
8,192 state-copy cases and264 record-scan cases. Complete reports are identical,
SHA256 `7eea248482fa02b90f7ec335c092e4ad328f2a4938f3765624dcf817417e7257`.
The [derived receipt](../evidence/2026-11-02-original-netlink-records.json)
retains original range/tool/report hashes, all controls and the initial failed
access hypothesis. These are CPU-only controlled-input results, not natural
sound events or proof of a queue/channel/voice interpretation.

## Original identity and state-copy contract

USA MK-81070 V1.003, sound CPU68000, original `NETLINK/SNDDRV.BIN`,23,920bytes,
SHA256 `f37289395dcf2f37f14157f6333ac9f6269d71888f5c08978411e0e034ab2296`,
candidate mapping0 in the NetLink sound-driver lifetime. Full source identity is
checked before execution. This mapping/lifetime remains distinct from SND/XBSND,
SH2 modules and Japan. All code/literal bytes used remain original.

Entry `0x4BB6`, exclusive end `0x4BE0`, executes12 original instructions. Given
an explicitly initialized pointer `b = read32(0x404)` and bytes at A6+1/+2/+3:

```text
index = read8(A6+1)
destination = b + 0x80 + 2*index
write8(destination, read8(A6+2))
write8(destination+1, read8(A6+3))
```

The original clears D2 before loading the byte and shifts its low word once;
the indexed word therefore ranges0..510, not a signed or stale-upper-bit index.
It saves/restores D0-D2/A0 in16 stack bytes. All visible general registers are
preserved except SP+=4 on RTS; PC reaches the initialized return sentinel.
The final SR low five bits are8 if the second copied byte has bit7 set,4 if it
is zero, otherwise0. Higher SR bits are preserved in the tested supervisor states.
The shift clears X/C for these index values; the last byte store supplies N/Z
and clears V/C. Stack/data/code bytes outside specified stores remain unchanged.

The8,192-case product covers **all256 possible index bytes**, four payload pairs
(0/0,1/255,128/127,255/128), four initial supervisor SR values
2700/271F/200A/2015 and two pointer bases30000/40000. Distinct initial register
values have differing high/low halves so saved-register order, preservation and
word transaction order are observable. Only the four-byte pointer, three source
bytes, two destination bytes and20-byte stack/return extent are mapped as data.

## Original bounded scan contract

Entry `0x4BE0`, exclusive end `0x4C2A`, receives A5 pointing at32 explicitly
initialized twelve-byte records. It reads bit7 of each record's first byte,
advances12 while occupied, and stops at the **first** clear bit or after32 records.
If a free record exists, it writes:

| Record field | Written value |
| --- | --- |
| +1,+2,+3 | low bytes of D0,D1,D2 |
| +0 | low byte of D3, then that byte OR0x80 |
| +4..+7 | D4, big endian |
| +8..+11 | A6, big endian |

No other record byte changes. The initial clear flag and any later free record
are controlled inputs; when two free slots exist, the later one stays unchanged.
If all32 slots are occupied, every record byte stays unchanged. The bit-set
operation reads/writes the just-written flag byte and is included in the access
sequence, including when its bit was already set by D3.

D7/A5 are saved/restored in eight stack bytes; a separate halfword stores SR.
All general registers are restored/preserved except SP+=4 on RTS. **Returned SR
is0x2700 for all tested inputs and both outcomes.** The routine writes SR2700,
then saves that value. The full-list path temporarily sets carry, but the later
SR restore overwrites it. It therefore does not expose a carry return in these
constructed calls. This result is not changed to a more conventional allocator
contract, nor assigned a natural caller meaning without reference evidence.

Every first-free position0..31 and the all-occupied case is tested for four
initial SR values and two distinct payload/occupancy variants:264 cases. The
original executes18+5*i instructions when first free is at indexi (18..173), and
168 instructions when full. Every executed PC, stack/data transaction, register
and expected byte result is compared. Only the384-byte record area and14-byte
stack/return extent are mapped as data; no SCSP/device RAM is supplied.

## Retained failed hypothesis and corrected transaction evidence

The first full probe attempt failed in original_execution and is retained at
`/home/dev/neptune-research-private/602/nlsnd-records-001/run1.json`, source head
`b941f356eb322c175758f8ad342d42f658175694`. It expected a single32-bit callback
for each MOVEM.L predecrement register save. A bounded isolated diagnostic ran
one original copy call, one full scan and one allocating scan. Their final
registers/memory matched the independent contracts; their observed stack events
were ordered **low-word then high-word16-bit writes** for each saved register.
The pinned `m68k_op_movem_32_re_pd` implementation independently explains this
callback sequence. Its postincrement loads use32-bit callbacks.

The corrected probe declares these exact16-bit events without adding mapped
bytes, permitting extra accesses or changing output arithmetic. Copy now requires
eight halfword save writes, four longword restore reads and its return read,
besides the pointer/source/destination transactions. Scan requires four halfword
register-save writes plus its SR halfword write, then exact flag/data/restores.
The actual diagnostic and failure hashes are in the receipt; selected results
are private at `/home/dev/neptune-research-private/602/diagnostic-001/`.
These are pinned-interpreter observations, not independently measured bus timing.

## Actual original runs and rejection controls

Corrected source head `a0c2e9af525c42ce7e1cf14d4a2b9ef15e8e3c02`, intake base
`287c4298a2e7a1e6bfb5332ab2017cd49aca04ea`. Fresh reports are at
`/home/dev/neptune-research-private/602/nlsnd-records-002/run{1,2}.json`.
Supervisor/commands/logs are `/home/dev/neptune-evidence/code602-20261102/`.
Each CPU call uses fresh explicit register state and initialized data, the
accepted prepared binary hash
`cc059d3a7f443cf2869496c245f9acae357b1f773e054e2ac009e5632df2c83c`, strict
read/write/PC/event bounds, and32(copy)/256(scan) instruction ceilings. Complete
source code buffers and all mapped bytes outside expected writes are compared.
All original sources/prepared tools are read-only; broker authority is hidden.
Each report pair passed under60-second command bounds in aboutsix seconds total,
using the existing shared host gate at unchanged observed limit3. Own leases
were released; #597 and Gemini#487 remain untouched. No native rebuild, new model
session, scheduler, paid fallback, allowance or continuity activation occurred.
Existing account/CI spend remains unknown.

| Original-copy mutation | Rejected / tested | Failure |
| --- | --- | --- |
| remove copy index clear | 256/256 | undeclared write destination |
| remove second byte store | 256/256 | expected output bytes missing |
| reduce scan limit32 to31 | 16/264 | wrong last-slot/full-case reads or output |
| remove record allocation bit-set | 256/264 | wrong record/access sequence |

Unaffected cases for a mutation remain recorded. All four controls distinguish
meaningful wrong behavior, not merely a changed source digest. Source originals
remain unchanged; altered-copy hashes are retained separately.

Five new synthetic tests cover selection, high-byte indexing/SR, first-free/full
contracts and native/memory/ABI/path rejection. The full182-test input suite
passes at corrected source. Those metadata/scripted contracts do not replace
the actual pinned-native original execution or establish independent CPU/hardware
fidelity. Model cycles are retained as model units, not Saturn/audio timing.

## Repeat and continue

After existing host admission, choose two fresh report names and compare them:

```sh
timeout 60s nice -n 10 python3 tools/saturn_lab/probe_netlink_records.py \
  --source-file /home/dev/neptune-research-private/596/sound-001/NLSND.container \
  --prepared /home/dev/neptune-code-recovery-20261102/.factory-tools/code600-001/prepared \
  --report /home/dev/neptune-research-private/602/NEW-records-run1.json
python3 -m unittest discover -s tools/saturn_lab/tests -p test_probe_netlink_records.py -v
python3 tools/saturn_lab/check.py
```

Next derive the record-consumer path at4B1C and its4C2A callee, including conditions
for real SCSP side effects. Do not flatten device registers into generic RAM.
The state initializer at445C and shared-driver decode conflicts remain eligible;
Godot/native audio, natural sound events, self-modification, DSP, other regions,
boot/overlays/slave/gameplay/RNG and complete function/module coverage stay open.
These two isolated-tested entries do not complete #488/#464/#477/#515.
