# `PROGRAM.BIN` bank directory, Hudson ring/delta codec & resident memory verification (`EXP-SAT-ARCHIVE-002`): 30 October 2026

Gemini `#464` programme, bounded slice `#484` (`[P0][RSAT-007] Decode PROGRAM.BIN banks against their resident memory images`).
Informs `#484`, `#464`, `#394` (`REF-001`), `#28`, and `#399` (`REF-006`).
Machine-readable receipts: [`docs/restart/saturn-archive/`](../saturn-archive/README.md).
Versioned tooling: [`tools/saturn_archive/`](../../../tools/saturn_archive/README.md) (reuses [`tools/saturn_disc/`](../../../tools/saturn_disc/README.md) and [`tools/saturn_lab/state_graphics.py`](../../../tools/saturn_lab/state_graphics.py) without modifying either package).
No disc, BIOS, track, save-state, framebuffer, or raw RAM/VRAM bytes are committed or transmitted into model context.

---

## 1. Executive verdicts

1. **Verbatim CD staging into `MAIN.WorkRAML` — CONFIRMED (`100.0%` byte equality)**:
   - `0KRNL.BIN` (`0x06008B26`) copies `sector_count * 2048` bytes verbatim from `PROGRAM.BIN` into `load_dest` in `MAIN.WorkRAML` (`0x00200000..0x00300000`).
   - USA `base1` (`bank_id=1`, `344,064` B at sector `16`, SHA-256 `b4c9328f3cdf576d3efe07d61ec9fbd6b27d0b6e7fa4e2243c00b8e8ceee7a9f`) matches resident `MAIN.WorkRAML[0x000000:0x054000]` (`0x00200000..0x00254000`) **`344,064 / 344,064` bytes (`0` mismatches)** across three independent checkpoints: `#27` `menu-release` (`f=10800`), `#27` `navigation-release-late` (`f=10200`), and `#484` `normal2-run1` (`f=30360`).
   - Cross-region byte-identical `normal2` (`bank_id=5`, `573,440` B at sector `912`, SHA-256 `6c662d2cf24d8a2548a4b4982a9b780de0207cec227f5cfdf4dcf394300ac9e3` on both USA `MK-81070 V1.003` and Japan `T-14302G V1.000`) matches resident `MAIN.WorkRAML[0x054000:0x0e0000]` (`0x00254000..0x002e0000`) **`573,440 / 573,440` bytes (`0` mismatches)** in `#484` `normal2-run1`/`run2` (`f=30360`).
2. **Load-time pointer relocation — FALSIFIED**:
   - All `52/52` bytes of the `0x34` header (`11` `u32` slot pointers + 8-byte ASCII name) and every internal sub-table pointer remain 100% unchanged in resident `MAIN.WorkRAML`. Each bank is pre-linked offline to its fixed `load_dest` (`0x00200000`, `0x00254000`, `0x002da000`, `0x002ee000`, or `0x002fb000`); `0x06008A96` simply copies the `0x34` header into kernel globals `0x060BD8E4..0x060BD913`.
3. **Sub-resource Hudson compression & unpacking into VRAM/WRAM/SCSP — CONFIRMED**:
   - Sub-resources inside staged `WorkRAML` banks are compressed with a **Hudson Predictive Ring/Delta Codec** (`0x0603443C` direct / `0x0603461C`+`0x0603469E` 4-byte streaming) using 1..4-bit selector streams (`0x060B53B4`, including `0x0603434C`'s 3-byte bit-planar 3-bit width reader), 5 single/dual 16-entry ring modes (`0x060B53C8`), and 20 delta/lookback predictor methods (`0x060B52C4..0x060B5364`).
   - Independent Python decompression matches resident memory bit-for-bit across **`VDP2.VRAM`** (`base1` Slot 0 `3/3` blocks = `36,032` B exact; `normal2` Slot 0 block `#1` = `107,264 / 107,264` B exact at `VDP2.VRAM+0x20000`), **`VDP2.CRAM`** (`base1` `8` exact palettes; `normal2` `4` exact palettes), **`MAIN.WorkRAMH`** (`normal2` Slot 7 stage grids `#1`, `#2`, and `#4` = `8,192 / 8,192` B exact at `WorkRAMH+0x0f28b0`, `0x0f48b0`, and active pointer `*(u32*)0x060D7E94 = 0x060F68B0`), and **`VDP1.VRAM`** (`base1` Slot 8 **`623`** unique sprite blocks = `155,200` B exact; `normal2` Slot 8 **`150`** unique sprite blocks = `70,144` B exact).
4. **All `#473` (`EXP-SAT-DISC-001`) structural anomalies resolved from `0KRNL.BIN`**:
   - Live `0KRNL.BIN` directory tables hold **`72` entries (USA)** and **`66` entries (Japan)**, Fit **100% inside `MAIN.WorkRAML`** (`max_workram_l_end = 0x00300000`), and leave **`2,169,666` B (USA)** / **`2,931,522` B (Japan)** of unreferenced build-container tail at the end of `PROGRAM.BIN`. Both `0x002fb000..0x00325000` (`s_vo101` at sector `6328` measured to EOF) and `0x00250000` (`s_vo55` at sector `6264`) exist exclusively in that unreferenced tail.

---

## 2. Locked inputs & emulator provenance

USA and Japan discs remain strictly separated profiles; `normal2` (`bank_id=5`) was selected specifically because `#473` proved its 280 sectors (`573,440` B) are byte-for-byte identical across both regions.

| Artifact | Release / Scope | Size (bytes) | SHA-256 |
| --- | --- | ---: | --- |
| USA CUE (`Saturn Bomberman (USA) (1S).cue`) | `MK-81070` `V1.003` (`U`) | — | `785e6f9f98dfcfadbd1fa24eb87dfad20bc94173c88565d75c9616aa31e6e9da` |
| USA `BOMSS/0KRNL.BIN` (load `0x06006000`) | `MK-81070` `V1.003` (`U`) | `786,432` | `20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7` |
| USA `BOMSS/PROGRAM.BIN` | `MK-81070` `V1.003` (`U`) | `12,976,962` | `f5154d4aabdf9f3434b966a0d09fe5d08aa1ddabfa8848b836be630f506596d5` |
| Japan CUE (`Saturn Bomberman (Japan).cue`) | `T-14302G` `V1.000` (`J`) | — | `ac6c34bb3d1ea689e0a0b748ac96444df5bf1152bd6e4d6c43e1cfcd9d0fbcdb` |
| Japan `0KRNL.BIN` (load `0x0600A000`) | `T-14302G` `V1.000` (`J`) | `786,432` | `23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb` |
| Japan `PROGRAM.BIN` | `T-14302G` `V1.000` (`J`) | `12,976,962` | `928b959f9730a0eb02319c1541b2d9ca7849c1c8860738302c89d2a19e0da348` |
| Beetle Saturn `mednafen_saturn_libretro.so` | Emulator core (`#27` lock) | — | `c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e` |
| `saturn_headless_frontend` / settings / lock | `#27` harness | — | `84b29f26…c8da` / `ff026117…2f25` / `c3c92ca3…db99` |
| `#27` `menu-release` (`f=10800`) | Private checkpoint | `6,323,674` | `e5bd5164193db6b7af59ecd1b1705b4a794debd8e8b1496c8406c47d21f33506` |
| `#27` `navigation-release-late` (`f=10200`) | Private checkpoint | `6,323,674` | `7049c38909dcd57a1aa84248cf3a531fdefef9f6d1150fff3f2822d4f70cef10` |
| `#484` `normal2-run1` & `normal2-run2` (`f=30360`) | Private checkpoints (`2` runs) | `6,323,674` | `311c886c5bc2b0dc78d0d4ccdeb41044939b10ff334848f1691adf86b6d0e601` |

*Emulator independence note*: Both Beetle Saturn (`mednafen_saturn_libretro.so`) and standalone Mednafen `1.32.1` share Mednafen Saturn emulation ancestry; resident comparisons here prove exact agreement between offline `0KRNL.BIN`-derived decoding and Beetle Saturn's emulated SH-2/VDP1/VDP2/SCSP state, not two unrelated emulator lineages.

---

## 3. Live `0KRNL.BIN` bank directory & resolution of `#473` anomalies

Disassembly of `0KRNL.BIN` (`0x06008B26..0x06008C34` on USA; matching literal pool `0x0600CF30` on Japan) reveals that `PROGRAM.BIN` is **not** indexed by scanning `0x34` headers on disc. Instead, the kernel indexes three parallel big-endian arrays by `bank_id`:
- `u16 sector_offset[N]` (2048-byte sector offset from the start of `PROGRAM.BIN`)
- `u16 sector_count[N]` (exact 2048-byte sector count to stage via GFS)
- `u32 load_dest[N]` (target address in `MAIN.WorkRAML`, `0x00200000..0x002FFFFF`)

| Metric | USA (`MK-81070 V1.003`) | Japan (`T-14302G V1.000`) |
| --- | --- | --- |
| `0KRNL.BIN` load base / literal pool | `0x06006000` / `0x06008c28` | `0x0600a000` / `0x0600cf30` |
| `sector_offset` / `sector_count` / `load_dest` | `0x06093ecc` / `0x06093f5c` / `0x06093fec` | `0x06095018` / `0x0609509c` / `0x06095120` |
| Live kernel `entry_count` (`N`) | **`72`** (`bank_id = 0..71`) | **`66`** (`bank_id = 0..65`) |
| Entries fitting inside `WorkRAML` (`<= 0x00300000`) | **`72 / 72`** (`max_end = 0x00300000`) | **`66 / 66`** (`max_end = 0x00300000`) |
| Referenced sectors / inter-entry gap sectors | `5,277` (`0..5276`) / **`0`** | `4,905` (`0..4904`) / **`0`** |
| Referenced bytes | `10,807,296` (`0x0a4e800`) | `10,045,440` (`0x0994800`) |
| Unreferenced build-container tail | `1,059` sectors + `834` B = **`2,169,666` B** | `1,431` sectors + `834` B = **`2,931,522` B** |
| Unreferenced tail SHA-256 | `5d2fc11230c2b7135a994420a638ed9d13aaf27ca3c76090ed7ae1e4fda2d04f` | `ec635f89638ff82057afb583f419a016bc805829e90db676cd2ea0c6b1b6a415` |
| Static `0x34` headers (`active + mid-slot + tail = total`) | **`68 + 43 + 125 = 236`** (+ `4` headerless active) | **`66 + 8 + 166 = 240`** (`0` headerless) |
| Active destination breakdown | `0x00200000`: 2, `0x00254000`: 19, `0x002da000`: 1, `0x002ee000`: 2, `0x002fb000`: 48 | `0x00200000`: 2, `0x00254000`: 18, `0x002ee000`: 2, `0x002fb000`: 44 |

### Exact resolution of every `#473` static inventory question

1. **Why `#473` saw `236` (USA) / `240` (Japan) static headers vs `72` / `66` live kernel banks**:
   `PROGRAM.BIN` was assembled on a fixed-size `12,976,962`-byte (`6,336` sectors + `834` trailing bytes) master container without zero-wiping sectors beyond the active directory (`sector 5277+` USA, `sector 4905+` Japan) or unused tail sectors inside wider slots (e.g., an 8-sector `s_vo*` slot overwritten by a shorter bank leaving an older `s_vo*` header 4 sectors inside the slot, accounting for the `43` USA and `8` Japan mid-slot residual headers).
2. **Why `#473` saw `s_vo*` extending `0x002fb000..0x00325000` past the `0x00300000` end of `WorkRAML`**:
   Active `s_vo*` voice banks (`bank_id = 27..71` USA, `22..65` Japan) are strictly `8` or `9` sectors (`16,384` or `18,432` B), occupying `0x002fb000..0x002ff000` or `0x002fb000..0x002ff800` — completely inside `MAIN.WorkRAML`. The `0x00325000` span in `#473` came from the final unreferenced tail header (`header_index=235`, `s_vo101` at sector `6328`) measured to EOF (`12,976,962 - 12,959,744 = 17,218` B; and earlier unreferenced tail gaps up to `172,032` B).
3. **Why `#473` saw `0x00250000` overlapping `base1`/`base2` (`0x00200000..0x00254000`)**:
   **Zero** active kernel entries load at `0x00250000`. The single header carrying `0x00250000` (`s_vo55` at sector `6264`, byte `12,828,672`) sits inside the unreferenced build-container tail in both USA (`header_index=227`) and Japan (`header_index=231`).
4. **Four headerless active entries in USA `0KRNL.BIN`**:
   USA adds `bank_id=23` (`sector=4936`, `50` sectors = `102,400` B at `0x002da000..0x002f3000`, starting with a 21-pointer table `0x002da058..0x002ff4ec` instead of an ASCII-named `0x34` header) and three 8-sector (`16,384` B) headerless slots at `0x002fb000` (`bank_id=41, 42, 43` at sectors `5036, 5044, 5052`).
5. **Runtime bank multiplexing & transient `s_*` sound staging (`0x00254000`, `0x002ee000`, `0x002fb000`)**:
   - `0x06008B26(r4=bank_id, r5=active_slot)` stages the bank into `load_dest[bank_id]` and records `0x060BD8C4[slot] = bank_id` and `0x060BD8D4[slot] = load_dest`.
   - Mode dispatcher `0x0600AE8C..0x0600B030` reads `*(u16*)0x26006158` (`mode=1` opening, `mode=2` normal worlds `0..4` indexed by `*(u8*)0x060C029C`, `mode=3` battle/xband, `mode=4` master, `mode=6` staff).
   - Helper `0x0600AE58(r4=sound_bank_id, r5=base_bank_id, r6=world_bank_id)` executes a **two-step staging sequence** at `0x00254000`:
     1. Calls `0x06008E80(r4=sound_bank_id, r5=1, r6=0)` — loads `s_nor2` (`bank_id=15`) into `0x00254000`, transfers its `Slot 10` payload into `SCSP.RAM` (`0x25A00000+`) via `0x060095E0(slot=10)`, and clears active slot `1` (`r6=0`).
     2. Ensures `base1` (`bank_id=1`) is resident at `0x00200000` (active slot `0`).
     3. Calls `0x06008E80(r4=world_bank_id, r5=1, r6=1)` — overwrites `0x00254000..0x002e0000` with `normal2` (`bank_id=5`) and latches its `0x34` header into active slot `1`.
   - **Live runtime confirmation**: During bounded step discovery (`frame=29400` -> `frame=29880`), `MAIN.WorkRAML[0x05402c:0x054034]` was directly observed holding `"s_nor2\xff\xff"` (`0x060BD8C8 == 15`) at `frame=29400` and `"normal2\xff"` (`0x060BD8C8 == 5`) 480 frames later at `frame=29880`, while `s_nor2`'s 256-byte audio probe remained intact in `SCSP.RAM` at offset `0x0b006` at `frame=30360`! Meanwhile, `0x002fb000..0x002fffff` doubles as a voice overlay slot (`s_vo*`) and as the Slot 8 sprite decompression scratchpad (`0x06068BDC`, confirmed by `1` exact decoded sprite prefix remaining at `0x002fb000` in all three `base1` checkpoints).

---

## 4. Hudson Predictive Ring/Delta Codec (`0x0603443C` / `0x0603461C`) & slot unpackers

### 4.1 Compressed stream header & bit-stream width readers (`0x060B53B4`)

Every compressed sub-resource starts with a variable-length byte header read by `0x0603443C` (direct buffer decode) or `0x0603461C`+`0x0603469E` (4-byte chunked streaming decode):

1. Byte `+0x00`: `b0`
   - `selector_bits = ((b0 >> 4) & 0x0F) + 1` (valid values `1..4`; number of methods `M = 1 << selector_bits`).
   - `stream_mode = b0 & 0x0F` (valid values `0..4`, indexing `0x060B53C8`).
2. Bytes `+0x01 .. +M`: `methods[0 .. M-1]`, each in `0..19` (indexing predictor tables `0x060B52C4` / `0x060B5314`).
3. Bitstream payload starting at byte `+(1 + M)`:
   - For each output element, read a `selector_bits`-wide `method_idx` via `0x060B53B4[selector_bits - 1]` (`sb=1`: MSB-first 1-bit; `sb=2`: MSB-first 2-bit crumbs; `sb=3`: MSB-first 3-bit octals; `sb=4`: MSB-first 4-bit nibbles) and look up `method = methods[method_idx]`.
   - If `method < 4` (signed delta mode): first read a **3-bit width code `w_code in 0..7`** using **`0x0603434C`**, which refills `24` bits (`3` bytes) at a time in **3-byte bit-planar layout** rather than contiguous big-endian bits:
     ```text
     b0, b1, b2 = stream[pos : pos + 3]
     for step in 0..7 (shift = 7 - step):
         w_code = (((b0 >> shift) & 1) << 2) | (((b1 >> shift) & 1) << 1) | ((b2 >> shift) & 1)
     ```
     - If `w_code == 0`: read `elem_bytes * 8` raw literal bits (`8`, `16`, or `32` bits MSB-first) directly as the new unsigned element `val` (no predictor base added).
     - If `w_code in 1..7`: let `bit_len = w_code + 1` (`2..8` bits), read `raw` (`bit_len` bits MSB-first), compute signed nonzero delta (`raw >= (1 << w_code)` -> `delta = raw - (1 << w_code) + 1`; else `delta = raw - (1 << w_code)`), and add `delta` modulo `2^(8 * elem_bytes)` to the predictor base (`0` for `method=0`, `ring[(idx-1)&15]` for `method=1`, `ring[(idx-2)&15]` for `method=2`, `ring[(idx-3)&15]` for `method=3`).
   - If `method in 4..19` (ring lookback copy): copy `ring[(idx - (method - 3)) & 15]` (`0` extra payload bits).
   - Write `val` in big-endian (`u8`, `u16`, or `u32`) and update `ring[idx & 15] = val`, `idx += 1`.

### 4.2 Five stream modes (`0x060B53C8`)

| `stream_mode` | `elem_bytes` | Ring state | Output element count (`decoded_bytes = B`) |
| ---: | ---: | --- | --- |
| `0` | `1` (`u8`) | Single 16-entry `u8` ring (zero-init) | `B` |
| `1` | `1` (`u8`) | **Dual** 16-entry `u8` rings alternating every element (`even -> ring_a`, `odd -> ring_b`) | `B` |
| `2` | `2` (`u16` BE) | Single 16-entry `u16` ring (zero-init) | `B / 2` |
| `3` | `2` (`u16` BE) | **Dual** 16-entry `u16` rings alternating every `u16` element (`even -> ring_a`, `odd -> ring_b`) | `B / 2` |
| `4` | `4` (`u32` BE) | Single 16-entry `u32` ring (zero-init) | `B / 4` |

### 4.3 Sub-resource slot unpackers (`0x34` header slots `0..10`)

| Slot | Kernel unpacker | Binary record layout & runtime destination |
| ---: | --- | --- |
| `0` | `0x06009470` | Null-terminated `u32` pointer list -> `+0x00 u32 default_dest`, `+0x04 u32 size_and_flags` (`bit 31 = raw`, `bits 0..30 = decoded_bytes`), `+0x08` payload -> **`VDP2.VRAM`** (`0x25E00000+`). |
| `1` | `0x06008E06` | Null-terminated `u32` pointer list -> `+0x00 u16 cram_word_offset` (`* 2` byte offset), `+0x02 u16 color_count`, `+0x04` raw RGB555 words -> **`VDP2.CRAM`** (`0x25F00000+`) and shadow CRAM (`WorkRAMH+0x0ce260`). |
| `2` | Polymorphic (`0x060094E2` vs `0x060095E0`) | In UI/menu banks (`base1`): VDP2 tilemap records (`+0x00 u8 w`, `+0x01 u8 h`, `+0x02 u16 flags`, `+0x04` compressed `w*h*2` stream). In stage banks (`normal2`): passed to `0x060095E0(slot=2)` as SCSP DSP/PCM command tables (contains `"DSP01e.EXB"`). |
| `7` | `0x0600C502` | Null-terminated `u32` pointer list -> `+0x00 u16 cols` (`64`), `+0x02 u16 rows` (`64`), `+0x04` compressed `8,192`-byte (`64x64 u16`) stage collision/tile grid -> **`MAIN.WorkRAMH`** (`*(u32*)0x060D7E94`). |
| `8` | `0x06068BDC` / `0x06068B86` | Header `(u32 anim_table_ptr, u32 desc_table_ptr)`. 12-byte descriptors `(u32 pixel_ptr, u16 w, u16 h, u8 fmt, u8 pad, i16 hx, i16 hy)`; `fmt=5` is raw (`+0x04` pixels), `fmt!=5` is Hudson-compressed (`+0x00 u32 byte_len`, `+0x04` stream) unpacked via `0x002fb000` scratchpad into **`VDP1.VRAM`** (`0x25C00000+`). |
| `10` | `0x060095E0(slot=10)` | SCSP sound/sequence/PCM transfer records staged into **`SCSP.RAM`** (`0x25A00000+`). |
| `3..6, 9` | Per-mode SH-2 callers | Validated pointer tables inside bank bounds; inner payload semantics remain open (see Section 8). |

---

## 5. Resident memory comparisons & two-run replay determinism

### 5.1 Deterministic `normal2` capture protocol (`HostResourceGate`-admitted)

Restoring `#27` `navigation-release-late` (`frame=10200`, Normal Game World 1-1 attract demo, `*(u8*)0x060C17DA = 2`), `6` bounded `"start"` presses (`180..195`, `3180..3195`, `5580..5595`, `10380..10395`, `12780..12795`, `16980..16995`; `actions_sha256: e09a07eb4b988a6c2b5a28cf7fbbca910d21713d83ab324ab01817772fae77ed`) advance `20,160` frames to `frame=30360`. Each Title Screen timeout (`0x06052E54`, `0x0384 = 900` 2-frame ticks = `1,800` frames) invokes `0x06052A00`, indexing 48-byte attract table `0x060B6BC0` up to `idx=12 -> (1, 1)` (Normal Game World 2 Stage 1 = `normal2`, `world_idx=1`).

Two independent fresh-process uninterrupted `20,160`-frame emulator executions (`normal2-run1` and `normal2-run2`) produced **100% bit-identical save states and memory regions**:
- `state_sha256` (`run1` == `run2`): `311c886c5bc2b0dc78d0d4ccdeb41044939b10ff334848f1691adf86b6d0e601`
- `MAIN.WorkRAML` (`1,048,576` B): `28dd2cb2a3b62cab7518ea383b85d3087be97f465d99be5c2668466cc2c00ba4`
- `MAIN.WorkRAMH` (`1,048,576` B): `03fdb2c3b68beeea47df06462c9cd64bcdedd9a3c9d2fdedaf89269c750c8f9f`
- `VDP1.VRAM` (`524,288` B): `c3b549e283a75e7e442905666708ba9623c0a6ab19ae84c523b15c123c281ead`
- `VDP2.VRAM` (`524,288` B): `30dd3e79fa455e031a35eb90afba12db3b1cda4dd58bf0650aa01af108ce72d0`
- `VDP2.CRAM` (`4,096` B): `7158f81c4981f9e2d2de8eaacba68e135a61c72a01cd7e85c2d3f29a7e14edab`
- `SCSP.RAM` (`524,288` B): `12318ca296702452899aa6dc21931973429e7b70dcfcf33e412e1e0983a5f3b4`

### 5.2 Bank-to-resident comparison summary

| Bank (`bank_id`) | Checkpoint (`frame`) | Raw `WorkRAML` match | `0x34` header unrelocated | Slot 0 (`VDP2.VRAM`) | Slot 1 (`VDP2.CRAM`) | Slot 7 (`WorkRAMH` `64x64` grids) | Slot 8 (`VDP1.VRAM` unique sprite blocks) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `base1` (`1`, USA) | `menu-release` (`10800`) | **`344,064 / 344,064` (`100.0%`)** | `true` (`52/52` B) | **`3/3` exact** (`16,352` B `@0x50000`, `13,312` B `@0x40000`, `6,368` B `@0x4e000`) | `3 / 36` CRAM (`1` shadow) | n/a (`NULL`) | **`623 / 841` blocks exact (`155,200` B)** + `1` `@0x002fb000` |
| `base1` (`1`, USA) | `navigation-release-late` (`10200`) | **`344,064 / 344,064` (`100.0%`)** | `true` (`52/52` B) | **`3/3` exact** (`36,032` B total) | `8 / 36` CRAM (`8` shadow) | n/a (`NULL`) | **`623 / 841` blocks exact (`155,200` B)** + `1` `@0x002fb000` |
| `base1` (`1`, USA) | `normal2-run1` (`30360`) | **`344,064 / 344,064` (`100.0%`)** | `true` (`52/52` B) | **`3/3` exact** (`36,032` B total) | `8 / 36` CRAM (`8` shadow) | n/a (`NULL`) | **`623 / 841` blocks exact (`155,200` B)** + `1` `@0x002fb000` |
| `normal2` (`5`, USA==JPN) | `normal2-run1` (`30360`) | **`573,440 / 573,440` (`100.0%`)** | `true` (`52/52` B) | **Block `#1` `107,264 / 107,264` (`100.0%`)** `@0x20000` (`#2, #3` for later World 2 sub-stages) | `4 / 18` CRAM (`4` shadow) | **Grids `#1, #2, #4` `8,192 / 8,192` (`100.0%`)** `@0x0f28b0`, `0x0f48b0`, `0x0f68b0` (`*(u32*)0x060D7E94`); Grid `#3` `8,178 / 8,192` (`99.83%`) | **`150 / 566` blocks exact (`70,144` B)** across `sm=0,1,2,3` |

*Note on partial sub-resource residency*: Each world bank bundles graphics, palettes, and stage grids for **all stages/bosses of that world** (`Slot 0` blocks `#2` and `#3` share `default_dest = 0x25e20000` with block `#1`; `Slot 7` holds `9` `8,192`-byte grids; `Slot 8` holds `566` unique sprite blocks across all World 2 enemies/bosses). Only the active Stage 2-1 sub-resources are unpacked into VRAM/WRAMH at `frame=30360`, while 100% of all `566` `normal2` and `841` `base1` sprite blocks decompress cleanly without bitstream overruns or invalid predictors.

---

## 6. Negative controls & falsification checks (`NC-01..NC-06`)

All 6 negative controls execute automatically in `compare-resident` and must reject as expected for CI verification to pass:

| Control ID | Falsification test | Observed outcome | Verdict |
| --- | --- | --- | --- |
| `NC-01` | Compare `normal2` (`0x00254000..0x002e0000`) against `menu-release` (where `openning` occupies `0x00254000`) | `match_ratio = 0.017779` (`1` incidental 32B VDP1 match) | Rejected (`PASS`) |
| `NC-02` | Compare `normal1` (`bank_id=4`) against resident `normal2` (`bank_id=5`) `WorkRAML` | `match_ratio = 0.042324` | Rejected (`PASS`) |
| `NC-03` | Decode real `normal2` Slot 8 `sb=3` sprite (`0x0029f804`) with contiguous 24-bit width packing instead of `0x0603434C`'s 3-byte bit-planar width reader | `832` differing bytes (`9c810e37…` vs true `ebc3cc69…`) | Rejected (`PASS`) |
| `NC-04` | Decode real `normal2` Slot 7 dual-ring stage grid `#1` (`0x0029453c`, `sm=1`) with a single ring and with 2-element pair interleaving | `3,711` B (single ring) and `1,115` B (pair interleave) corrupted | Rejected (`PASS`) |
| `NC-05` | Mutate `base1` Slot 0 `#1` predictor method to `20` (`>19`) and truncate payload to `24` B | Both raise `ArchiveError` (`invalid_predictor` & `truncated_stream`) | Rejected (`PASS`) |
| `NC-06` | Flip `1` bit in resident `WorkRAML+0x00100` and `1` bit in `VDP2.VRAM+0x50010` | Exact-match verifiers fail (`1` mismatch byte reported in each) | Rejected (`PASS`) |

---

## 7. Committed receipts & regeneration commands

| Committed receipt | SHA-256 |
| --- | --- |
| [`docs/restart/saturn-archive/usa-mk81070-v1003.kernel-directory.json`](../saturn-archive/usa-mk81070-v1003.kernel-directory.json) | `7fb543edca68969ed06658948cfafa649e61b7706fc814e7d6b2862df9fe2d55` |
| [`docs/restart/saturn-archive/japan-t14302g-v1000.kernel-directory.json`](../saturn-archive/japan-t14302g-v1000.kernel-directory.json) | `82b6aebd754e5e37d7fff60d35e7d49160bc8afde06b6d4d30883f55ac5c3d47` |
| [`docs/restart/saturn-archive/usa-mk81070-v1003.base1-decode.json`](../saturn-archive/usa-mk81070-v1003.base1-decode.json) | `657e524ec29ab6b0055a3aa695f288d24af669b015dfb56615434a8dcb3dd091` |
| [`docs/restart/saturn-archive/cross-region.normal2-decode.json`](../saturn-archive/cross-region.normal2-decode.json) | `8fc054ab3c1d693fc31437e03e4539460cb5619ae87b8f056ce5a45e37182976` |
| [`docs/restart/saturn-archive/base1-normal2-resident-comparison.json`](../saturn-archive/base1-normal2-resident-comparison.json) | `05c430723e1e39e3bb19c10ac99bb862e8021451493ee37973af494beed43319` |

```sh
# Offline CI unit suite + committed receipt verification (no private media/states needed)
python3 tools/saturn_archive/check.py
python3 tools/saturn_archive/cli.py verify \
  --directory docs/restart/saturn-archive/usa-mk81070-v1003.kernel-directory.json \
  --directory docs/restart/saturn-archive/japan-t14302g-v1000.kernel-directory.json \
  --bank docs/restart/saturn-archive/usa-mk81070-v1003.base1-decode.json \
  --bank docs/restart/saturn-archive/cross-region.normal2-decode.json \
  --comparison docs/restart/saturn-archive/base1-normal2-resident-comparison.json
```

Full read-only regeneration commands from `/home/dev/Sega-Saturn-BIOS` and private checkpoints are documented in [`tools/saturn_archive/README.md`](../../../tools/saturn_archive/README.md#usage).

---

## 8. Explicit remaining unknowns

1. **Slots `3, 4, 5, 6, 9` inner record semantics**: Pointer-table bounds inside `base1` and `normal2` are indexed and verified in-bounds, but the per-scene SH-2 consumers (likely sprite animation scripts, object spawn lists, and stage event tables) are not yet decoded.
2. **SCSP binary transfer headers (`0x060095E0`)**: `Slot 10` in `s_*` / world banks and polymorphic `Slot 2` in stage banks (`"DSP01e.EXB"`) transfer payloads into `SCSP.RAM` (`0x25A00000+`), proven via the 256-byte `s_nor2` probe at `SCSP.RAM+0x0b006`, but full sequence/tone/PCM record decoding remains open for `RSAT-008`.
3. **USA-only headerless entries (`bank_id=23` at `0x002da000`, `bank_id=41..43` at `0x002fb000`)**: Bounded and hashed in the USA kernel directory receipt, but their runtime callers (likely USA NetLink/localization or voice sub-tables) were not exercised in Normal Game attract/stage flows.
4. **Dynamic VDP2 plane destination selection**: `Slot 0` entries with `default_dest == 0x00000000` and `Slot 2` compressed tilemaps receive their target `VDP2.VRAM` plane addresses from scene-specific SH-2 callers rather than from the `0x34` bank header.
