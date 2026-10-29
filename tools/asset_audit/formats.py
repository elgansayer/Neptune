"""Dependency-free binary header and structural decoders for asset auditing.

All inspectors read local bytes only and distinguish header-only metadata from
full container/stream verification. No external tools or network/model calls are used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import platform
import struct
from typing import Any
import xml.etree.ElementTree as ET
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

DECODER_VERSION = f"python-stdlib/{platform.python_version()}/zlib-{zlib.ZLIB_VERSION}"

# Color-type -> channel count in PNG IHDR
_PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
# Adam7 pass (x0, dx, y0, dy)
_ADAM7 = (
    (0, 8, 0, 8),
    (4, 8, 0, 8),
    (0, 4, 4, 8),
    (2, 4, 0, 4),
    (0, 2, 2, 4),
    (1, 2, 0, 2),
    (0, 1, 1, 2),
)


def _expected_png_raw_bytes(width: int, height: int, bit_depth: int, color_type: int, interlace: int) -> int:
    channels = _PNG_CHANNELS[color_type]
    bits_per_pixel = bit_depth * channels
    if interlace == 0:
        row_bytes = (width * bits_per_pixel + 7) // 8
        return height * (1 + row_bytes)
    total = 0
    for x0, dx, y0, dy in _ADAM7:
        pw = (width - x0 + dx - 1) // dx if width > x0 else 0
        ph = (height - y0 + dy - 1) // dy if height > y0 else 0
        if pw > 0 and ph > 0:
            row_bytes = (pw * bits_per_pixel + 7) // 8
            total += ph * (1 + row_bytes)
    return total


def inspect_png(path: Path, full_decode: bool = True) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 33 or data[:8] != PNG_SIGNATURE:
        return {
            "detected_format": "png",
            "decode_level": "full_stream" if full_decode else "header_only",
            "decoder": DECODER_VERSION,
            "valid": False,
            "error": "Invalid or truncated PNG signature",
        }
    if data[12:16] != b"IHDR":
        return {
            "detected_format": "png",
            "decode_level": "full_stream" if full_decode else "header_only",
            "decoder": DECODER_VERSION,
            "valid": False,
            "error": "First PNG chunk is not IHDR",
        }
    ihdr_len = struct.unpack(">I", data[8:12])[0]
    if ihdr_len != 13 or len(data) < 33:
        return {
            "detected_format": "png",
            "decode_level": "full_stream" if full_decode else "header_only",
            "decoder": DECODER_VERSION,
            "valid": False,
            "error": f"Invalid IHDR length: {ihdr_len}",
        }
    width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(">IIBBBBB", data[16:29])
    if width == 0 or height == 0 or color_type not in _PNG_CHANNELS or comp != 0 or filt != 0 or interlace not in (0, 1):
        return {
            "detected_format": "png",
            "decode_level": "full_stream" if full_decode else "header_only",
            "decoder": DECODER_VERSION,
            "valid": False,
            "error": "Unsupported or invalid PNG IHDR parameters",
        }
    base_info: dict[str, Any] = {
        "detected_format": "png",
        "decoder": DECODER_VERSION,
        "dimensions": [width, height],
        "bit_depth": bit_depth,
        "color_type": color_type,
        "interlace": interlace,
    }
    if not full_decode:
        base_info.update(decode_level="header_only", valid=True)
        return base_info

    offset = 8
    seen_iend = False
    idat_parts: list[bytes] = []
    palette_entries: int | None = None
    has_trns = False
    while offset < len(data):
        if offset + 12 > len(data):
            return {**base_info, "decode_level": "full_stream", "valid": False, "error": "Truncated PNG chunk header"}
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        ctype = data[offset + 4 : offset + 8]
        end_payload = offset + 8 + length
        if end_payload + 4 > len(data):
            return {
                **base_info,
                "decode_level": "full_stream",
                "valid": False,
                "error": f"Truncated PNG chunk {ctype.decode('latin1', errors='replace')}",
            }
        payload = data[offset + 8 : end_payload]
        expected_crc = struct.unpack(">I", data[end_payload : end_payload + 4])[0]
        actual_crc = zlib.crc32(data[offset + 4 : end_payload]) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            return {
                **base_info,
                "decode_level": "full_stream",
                "valid": False,
                "error": f"CRC mismatch in PNG chunk {ctype.decode('latin1', errors='replace')}",
            }
        offset = end_payload + 4
        if ctype == b"PLTE":
            if length == 0 or length % 3 != 0:
                return {**base_info, "decode_level": "full_stream", "valid": False, "error": "Invalid PLTE length"}
            palette_entries = length // 3
        elif ctype == b"tRNS":
            has_trns = True
        elif ctype == b"IDAT":
            idat_parts.append(payload)
        elif ctype == b"IEND":
            seen_iend = True
            if offset != len(data):
                return {**base_info, "decode_level": "full_stream", "valid": False, "error": "Trailing bytes after IEND"}
            break

    if not seen_iend or not idat_parts:
        return {**base_info, "decode_level": "full_stream", "valid": False, "error": "Missing IDAT or IEND chunk"}
    if color_type == 3 and palette_entries is None:
        return {**base_info, "decode_level": "full_stream", "valid": False, "error": "Indexed PNG missing PLTE chunk"}

    try:
        decomp = zlib.decompressobj()
        raw_len = 0
        for part in idat_parts:
            raw_len += len(decomp.decompress(part))
        raw_len += len(decomp.flush())
        if not decomp.eof or decomp.unused_data:
            return {
                **base_info,
                "decode_level": "full_stream",
                "valid": False,
                "error": "Incomplete or trailing bytes in PNG zlib stream",
            }
    except zlib.error as exc:
        return {**base_info, "decode_level": "full_stream", "valid": False, "error": f"PNG zlib decode failed: {exc}"}

    expected_raw = _expected_png_raw_bytes(width, height, bit_depth, color_type, interlace)
    if raw_len != expected_raw:
        return {
            **base_info,
            "decode_level": "full_stream",
            "valid": False,
            "error": f"Decompressed scanline byte count {raw_len} != expected {expected_raw}",
        }

    result = {
        **base_info,
        "decode_level": "full_stream",
        "valid": True,
        "has_trns": has_trns,
    }
    if palette_entries is not None:
        result["palette_entries"] = palette_entries
    return result


def inspect_sega_film(path: Path, size: int) -> dict[str, Any]:
    with path.open("rb") as stream:
        head = stream.read(64)
        if len(head) < 48 or head[:4] != b"FILM":
            return {"detected_format": "sega_film_cpk", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": "Truncated FILM header"}
        header_len = struct.unpack(">I", head[4:8])[0]
        version = head[8:12].decode("ascii", errors="replace")
        if header_len > size or head[16:20] != b"FDSC":
            return {
                "detected_format": "sega_film_cpk",
                "decode_level": "container_table",
                "decoder": DECODER_VERSION,
                "valid": False,
                "film_version": version,
                "error": "Header exceeds file size or missing FDSC chunk",
            }
        fdsc_len = struct.unpack(">I", head[20:24])[0]
        vcodec = head[24:28].decode("ascii", errors="replace")
        height, width = struct.unpack(">II", head[28:36])
        bpp, audio_ch, audio_bits = head[36], head[37], head[38]
        audio_hz = struct.unpack(">H", head[40:42])[0]
        stream.seek(0)
        full_header = stream.read(header_len)

    stab_pos = 16 + fdsc_len
    if stab_pos + 16 > len(full_header) or full_header[stab_pos : stab_pos + 4] != b"STAB":
        return {
            "detected_format": "sega_film_cpk",
            "decode_level": "container_table",
            "decoder": DECODER_VERSION,
            "valid": False,
            "error": "Missing or truncated STAB sample table",
        }
    stab_len, timebase_hz, sample_count = struct.unpack(">III", full_header[stab_pos + 4 : stab_pos + 16])
    table_start = stab_pos + 16
    table_end = table_start + sample_count * 16
    if table_end > len(full_header) or stab_len < 16 + sample_count * 16:
        return {
            "detected_format": "sega_film_cpk",
            "decode_level": "container_table",
            "decoder": DECODER_VERSION,
            "valid": False,
            "error": "STAB sample count overflows FILM header",
        }
    max_end = header_len
    for idx in range(sample_count):
        rec_off = table_start + idx * 16
        rel_off, sample_len = struct.unpack(">II", full_header[rec_off : rec_off + 8])
        # Mask top flags if any exist in offset (in FILM 1.04 offset is unsigned 32-bit from data start)
        end_byte = header_len + rel_off + sample_len
        if end_byte > max_end:
            max_end = end_byte
    info: dict[str, Any] = {
        "detected_format": "sega_film_cpk",
        "decode_level": "container_table",
        "decoder": DECODER_VERSION,
        "film_version": version,
        "video_codec": vcodec,
        "dimensions": [width, height],
        "video_bpp": bpp,
        "audio_channels": audio_ch,
        "audio_bits": audio_bits,
        "audio_hz": audio_hz,
        "timebase_ticks": timebase_hz,
        "sample_count": sample_count,
        "expected_min_bytes": max_end,
    }
    if max_end > size:
        info["valid"] = False
        info["error"] = f"Truncated Sega FILM payload: STAB requires {max_end} bytes, file has {size} bytes"
    else:
        info["valid"] = True
    return info


def _parse_ieee_extended_80(raw: bytes) -> float:
    expon, hi, lo = struct.unpack(">HII", raw)
    sign = -1.0 if (expon & 0x8000) else 1.0
    expon &= 0x7FFF
    if expon == 0 and hi == 0 and lo == 0:
        return 0.0
    if expon == 0x7FFF:
        return math.nan
    mantissa = hi * (2.0 ** 32) + lo
    return sign * math.ldexp(mantissa, expon - 16383 - 63)


def inspect_aiff(path: Path, size: int) -> dict[str, Any]:
    with path.open("rb") as stream:
        header = stream.read(min(size, 4096))
    if len(header) < 12 or header[:4] != b"FORM" or header[8:12] not in (b"AIFF", b"AIFC"):
        return {"detected_format": "aiff", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": "Invalid AIFF header"}
    form_size = struct.unpack(">I", header[4:8])[0]
    expected_total = form_size + 8
    offset = 12
    channels = None
    frames = None
    bits = None
    rate_hz = None
    while offset + 8 <= len(header):
        cid = header[offset : offset + 4]
        clen = struct.unpack(">I", header[offset + 4 : offset + 8])[0]
        payload = header[offset + 8 : offset + 8 + clen]
        if cid == b"COMM" and len(payload) >= 18:
            channels, frames, bits = struct.unpack(">hIh", payload[:8])
            rate_hz = round(_parse_ieee_extended_80(payload[8:18]), 2)
            break
        offset += 8 + clen + (clen & 1)
    valid = expected_total <= size and channels is not None and channels > 0
    result: dict[str, Any] = {
        "detected_format": "aiff",
        "decode_level": "container_header",
        "decoder": DECODER_VERSION,
        "valid": valid,
        "declared_bytes": expected_total,
    }
    if channels is not None:
        result.update(audio_channels=channels, sample_frames=frames, audio_bits=bits, audio_hz=rate_hz)
    if not valid:
        result["error"] = f"Truncated AIFF or missing COMM chunk (declared {expected_total} bytes, actual {size})"
    return result


def inspect_bmp(path: Path, size: int) -> dict[str, Any]:
    with path.open("rb") as stream:
        head = stream.read(54)
    if len(head) < 26 or head[:2] != b"BM":
        return {"detected_format": "bmp", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": "Truncated BMP header"}
    declared_size = struct.unpack("<I", head[2:6])[0]
    dib_size = struct.unpack("<I", head[14:18])[0]
    if dib_size >= 40 and len(head) >= 30:
        width, height = struct.unpack("<ii", head[18:26])
        bpp = struct.unpack("<H", head[28:30])[0]
    elif dib_size == 12:
        width, height, _, bpp = struct.unpack("<HHHH", head[18:26])
    else:
        return {"detected_format": "bmp", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": f"Unsupported BMP DIB header size {dib_size}"}
    valid = width > 0 and height != 0 and declared_size <= size
    res: dict[str, Any] = {
        "detected_format": "bmp",
        "decode_level": "container_header",
        "decoder": DECODER_VERSION,
        "valid": valid,
        "dimensions": [width, abs(height)],
        "bit_depth": bpp,
    }
    if not valid:
        res["error"] = f"Invalid or truncated BMP (declared {declared_size} bytes, actual {size})"
    return res


def inspect_gif(path: Path, size: int) -> dict[str, Any]:
    with path.open("rb") as stream:
        head = stream.read(13)
        if size >= 1:
            stream.seek(size - 1)
            tail = stream.read(1)
        else:
            tail = b""
    if len(head) < 13 or head[:6] not in (b"GIF87a", b"GIF89a"):
        return {"detected_format": "gif", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": "Invalid GIF header"}
    width, height = struct.unpack("<HH", head[6:10])
    valid = width > 0 and height > 0 and tail == b";"
    res: dict[str, Any] = {
        "detected_format": "gif",
        "decode_level": "container_header",
        "decoder": DECODER_VERSION,
        "valid": valid,
        "dimensions": [width, height],
    }
    if not valid:
        res["error"] = "Truncated GIF missing 0x3B trailer or zero dimensions"
    return res


def inspect_jpeg(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return {"detected_format": "jpeg", "decode_level": "container_header", "decoder": DECODER_VERSION, "valid": False, "error": "Missing JPEG SOI"}
    idx = 2
    dims = None
    seen_eoi = data[-2:] == b"\xff\xd9"
    while idx + 4 <= len(data):
        if data[idx] != 0xFF:
            idx += 1
            continue
        while idx < len(data) and data[idx] == 0xFF:
            idx += 1
        if idx >= len(data):
            break
        marker = data[idx]
        idx += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            if marker == 0xD9:
                seen_eoi = True
                break
            continue
        if idx + 2 > len(data):
            break
        seg_len = struct.unpack(">H", data[idx : idx + 2])[0]
        if seg_len < 2 or idx + seg_len > len(data):
            break
        if marker in (0xC0, 0xC1, 0xC2) and seg_len >= 7:
            height, width = struct.unpack(">HH", data[idx + 3 : idx + 7])
            dims = [width, height]
            break
        idx += seg_len
    valid = dims is not None and dims[0] > 0 and dims[1] > 0 and seen_eoi
    res: dict[str, Any] = {"detected_format": "jpeg", "decode_level": "container_header", "decoder": DECODER_VERSION, "valid": valid}
    if dims is not None:
        res["dimensions"] = dims
    if not valid:
        res["error"] = "Missing JPEG SOF dimensions or EOI marker"
    return res


def inspect_xcf(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        head = stream.read(26)
    if len(head) < 26 or head[:9] != b"gimp xcf " or head[13:14] != b"\x00":
        return {"detected_format": "xcf", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": "Invalid GIMP XCF header"}
    width, height, base_type = struct.unpack(">III", head[14:26])
    valid = width > 0 and height > 0
    return {
        "detected_format": "xcf",
        "decode_level": "header_only",
        "decoder": DECODER_VERSION,
        "valid": valid,
        "xcf_version": head[9:13].decode("ascii", errors="replace"),
        "dimensions": [width, height],
        "base_color_mode": base_type,
    }


def inspect_avif(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 16 or data[4:8] != b"ftyp" or data[8:12] not in (b"avif", b"avis", b"mif1"):
        return {"detected_format": "avif", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": "Invalid ISO-BMFF AVIF ftyp box"}
    # Search for 'ispe' (ImageSpatialExtentsProperty: 4-byte version/flags + uint32 width + uint32 height)
    dims = None
    pos = data.find(b"ispe")
    if pos >= 4 and pos + 16 <= len(data):
        box_len = struct.unpack(">I", data[pos - 4 : pos])[0]
        if box_len >= 20:
            w, h = struct.unpack(">II", data[pos + 8 : pos + 16])
            if w > 0 and h > 0:
                dims = [w, h]
    res: dict[str, Any] = {
        "detected_format": "avif",
        "decode_level": "container_header",
        "decoder": DECODER_VERSION,
        "valid": dims is not None,
    }
    if dims is not None:
        res["dimensions"] = dims
    else:
        res["error"] = "AVIF missing readable ispe dimensions"
    return res


def inspect_ogg(path: Path, size: int) -> dict[str, Any]:
    with path.open("rb") as stream:
        head = stream.read(min(size, 256))
    if len(head) < 27 or head[:4] != b"OggS":
        return {"detected_format": "ogg_vorbis", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": "Missing OggS capture pattern"}
    vorbis_pos = head.find(b"\x01vorbis")
    res: dict[str, Any] = {"detected_format": "ogg_vorbis", "decode_level": "container_header", "decoder": DECODER_VERSION, "valid": True}
    if vorbis_pos != -1 and vorbis_pos + 16 <= len(head):
        channels = head[vorbis_pos + 11]
        rate_hz = struct.unpack("<I", head[vorbis_pos + 12 : vorbis_pos + 16])[0]
        res.update(audio_channels=channels, audio_hz=rate_hz)
    return res


def inspect_au(path: Path, size: int) -> dict[str, Any]:
    with path.open("rb") as stream:
        head = stream.read(64)
    if len(head) < 24 or head[:4] not in (b".snd", b"dns."):
        return {"detected_format": "audacity_au", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": "Invalid AU magic"}
    endian = ">" if head[:4] == b".snd" else "<"
    data_offset, _, encoding, rate_hz, channels = struct.unpack(endian + "IIIII", head[4:24])
    is_audacity = b"AudacityBlockFile" in head[24:]
    valid = data_offset <= size and channels > 0 and rate_hz > 0
    res: dict[str, Any] = {
        "detected_format": "audacity_au" if is_audacity else "sun_au",
        "decode_level": "header_only",
        "decoder": DECODER_VERSION,
        "valid": valid,
        "audio_channels": channels,
        "audio_hz": rate_hz,
        "au_encoding": encoding,
    }
    if not valid:
        res["error"] = f"Truncated AU header/data offset ({data_offset} > {size})"
    return res


def inspect_riff_wav(path: Path, size: int) -> dict[str, Any]:
    with path.open("rb") as stream:
        head = stream.read(min(size, 512))
    if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        return {"detected_format": "wav", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": "Invalid RIFF/WAVE header"}
    riff_size = struct.unpack("<I", head[4:8])[0] + 8
    offset = 12
    channels = None
    rate_hz = None
    bits = None
    while offset + 8 <= len(head):
        cid = head[offset : offset + 4]
        clen = struct.unpack("<I", head[offset + 4 : offset + 8])[0]
        payload = head[offset + 8 : offset + 8 + clen]
        if cid == b"fmt " and len(payload) >= 16:
            _, channels, rate_hz, _, _, bits = struct.unpack("<HHIIHH", payload[:16])
            break
        offset += 8 + clen + (clen & 1)
    valid = riff_size <= size and channels is not None and channels > 0
    res: dict[str, Any] = {"detected_format": "wav", "decode_level": "container_header", "decoder": DECODER_VERSION, "valid": valid}
    if channels is not None:
        res.update(audio_channels=channels, audio_hz=rate_hz, audio_bits=bits)
    if not valid:
        res["error"] = f"Truncated WAV or missing fmt chunk (declared {riff_size}, actual {size})"
    return res


def inspect_file_bytes(path: Path, full_png_decode: bool = True) -> dict[str, Any]:
    """Inspect file magic, container structure, and extension consistency."""
    size = path.stat().st_size
    ext = path.suffix.lower()
    with path.open("rb") as stream:
        magic = stream.read(32)

    if magic.startswith(PNG_SIGNATURE):
        info = inspect_png(path, full_decode=full_png_decode)
        expected_exts = {".png"}
    elif magic[:4] == b"FILM":
        info = inspect_sega_film(path, size)
        expected_exts = {".cpk", ".cak", ".film"}
    elif magic[:4] == b"FORM" and magic[8:12] in (b"AIFF", b"AIFC"):
        info = inspect_aiff(path, size)
        expected_exts = {".aif", ".aiff", ".aifc"}
    elif magic[:4] == b"RIFF" and magic[8:12] == b"WAVE":
        info = inspect_riff_wav(path, size)
        expected_exts = {".wav"}
    elif (len(magic) >= 18 and magic[:2] == b"BM" and struct.unpack("<I", magic[14:18])[0] in (12, 40, 52, 56, 108, 124)) or (magic[:2] == b"BM" and ext == ".bmp"):
        info = inspect_bmp(path, size)
        expected_exts = {".bmp"}
    elif magic[:6] in (b"GIF87a", b"GIF89a"):
        info = inspect_gif(path, size)
        expected_exts = {".gif"}
    elif magic[:2] == b"\xff\xd8":
        info = inspect_jpeg(path)
        expected_exts = {".jpg", ".jpeg"}
    elif magic[:9] == b"gimp xcf ":
        info = inspect_xcf(path)
        expected_exts = {".xcf"}
    elif len(magic) >= 12 and magic[4:8] == b"ftyp" and magic[8:12] in (b"avif", b"avis", b"mif1"):
        info = inspect_avif(path)
        expected_exts = {".avif"}
    elif magic[:4] == b"OggS":
        info = inspect_ogg(path, size)
        expected_exts = {".ogg"}
    elif magic[:4] in (b".snd", b"dns."):
        info = inspect_au(path, size)
        expected_exts = {".au"}
    elif magic.startswith(OLE2_SIGNATURE):
        info = {
            "detected_format": "ole2_compound_db",
            "decode_level": "header_only",
            "decoder": DECODER_VERSION,
            "valid": True,
        }
        expected_exts = {".db"}
    elif magic[:4] == b"DXBC":
        info = {
            "detected_format": "hlsl_dxbc_bytecode",
            "decode_level": "header_only",
            "decoder": DECODER_VERSION,
            "valid": size >= 32,
        }
        expected_exts = {".bin"}
    elif ext in {".json", ".tpsheet"}:
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
            info = {"detected_format": "json", "decode_level": "full_parse", "decoder": DECODER_VERSION, "valid": True}
        except (UnicodeDecodeError, ValueError) as exc:
            info = {"detected_format": "json", "decode_level": "full_parse", "decoder": DECODER_VERSION, "valid": False, "error": f"Invalid JSON: {exc}"}
        expected_exts = {".json", ".tpsheet"}
    elif ext in {".aup", ".plist", ".tps", ".xml"}:
        try:
            root = ET.fromstring(path.read_text(encoding="utf-8-sig"))
            tag = root.tag.split("}")[-1]
            info = {"detected_format": f"xml_{tag.lower()}", "decode_level": "full_parse", "decoder": DECODER_VERSION, "valid": True}
        except (UnicodeDecodeError, ET.ParseError) as exc:
            info = {"detected_format": "xml", "decode_level": "full_parse", "decoder": DECODER_VERSION, "valid": False, "error": f"Invalid XML: {exc}"}
        expected_exts = {".aup", ".plist", ".tps", ".xml"}
    elif ext == ".import":
        try:
            text = path.read_text(encoding="utf-8")
            ok = text.startswith("[remap]")
            info = {
                "detected_format": "godot_import_ini",
                "decode_level": "full_parse",
                "decoder": DECODER_VERSION,
                "valid": ok,
            }
            if not ok:
                info["error"] = "Godot .import missing [remap] header"
        except UnicodeDecodeError as exc:
            info = {"detected_format": "godot_import_ini", "decode_level": "full_parse", "decoder": DECODER_VERSION, "valid": False, "error": str(exc)}
        expected_exts = {".import"}
    elif ext in {".md", ".txt", ".bat"}:
        try:
            path.read_text(encoding="utf-8-sig")
            info = {"detected_format": "utf8_text", "decode_level": "full_parse", "decoder": DECODER_VERSION, "valid": True}
        except UnicodeDecodeError as exc:
            info = {"detected_format": "text_non_utf8", "decode_level": "header_only", "decoder": DECODER_VERSION, "valid": False, "error": str(exc)}
        expected_exts = {".md", ".txt", ".bat"}
    else:
        # Check if extension claimed an image/audio format whose magic did not match!
        known_binary_exts = {
            ".png": "png",
            ".bmp": "bmp",
            ".gif": "gif",
            ".jpg": "jpeg",
            ".jpeg": "jpeg",
            ".avif": "avif",
            ".xcf": "xcf",
            ".cpk": "sega_film_cpk",
            ".aif": "aiff",
            ".aiff": "aiff",
            ".wav": "wav",
            ".ogg": "ogg_vorbis",
            ".au": "audacity_au",
        }
        if ext in known_binary_exts:
            info = {
                "detected_format": "magic_mismatch",
                "expected_format_from_extension": known_binary_exts[ext],
                "decode_level": "header_only",
                "decoder": DECODER_VERSION,
                "valid": False,
                "error": f"Extension {ext} disagrees with leading magic bytes {magic[:8].hex()}",
            }
            expected_exts = {ext}
        else:
            info = {
                "detected_format": "opaque_binary",
                "decode_level": "header_only",
                "decoder": DECODER_VERSION,
                "valid": size > 0,
            }
            if size == 0:
                info["error"] = "Empty file"
            expected_exts = {ext} if ext else set()

    info["extension"] = ext or "(none)"
    info["extension_matches_format"] = (ext in expected_exts) if expected_exts else False
    return info
