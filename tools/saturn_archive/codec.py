"""Hudson Predictive Ring/Delta Codec and bank slot unpackers derived from 0KRNL.BIN.

Disassembly provenance (USA MK-81070 V1.003 BOMSS/0KRNL.BIN, load base 0x06006000):
- Direct buffer decompressor:      0x0603443C (src, dst, byte_len)
- Streaming 4-byte init / read:    0x0603461C (src) / 0x0603469E (want_bytes)
- Selector bit-readers (1..4 bit): 0x060B53B4 -> 0x060342F8, 0x06034322, 0x0603434C (3-byte bit-planar), 0x060343BA
- Stream mode table (0..4):        0x060B53C8 (u8 single/dual, u16 single/dual, u32 single)
- 20-entry predictor tables:       0x060B52C4 (u8), 0x060B5314 (u16), 0x060B5364 (u32)
- Bank slot unpackers:
    Slot 0 (VDP2 patterns):        0x06009470
    Slot 1 (VDP2 CRAM palettes):   0x06008E06
    Slot 2 (VDP2 tilemaps):        0x060094E2
    Slot 7 (stage collision grid): 0x0600C502
    Slot 8 (VDP1 sprite records):  0x06068BDC / 0x06068B86
"""

from __future__ import annotations

import hashlib
import struct
from typing import Any

from . import ArchiveError

# 20-entry predictor catalog (codes 0..19) from 0x06033DF0..0x060342F6:
#   0:      literal element read from stream (1, 2, or 4 big-endian bytes)
#   1..7:   ring[(pos - 1) & ring_mask] + {0, 1, 2, 4, 8, 16, 32}
#   8..13:  ring[(pos - 1) & ring_mask] - {1, 2, 4, 8, 16, 32}
#   14..19: ring[(pos - dist) & ring_mask] for dist in {2, 4, 8, 16, 32, 64}
DELTAS_FROM_PREV: dict[int, int] = {
    1: 0,
    2: 1,
    3: 2,
    4: 4,
    5: 8,
    6: 16,
    7: 32,
    8: -1,
    9: -2,
    10: -4,
    11: -8,
    12: -16,
    13: -32,
}

LOOKBACK_DISTANCES: dict[int, int] = {
    14: 2,
    15: 4,
    16: 8,
    17: 16,
    18: 32,
    19: 64,
}

# 5-entry stream mode dispatch table at 0x060B53C8..0x060B5417:
#   mode -> (elem_bytes, elem_mask, ring_mask, dual_ring)
STREAM_MODES: dict[int, tuple[int, int, int, bool]] = {
    0: (1, 0xFF, 0x1FF, False),        # u8,  single 512-entry ring
    1: (1, 0xFF, 0x0FF, True),         # u8,  dual interleaved 2x256-entry rings
    2: (2, 0xFFFF, 0x0FF, False),      # u16, single 256-entry ring
    3: (2, 0xFFFF, 0x07F, True),       # u16, dual interleaved 2x128-entry rings
    4: (4, 0xFFFFFFFF, 0x07F, False),  # u32, single 128-entry ring
}


def hudson_decompress(
    src: bytes,
    start_off: int,
    out_len: int,
    *,
    streaming_4byte: bool = True,
    planar_3bit: bool = True,
    dual_ring_enabled: bool = True,
    pair_interleave_falsification: bool = False,
) -> tuple[bytes, int, dict[str, Any]]:
    """Decode `out_len` bytes from `src[start_off:]` using 0KRNL.BIN's predictive ring/delta codec.

    The optional `planar_3bit`, `dual_ring_enabled`, and `pair_interleave_falsification` flags
    default to exact hardware/kernel behavior and exist strictly for negative-control falsification.
    """
    if start_off < 0 or start_off > len(src):
        raise ArchiveError(f"Stream start offset {start_off} out of bounds for buffer of {len(src)} bytes")
    if out_len < 0:
        raise ArchiveError(f"Negative output length: {out_len}")
    if out_len == 0:
        return b"", 0, {
            "selector_bits": None,
            "stream_mode": None,
            "elem_bytes": None,
            "dual_ring": False,
            "methods": [],
        }

    pos = start_off
    if pos >= len(src):
        raise ArchiveError("Truncated Hudson stream header: missing selector_bits")
    selector_bits = src[pos]
    pos += 1

    if selector_bits == 0:
        if pos + out_len > len(src):
            raise ArchiveError(
                f"Truncated raw Hudson stream: need {out_len} bytes at +0x{pos:x}, have {len(src) - pos}"
            )
        raw = src[pos : pos + out_len]
        if streaming_4byte:
            padded = ((out_len + 3) // 4) * 4
            consumed = 1 + min(padded, len(src) - pos)
        else:
            consumed = 1 + out_len
        return raw, consumed, {
            "selector_bits": 0,
            "stream_mode": None,
            "elem_bytes": 1,
            "dual_ring": False,
            "methods": [0],
        }

    if selector_bits not in (1, 2, 3, 4):
        raise ArchiveError(f"Invalid Hudson selector_bits={selector_bits} (expected 0..4)")
    if pos >= len(src):
        raise ArchiveError("Truncated Hudson stream header: missing stream_mode")
    stream_mode = src[pos]
    pos += 1
    if stream_mode not in STREAM_MODES:
        raise ArchiveError(f"Invalid Hudson stream_mode={stream_mode} (expected 0..4)")

    elem_bytes, elem_mask, ring_mask, mode_dual = STREAM_MODES[stream_mode]
    dual_ring = mode_dual and dual_ring_enabled
    if mode_dual and not dual_ring_enabled:
        # Falsification control: collapse 2xN rings into single 2N ring
        ring_mask = ((ring_mask + 1) * 2) - 1

    num_methods = 1 << selector_bits
    methods = [0]
    for _ in range(1, num_methods):
        if pos >= len(src):
            raise ArchiveError("Truncated Hudson method dispatch table")
        m = src[pos]
        pos += 1
        if m > 19:
            raise ArchiveError(f"Invalid Hudson predictor method code {m} > 19")
        methods.append(m)

    ring_a = [0] * (ring_mask + 1)
    ring_b = [0] * (ring_mask + 1)
    rpos_a = 0
    rpos_b = 0

    bit_phase = 0
    s0 = s1 = s2 = 0
    packed24 = 0

    def read_selector() -> int:
        nonlocal pos, bit_phase, s0, s1, s2, packed24
        if selector_bits == 1:
            if bit_phase == 0:
                if pos >= len(src):
                    raise ArchiveError("Truncated 1-bit selector stream")
                s0 = src[pos]
                pos += 1
            sel = s0 & 1
            s0 >>= 1
            bit_phase = (bit_phase + 1) & 7
            return sel
        if selector_bits == 2:
            if bit_phase == 0:
                if pos >= len(src):
                    raise ArchiveError("Truncated 2-bit selector stream")
                s0 = src[pos]
                pos += 1
            sel = s0 & 3
            s0 >>= 2
            bit_phase = (bit_phase + 2) & 7
            return sel
        if selector_bits == 3:
            if bit_phase == 0:
                if pos + 3 > len(src):
                    raise ArchiveError("Truncated 3-bit selector stream")
                if planar_3bit:
                    s0 = src[pos]
                    s1 = src[pos + 1]
                    s2 = src[pos + 2]
                else:
                    packed24 = src[pos] | (src[pos + 1] << 8) | (src[pos + 2] << 16)
                pos += 3
            if planar_3bit:
                sel = ((s2 & 1) << 2) | ((s1 & 1) << 1) | (s0 & 1)
                s0 >>= 1
                s1 >>= 1
                s2 >>= 1
            else:
                sel = packed24 & 7
                packed24 >>= 3
            bit_phase = (bit_phase + 1) & 7
            return sel
        # selector_bits == 4
        if bit_phase == 0:
            if pos >= len(src):
                raise ArchiveError("Truncated 4-bit selector stream")
            s0 = src[pos]
            pos += 1
        sel = s0 & 0xF
        s0 >>= 4
        bit_phase = (bit_phase + 4) & 7
        return sel

    def read_literal() -> int:
        nonlocal pos
        if pos + elem_bytes > len(src):
            raise ArchiveError(f"Truncated {elem_bytes}-byte literal in Hudson stream")
        if elem_bytes == 1:
            val = src[pos]
        elif elem_bytes == 2:
            val = struct.unpack_from(">H", src, pos)[0]
        else:
            val = struct.unpack_from(">I", src, pos)[0]
        pos += elem_bytes
        return val

    if streaming_4byte:
        total_bytes_to_decode = ((out_len + 3) // 4) * 4
        num_elements = total_bytes_to_decode // elem_bytes
    else:
        num_elements = (out_len + elem_bytes - 1) // elem_bytes

    out = bytearray()
    for idx in range(num_elements):
        if pair_interleave_falsification:
            use_ring_b = dual_ring and (((idx >> 1) & 1) == 0)
        else:
            use_ring_b = dual_ring and ((idx & 1) == 0)
        if use_ring_b:
            ring = ring_b
            rpos = rpos_b
        else:
            ring = ring_a
            rpos = rpos_a

        sel = read_selector()
        code = methods[sel]
        if code == 0:
            val = read_literal()
        elif code in DELTAS_FROM_PREV:
            val = (ring[(rpos - 1) & ring_mask] + DELTAS_FROM_PREV[code]) & elem_mask
        else:
            dist = LOOKBACK_DISTANCES[code]
            val = ring[(rpos - dist) & ring_mask]

        ring[rpos] = val
        rpos = (rpos + 1) & ring_mask
        if use_ring_b:
            rpos_b = rpos
        else:
            rpos_a = rpos

        if elem_bytes == 1:
            out.append(val)
        elif elem_bytes == 2:
            out.extend(struct.pack(">H", val))
        else:
            out.extend(struct.pack(">I", val))

    return bytes(out[:out_len]), pos - start_off, {
        "selector_bits": selector_bits,
        "stream_mode": stream_mode,
        "elem_bytes": elem_bytes,
        "dual_ring": dual_ring,
        "methods": methods,
    }


def hudson_encode_synthetic(
    selector_bits: int,
    stream_mode: int,
    methods: list[int],
    steps: list[tuple[int, int | None]],
) -> bytes:
    """Deterministic synthetic encoder for unit tests (zero copyrighted bytes).

    `steps` is a list of `(selector_index, optional_literal_value)` pairs.
    """
    if selector_bits == 0:
        out = bytearray([0])
        for _, lit in steps:
            if lit is None:
                raise ArchiveError("selector_bits=0 requires literal byte values")
            out.append(lit & 0xFF)
        return bytes(out)
    if selector_bits not in (1, 2, 3, 4):
        raise ArchiveError(f"Invalid selector_bits={selector_bits}")
    if stream_mode not in STREAM_MODES:
        raise ArchiveError(f"Invalid stream_mode={stream_mode}")
    expected_methods = 1 << selector_bits
    if len(methods) != expected_methods or methods[0] != 0:
        raise ArchiveError(f"Expected {expected_methods} methods starting with 0")

    elem_bytes = STREAM_MODES[stream_mode][0]
    out = bytearray([selector_bits, stream_mode, *methods[1:]])
    group_size = {1: 8, 2: 4, 3: 8, 4: 2}[selector_bits]

    for base in range(0, len(steps), group_size):
        chunk = steps[base : base + group_size]
        sels = [s for s, _ in chunk] + [0] * (group_size - len(chunk))
        if selector_bits == 1:
            b = sum((s & 1) << k for k, s in enumerate(sels))
            out.append(b)
        elif selector_bits == 2:
            b = sum((s & 3) << (2 * k) for k, s in enumerate(sels))
            out.append(b)
        elif selector_bits == 3:
            b0 = sum(((s >> 0) & 1) << k for k, s in enumerate(sels))
            b1 = sum(((s >> 1) & 1) << k for k, s in enumerate(sels))
            b2 = sum(((s >> 2) & 1) << k for k, s in enumerate(sels))
            out.extend([b0, b1, b2])
        else:
            b = (sels[0] & 0xF) | ((sels[1] & 0xF) << 4)
            out.append(b)

        for sel, lit in chunk:
            if methods[sel] == 0:
                if lit is None:
                    raise ArchiveError("Literal step missing value")
                if elem_bytes == 1:
                    out.append(lit & 0xFF)
                elif elem_bytes == 2:
                    out.extend(struct.pack(">H", lit & 0xFFFF))
                else:
                    out.extend(struct.pack(">I", lit & 0xFFFFFFFF))
    return bytes(out)


def decode_slot0_entry(bank_bytes: bytes, load_base: int, entry_ptr: int) -> dict[str, Any]:
    """Unpack a Slot 0 VDP2 pattern/character sub-resource (0x06009470)."""
    roff = entry_ptr - load_base
    if roff < 0x34 or roff + 8 > len(bank_bytes):
        raise ArchiveError(f"Slot 0 entry pointer 0x{entry_ptr:08x} out of bounds")
    default_dest, flags_len = struct.unpack_from(">II", bank_bytes, roff)
    compressed = bool(flags_len & 0x80000000)
    out_len = flags_len & 0x7FFFFFFF
    if compressed:
        decoded, consumed, meta = hudson_decompress(bank_bytes, roff + 8, out_len, streaming_4byte=True)
    else:
        if roff + 8 + out_len > len(bank_bytes):
            raise ArchiveError(f"Uncompressed Slot 0 entry at 0x{entry_ptr:08x} overflows bank")
        decoded = bank_bytes[roff + 8 : roff + 8 + out_len]
        consumed = out_len
        meta = {"selector_bits": None, "stream_mode": None, "elem_bytes": 1, "dual_ring": False, "methods": []}

    return {
        "slot": 0,
        "entry_ptr_hex": f"0x{entry_ptr:08x}",
        "bank_rel_offset": roff,
        "default_dest_hex": f"0x{default_dest:08x}",
        "default_dest": default_dest,
        "compressed": compressed,
        "compressed_stream_bytes": consumed,
        "decoded_bytes": len(decoded),
        "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
        "codec": meta,
        "_raw_decoded": decoded,
    }


def decode_slot1_palette(bank_bytes: bytes, load_base: int, entry_ptr: int) -> dict[str, Any]:
    """Unpack a Slot 1 RGB555 CRAM palette sub-resource (0x06008E06)."""
    roff = entry_ptr - load_base
    if roff < 0x34 or roff + 4 > len(bank_bytes):
        raise ArchiveError(f"Slot 1 palette pointer 0x{entry_ptr:08x} out of bounds")
    cram_byte_offset, color_count = struct.unpack_from(">HH", bank_bytes, roff)
    byte_len = color_count * 2
    if roff + 4 + byte_len > len(bank_bytes):
        raise ArchiveError(f"Slot 1 palette at 0x{entry_ptr:08x} overflows bank ({color_count} colors)")
    decoded = bank_bytes[roff + 4 : roff + 4 + byte_len]
    return {
        "slot": 1,
        "entry_ptr_hex": f"0x{entry_ptr:08x}",
        "bank_rel_offset": roff,
        "cram_byte_offset": cram_byte_offset,
        "cram_byte_offset_hex": f"0x{cram_byte_offset:04x}",
        "color_count": color_count,
        "compressed": False,
        "decoded_bytes": byte_len,
        "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
        "_raw_decoded": decoded,
    }


def decode_slot2_tilemap(bank_bytes: bytes, load_base: int, entry_ptr: int) -> dict[str, Any]:
    """Unpack a Slot 2 VDP2 tilemap/name-table sub-resource (0x060094E2)."""
    roff = entry_ptr - load_base
    if roff < 0x34 or roff + 6 > len(bank_bytes):
        raise ArchiveError(f"Slot 2 tilemap pointer 0x{entry_ptr:08x} out of bounds")
    wh, xy, flags = struct.unpack_from(">HHH", bank_bytes, roff)
    width = wh >> 8
    height = wh & 0xFF
    if width == 0 or height == 0:
        raise ArchiveError(
            f"Slot 2 entry at 0x{entry_ptr:08x} has zero tilemap dimension ({width}x{height}); "
            "likely a 0x060095E0 SCSP command record rather than a 0x060094E2 VDP2 tilemap"
        )
    x_pos = xy >> 8
    y_pos = xy & 0xFF
    compressed = (flags & 0x000F) != 0
    out_len = width * height * 2
    if compressed:
        decoded, consumed, meta = hudson_decompress(bank_bytes, roff + 6, out_len, streaming_4byte=True)
    else:
        if roff + 6 + out_len > len(bank_bytes):
            raise ArchiveError(f"Uncompressed Slot 2 tilemap at 0x{entry_ptr:08x} overflows bank")
        decoded = bank_bytes[roff + 6 : roff + 6 + out_len]
        consumed = out_len
        meta = {"selector_bits": None, "stream_mode": None, "elem_bytes": 2, "dual_ring": False, "methods": []}

    return {
        "slot": 2,
        "entry_ptr_hex": f"0x{entry_ptr:08x}",
        "bank_rel_offset": roff,
        "width_cells": width,
        "height_cells": height,
        "default_x_cell": x_pos,
        "default_y_cell": y_pos,
        "flags_hex": f"0x{flags:04x}",
        "compressed": compressed,
        "compressed_stream_bytes": consumed,
        "decoded_bytes": len(decoded),
        "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
        "codec": meta,
        "_raw_decoded": decoded,
    }


def decode_slot7_grid(bank_bytes: bytes, load_base: int, entry_ptr: int) -> dict[str, Any]:
    """Unpack a Slot 7 stage tile/collision grid sub-resource (0x0600C502)."""
    roff = entry_ptr - load_base
    if roff < 0x34 or roff + 2 > len(bank_bytes):
        raise ArchiveError(f"Slot 7 grid pointer 0x{entry_ptr:08x} out of bounds")
    dims = bank_bytes[roff]
    cols = dims & 0xF0
    rows = (dims & 0x0F) << 4
    out_len = cols * rows * 2
    decoded, consumed, meta = hudson_decompress(bank_bytes, roff + 1, out_len, streaming_4byte=True)
    return {
        "slot": 7,
        "entry_ptr_hex": f"0x{entry_ptr:08x}",
        "bank_rel_offset": roff,
        "cols": cols,
        "rows": rows,
        "row_stride_bytes_runtime": 0x80,
        "compressed": True,
        "compressed_stream_bytes": consumed,
        "decoded_bytes": len(decoded),
        "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
        "codec": meta,
        "_raw_decoded": decoded,
    }


def decode_slot8_sprites(
    bank_bytes: bytes,
    load_base: int,
    slot8_ptr: int,
    slot8_stop_off: int,
) -> dict[str, Any]:
    """Unpack Slot 8 VDP1 sprite descriptors and unique pixel blocks (0x06068BDC / 0x06068B86)."""
    roff = slot8_ptr - load_base
    if roff < 0x34 or roff + 8 > len(bank_bytes):
        raise ArchiveError(f"Slot 8 header pointer 0x{slot8_ptr:08x} out of bounds")
    chr_tbl_ptr, meta_tbl_ptr = struct.unpack_from(">II", bank_bytes, roff)
    end_addr = load_base + len(bank_bytes)
    if not (load_base + 0x34 <= chr_tbl_ptr < meta_tbl_ptr < end_addr):
        raise ArchiveError(
            f"Slot 8 two-table header invalid at 0x{slot8_ptr:08x}: "
            f"chr=0x{chr_tbl_ptr:08x}, meta=0x{meta_tbl_ptr:08x}"
        )

    # Read 1-based sprite descriptor pointers from chr_tbl_ptr up to meta_tbl_ptr (or earliest target)
    off = chr_tbl_ptr - load_base
    min_target = min(meta_tbl_ptr - load_base, slot8_stop_off)
    desc_ptrs: list[int] = []
    while off + 4 <= min_target:
        val = struct.unpack_from(">I", bank_bytes, off)[0]
        if val == 0:
            desc_ptrs.append(0)
        elif load_base + 0x34 <= val < end_addr:
            desc_ptrs.append(val)
            rel = val - load_base
            if rel > off and rel < min_target:
                min_target = rel
        else:
            break
        off += 4
    while desc_ptrs and desc_ptrs[-1] == 0:
        desc_ptrs.pop()

    unique_blocks: dict[int, dict[str, Any]] = {}
    null_descriptors = 0
    for desc_ptr in desc_ptrs:
        if desc_ptr == 0:
            null_descriptors += 1
            continue
        doff = desc_ptr - load_base
        if doff < 0x34 or doff + 20 > len(bank_bytes):
            raise ArchiveError(f"Slot 8 sprite descriptor 0x{desc_ptr:08x} out of bounds")
        pix_ptr = struct.unpack_from(">I", bank_bytes, doff + 16)[0]
        if pix_ptr == 0:
            null_descriptors += 1
            continue
        if pix_ptr in unique_blocks:
            unique_blocks[pix_ptr]["descriptor_ref_count"] += 1
            continue
        poff = pix_ptr - load_base
        if poff < 0x34 or poff + 4 > len(bank_bytes):
            raise ArchiveError(f"Slot 8 sprite pixel pointer 0x{pix_ptr:08x} out of bounds")
        byte_len, fmt = struct.unpack_from(">HH", bank_bytes, poff)
        if fmt == 5:
            if poff + 4 + byte_len > len(bank_bytes):
                raise ArchiveError(f"Raw fmt=5 sprite block at 0x{pix_ptr:08x} overflows bank")
            decoded = bank_bytes[poff + 4 : poff + 4 + byte_len]
            consumed = byte_len
            compressed = False
            meta: dict[str, Any] = {
                "selector_bits": None,
                "stream_mode": None,
                "elem_bytes": 1,
                "dual_ring": False,
                "methods": [],
            }
        else:
            decoded, consumed, meta = hudson_decompress(bank_bytes, poff + 4, byte_len, streaming_4byte=False)
            compressed = True

        unique_blocks[pix_ptr] = {
            "pixel_ptr_hex": f"0x{pix_ptr:08x}",
            "bank_rel_offset": poff,
            "format_code": fmt,
            "compressed": compressed,
            "compressed_stream_bytes": consumed,
            "decoded_bytes": len(decoded),
            "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
            "descriptor_ref_count": 1,
            "codec": meta,
            "_raw_decoded": decoded,
        }

    blocks_sorted = [unique_blocks[k] for k in sorted(unique_blocks)]
    mode_hist: dict[str, int] = {}
    for blk in blocks_sorted:
        if blk["compressed"]:
            key = f"sb={blk['codec']['selector_bits']},sm={blk['codec']['stream_mode']}"
        else:
            key = "raw_fmt5"
        mode_hist[key] = mode_hist.get(key, 0) + 1

    return {
        "slot8_header_ptr_hex": f"0x{slot8_ptr:08x}",
        "chr_table_ptr_hex": f"0x{chr_tbl_ptr:08x}",
        "meta_table_ptr_hex": f"0x{meta_tbl_ptr:08x}",
        "descriptor_count": len(desc_ptrs),
        "null_descriptor_count": null_descriptors,
        "unique_pixel_block_count": len(blocks_sorted),
        "compressed_block_count": sum(1 for b in blocks_sorted if b["compressed"]),
        "raw_fmt5_block_count": sum(1 for b in blocks_sorted if not b["compressed"]),
        "total_compressed_stream_bytes": sum(b["compressed_stream_bytes"] for b in blocks_sorted),
        "total_decoded_bytes": sum(b["decoded_bytes"] for b in blocks_sorted),
        "mode_histogram": dict(sorted(mode_hist.items())),
        "blocks": blocks_sorted,
    }
