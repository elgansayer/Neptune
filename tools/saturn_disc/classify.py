"""Extension-agnostic binary format and container inspector for Saturn disc files."""

from __future__ import annotations

import hashlib
import math
from pathlib import PurePosixPath
import struct
from typing import Any


def shannon_entropy_bits_per_byte(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    total = len(data)
    entropy = 0.0
    for count in counts:
        if count:
            prob = count / total
            entropy -= prob * math.log2(prob)
    return round(entropy, 4)


def _inspect_sega_film(data: bytes) -> dict[str, Any] | None:
    if len(data) < 32 or data[:4] != b"FILM":
        return None
    header_size = struct.unpack_from(">I", data, 4)[0]
    if header_size < 32 or header_size > len(data):
        return {
            "detected_format": "sega_film_cpk",
            "valid": False,
            "accounting_class": "identified_undecoded",
            "error": f"Invalid FILM header size {header_size} for {len(data)}-byte file",
        }
    version = data[8:12].decode("ascii", errors="replace")
    pos = 16
    fdsc: dict[str, Any] | None = None
    stab: dict[str, Any] | None = None
    while pos + 8 <= header_size:
        tag = data[pos : pos + 4].decode("ascii", errors="replace")
        chunk_len = struct.unpack_from(">I", data, pos + 4)[0]
        if chunk_len < 8 or pos + chunk_len > header_size:
            return {
                "detected_format": "sega_film_cpk",
                "valid": False,
                "accounting_class": "identified_undecoded",
                "error": f"Truncated FILM subchunk {tag!r} at {pos}",
            }
        payload = data[pos + 8 : pos + chunk_len]
        if tag == "FDSC" and len(payload) >= 20:
            v_codec = payload[:4].decode("ascii", errors="replace").strip("\x00 ")
            height, width = struct.unpack_from(">II", payload, 4)
            bpp = payload[12]
            channels = payload[13]
            audio_bits = payload[14]
            audio_compression = payload[15]
            sample_rate = struct.unpack_from(">H", payload, 16)[0]
            fdsc = {
                "video_codec": v_codec or "none",
                "width": width,
                "height": height,
                "video_bpp": bpp,
                "audio_channels": channels,
                "audio_bit_depth": audio_bits,
                "audio_compression": audio_compression,
                "audio_sample_rate_hz": sample_rate,
            }
        elif tag == "STAB" and len(payload) >= 8:
            base_clock, sample_count = struct.unpack_from(">II", payload, 0)
            table_bytes_needed = 8 + sample_count * 16
            if len(payload) < table_bytes_needed:
                return {
                    "detected_format": "sega_film_cpk",
                    "valid": False,
                    "accounting_class": "identified_undecoded",
                    "error": f"Truncated FILM STAB sample table ({len(payload)} < {table_bytes_needed})",
                }
            max_end = 0
            video_samples = 0
            audio_samples = 0
            for idx in range(sample_count):
                s_off, s_len, info1, _ = struct.unpack_from(">IIII", payload, 8 + idx * 16)
                end = s_off + s_len
                if end > max_end:
                    max_end = end
                if info1 == 0xFFFFFFFF:
                    audio_samples += 1
                else:
                    video_samples += 1
            stab = {
                "timebase_hz": base_clock,
                "sample_count": sample_count,
                "video_sample_count": video_samples,
                "audio_sample_count": audio_samples,
                "required_file_bytes": header_size + max_end,
            }
        pos += chunk_len

    if stab is None:
        return {
            "detected_format": "sega_film_cpk",
            "valid": False,
            "accounting_class": "identified_undecoded",
            "error": "FILM header missing STAB chunk",
        }
    if stab["required_file_bytes"] > len(data):
        return {
            "detected_format": "sega_film_cpk",
            "valid": False,
            "accounting_class": "identified_undecoded",
            "film_version": version,
            "fdsc": fdsc,
            "stab": stab,
            "error": (
                f"Truncated FILM payload: STAB requires {stab['required_file_bytes']} bytes, "
                f"file has {len(data)} bytes"
            ),
        }
    return {
        "detected_format": "sega_film_cpk",
        "valid": True,
        "accounting_class": "identified_undecoded",
        "film_version": version,
        "header_bytes": header_size,
        "fdsc": fdsc,
        "stab": stab,
    }


def _read_ieee_extended_80(raw: bytes) -> float:
    expon = ((raw[0] & 0x7F) << 8) | raw[1]
    hi, lo = struct.unpack_from(">II", raw, 2)
    mantissa = (hi << 32) | lo
    if expon == 0 and mantissa == 0:
        return 0.0
    sign = -1.0 if (raw[0] & 0x80) else 1.0
    if expon == 0x7FFF:
        return float("inf") * sign
    return sign * math.ldexp(mantissa, expon - 16383 - 63)


def _inspect_aiff(data: bytes) -> dict[str, Any] | None:
    if len(data) < 12 or data[:4] != b"FORM" or data[8:12] not in (b"AIFF", b"AIFC"):
        return None
    form_type = data[8:12].decode("ascii")
    declared_size = struct.unpack_from(">I", data, 4)[0]
    if declared_size + 8 > len(data):
        return {
            "detected_format": "aiff_audio",
            "valid": False,
            "accounting_class": "identified_undecoded",
            "error": f"Truncated FORM/{form_type}: declared {declared_size + 8} > {len(data)}",
        }
    pos = 12
    end = min(len(data), declared_size + 8)
    comm: dict[str, Any] | None = None
    ssnd_bytes: int | None = None
    chunks: list[str] = []
    while pos + 8 <= end:
        cid = data[pos : pos + 4].decode("ascii", errors="replace")
        clen = struct.unpack_from(">I", data, pos + 4)[0]
        if pos + 8 + clen > len(data):
            return {
                "detected_format": "aiff_audio",
                "valid": False,
                "accounting_class": "identified_undecoded",
                "error": f"Truncated {form_type} chunk {cid!r} at {pos}",
            }
        chunks.append(cid)
        payload = data[pos + 8 : pos + 8 + clen]
        if cid == "COMM" and len(payload) >= 18:
            channels, sample_frames, sample_size = struct.unpack_from(">hIh", payload, 0)
            rate = _read_ieee_extended_80(payload[8:18])
            comp = payload[18:22].decode("ascii", errors="replace") if form_type == "AIFC" and len(payload) >= 22 else "NONE"
            comm = {
                "channels": channels,
                "sample_frames": sample_frames,
                "bit_depth": sample_size,
                "sample_rate_hz": round(rate, 3),
                "duration_seconds": round(sample_frames / rate, 6) if rate > 0 else None,
                "compression": comp,
            }
        elif cid == "SSND" and len(payload) >= 8:
            ssnd_bytes = clen - 8
        pos += 8 + clen + (clen & 1)

    if comm is None or ssnd_bytes is None:
        return {
            "detected_format": "aiff_audio",
            "valid": False,
            "accounting_class": "identified_undecoded",
            "error": f"{form_type} missing COMM or SSND chunk",
        }
    return {
        "detected_format": "aiff_audio",
        "valid": True,
        "accounting_class": "decoded",
        "form_type": form_type,
        "chunks": chunks,
        "audio": comm,
        "ssnd_pcm_bytes": ssnd_bytes,
    }


def _inspect_riff_wave(data: bytes) -> dict[str, Any] | None:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    declared = struct.unpack_from("<I", data, 4)[0]
    if declared + 8 > len(data):
        return {
            "detected_format": "riff_wave_audio",
            "valid": False,
            "accounting_class": "identified_undecoded",
            "error": f"Truncated RIFF/WAVE ({declared + 8} > {len(data)})",
        }
    pos = 12
    end = min(len(data), declared + 8)
    fmt_info: dict[str, Any] | None = None
    data_bytes: int | None = None
    while pos + 8 <= end:
        cid = data[pos : pos + 4].decode("ascii", errors="replace")
        clen = struct.unpack_from("<I", data, pos + 4)[0]
        if pos + 8 + clen > len(data):
            return {
                "detected_format": "riff_wave_audio",
                "valid": False,
                "accounting_class": "identified_undecoded",
                "error": f"Truncated WAVE chunk {cid!r}",
            }
        payload = data[pos + 8 : pos + 8 + clen]
        if cid == "fmt " and len(payload) >= 16:
            audio_fmt, channels, rate, _, _, bits = struct.unpack_from("<HHIIHH", payload, 0)
            fmt_info = {
                "audio_format_code": audio_fmt,
                "channels": channels,
                "sample_rate_hz": rate,
                "bit_depth": bits,
            }
        elif cid == "data":
            data_bytes = clen
        pos += 8 + clen + (clen & 1)
    if fmt_info is None or data_bytes is None:
        return {
            "detected_format": "riff_wave_audio",
            "valid": False,
            "accounting_class": "identified_undecoded",
            "error": "RIFF/WAVE missing fmt or data chunk",
        }
    return {
        "detected_format": "riff_wave_audio",
        "valid": True,
        "accounting_class": "decoded",
        "wave": fmt_info,
        "pcm_data_bytes": data_bytes,
    }


def _inspect_bmp(data: bytes) -> dict[str, Any] | None:
    if len(data) < 26 or data[:2] != b"BM":
        return None
    file_size, _, _, pixel_offset, dib_size = struct.unpack_from("<IHHII", data, 2)
    if dib_size not in (12, 40, 52, 56, 108, 124) or file_size > len(data) or pixel_offset > len(data):
        return None
    if dib_size == 12:
        width, height, planes, bpp = struct.unpack_from("<HHHH", data, 18)
    else:
        if len(data) < 30:
            return None
        width, height, planes, bpp = struct.unpack_from("<iiHH", data, 18)
    if width <= 0 or height == 0 or planes != 1:
        return None
    return {
        "detected_format": "bmp_bitmap",
        "valid": True,
        "accounting_class": "decoded",
        "width": width,
        "height": abs(height),
        "bpp": bpp,
    }


def _inspect_gif(data: bytes) -> dict[str, Any] | None:
    if len(data) < 14 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    width, height = struct.unpack_from("<HH", data, 6)
    has_trailer = data.rstrip(b"\x00").endswith(b"\x3b")
    return {
        "detected_format": "gif_image",
        "valid": bool(width > 0 and height > 0 and has_trailer),
        "accounting_class": "decoded" if has_trailer else "identified_undecoded",
        "version": data[:6].decode("ascii"),
        "width": width,
        "height": height,
    }


def _inspect_jpeg(data: bytes) -> dict[str, Any] | None:
    if len(data) < 4 or data[:3] != b"\xff\xd8\xff":
        return None
    trimmed = data.rstrip(b"\x00")
    has_eoi = trimmed.endswith(b"\xff\xd9")
    return {
        "detected_format": "jpeg_image",
        "valid": has_eoi,
        "accounting_class": "decoded" if has_eoi else "identified_undecoded",
    }


def _inspect_saturn_ip_template(data: bytes) -> dict[str, Any] | None:
    if len(data) < 256 or data[:16] != b"SEGA SEGASATURN ":
        return None
    return {
        "detected_format": "saturn_ip_header_template",
        "valid": True,
        "accounting_class": "decoded",
        "product_number": data[0x20:0x2A].decode("ascii", errors="replace").strip(),
        "version": data[0x2A:0x30].decode("ascii", errors="replace").strip(),
    }


def _inspect_m68k_sound_driver(data: bytes) -> dict[str, Any] | None:
    """Detect Motorola 68000 sound driver (e.g. Sega Saturn SDDRVS.TSK) loaded at SCSP RAM 0x000000."""
    if len(data) < 0x100 or len(data) > 524288:
        return None
    vectors = struct.unpack_from(">32I", data, 0)
    ssp, reset_pc = vectors[0], vectors[1]
    if not (0x000400 <= ssp <= 0x080000 and ssp % 2 == 0):
        return None
    if not (0x000080 <= reset_pc < len(data) and reset_pc % 2 == 0):
        return None
    valid_exc = sum(1 for v in vectors[2:] if 0x000080 <= v <= 0x080000 and v % 2 == 0)
    if valid_exc < 24:
        return None
    return {
        "detected_format": "saturn_m68k_sound_driver",
        "valid": True,
        "accounting_class": "executable",
        "initial_ssp_hex": f"0x{ssp:06x}",
        "reset_pc_hex": f"0x{reset_pc:06x}",
        "valid_exception_vectors": valid_exc,
    }


def _inspect_sh2_executable_prologue(data: bytes) -> dict[str, Any] | None:
    """Detect Hitachi SH-2 Saturn executable overlays/kernels with literal-pool High-WRAM jump prologue."""
    if len(data) < 64:
        return None
    # Classic Sega Saturn SH-2 entry trampoline: mov.l @(disp,pc),rN ; jmp @rN ; nop ; .long 0x060xxxxx
    hw0, hw1, hw2, hw3 = struct.unpack_from(">4H", data, 0)
    w2 = struct.unpack_from(">I", data, 8)[0]
    if (hw0 & 0xF000) == 0xD000 and (hw1 & 0xF0FF) == 0x402B and hw2 == 0x0009 and 0x06000000 <= w2 < 0x06100000:
        return {
            "detected_format": "saturn_sh2_executable",
            "valid": True,
            "accounting_class": "executable",
            "entry_trampoline_target_hex": f"0x{w2:08x}",
        }
    # Alternate SH-2 trampoline: mov #0, r1 (E100); mov.l @(disp,pc), r0 (D0xx); ... jmp @r0 (402B); nop (0009)
    first_insns = struct.unpack_from(">8H", data, 0)
    has_jmp = any((op & 0xF0FF) == 0x402B for op in first_insns[:6])
    has_nop = 0x0009 in first_insns[:7]
    if has_jmp and has_nop:
        words = struct.unpack_from(">16I", data, 0)
        hwr_ptrs = [w for w in words[2:] if 0x06000000 <= w < 0x06100000 and w % 2 == 0]
        if hwr_ptrs:
            return {
                "detected_format": "saturn_sh2_executable",
                "valid": True,
                "accounting_class": "executable",
                "entry_literal_hwr_ptr_hex": f"0x{hwr_ptrs[0]:08x}",
            }
    return None


def _inspect_scsp_sound_area_map(data: bytes) -> dict[str, Any] | None:
    """Detect Sega Saturn SCSP Sound Area Map table (8-byte big-endian records terminated by >=0x80)."""
    if len(data) < 8 or len(data) > 4096:
        return None
    pos = 0
    entries: list[dict[str, Any]] = []
    while pos < len(data):
        first = data[pos]
        if first >= 0x80:
            tail = data[pos + 1 :]
            if tail and any(b not in (0x00, 0xFF) for b in tail):
                return None
            if len(entries) >= 2:
                return {
                    "detected_format": "saturn_scsp_area_map",
                    "valid": True,
                    "accounting_class": "decoded",
                    "entry_count": len(entries),
                    "entries": entries,
                }
            return None
        if pos + 8 > len(data):
            return None
        word0, word1 = struct.unpack_from(">II", data, pos)
        data_kind = (word0 >> 28) & 0x7
        unit_num = (word0 >> 24) & 0xF
        scsp_addr = word0 & 0x0FFFFF
        transfer_done = (word1 >> 31) & 1
        byte_size = word1 & 0x0FFFFF
        if scsp_addr >= 0x080000 or byte_size == 0 or scsp_addr + byte_size > 0x080000:
            return None
        entries.append(
            {
                "data_kind": data_kind,
                "unit_number": unit_num,
                "scsp_ram_addr_hex": f"0x{scsp_addr:05x}",
                "transfer_bit": transfer_done,
                "byte_size": byte_size,
            }
        )
        pos += 8
    return None


def inspect_hudson_lwr_bank_archive(data: bytes) -> dict[str, Any] | None:
    """Decode sector-aligned 0x34-byte Hudson Low-Work-RAM bank archive (BOMSS/PROGRAM.BIN)."""
    if len(data) < 65536:
        return None
    total_sectors = (len(data) + 2047) // 2048
    raw_banks: list[dict[str, Any]] = []

    for sec in range(total_sectors):
        off = sec * 2048
        if off + 64 > len(data):
            break
        hdr = data[off : off + 64]
        w = struct.unpack_from(">16I", hdr, 0)
        # All 11 header slots w[0..10] must be 0 or valid Sega Saturn Low Work RAM (0x00200000..0x00300000)
        if not all(v == 0 or (0x00200000 <= v <= 0x00300000) for v in w[:11]):
            continue
        nonzero_slots = [v for v in w[:11] if v != 0]
        if not nonzero_slots:
            continue
        # Non-zero section pointers inside a Hudson bank header are monotonically non-decreasing
        if any(nonzero_slots[i] > nonzero_slots[i + 1] for i in range(len(nonzero_slots) - 1)):
            continue
        # +0x2c..+0x34: 2..8 byte ASCII identifier (alphanumeric / '_' / '-') padded with 0xFF
        tag_bytes = hdr[0x2C:0x34]
        ff_pos = tag_bytes.find(b"\xff")
        core = tag_bytes if ff_pos == -1 else tag_bytes[:ff_pos]
        pad = b"" if ff_pos == -1 else tag_bytes[ff_pos:]
        if not (2 <= len(core) <= 8 and all(b == 0xFF for b in pad)):
            continue
        if not all(32 <= b <= 126 and (chr(b).isalnum() or chr(b) in "_-") for b in core):
            continue
        # First slot or slot 10 always begins at load_base + 0x34 (0x00200034, 0x00250034, 0x00254034, 0x002ee034, 0x002fb034)
        if (nonzero_slots[0] & 0xFFF) != 0x034:
            continue

        load_base = nonzero_slots[0] - 0x34
        raw_banks.append(
            {
                "sector_offset": sec,
                "byte_offset": off,
                "name": core.decode("ascii"),
                "load_base_lwr_hex": f"0x{load_base:08x}",
                "header_slots_hex": [f"0x{v:08x}" if v else None for v in w[:11]],
            }
        )

    if len(raw_banks) < 4 or raw_banks[0]["sector_offset"] != 0:
        return None

    banks: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_banks):
        start_off = item["byte_offset"]
        end_off = raw_banks[idx + 1]["byte_offset"] if idx + 1 < len(raw_banks) else len(data)
        slice_bytes = data[start_off:end_off]
        name = item["name"]
        if name.startswith("s_vo"):
            bank_role = "scsp_voice_bank"
        elif name.startswith("s_"):
            bank_role = "scsp_sound_driver_or_bank"
        elif name.startswith("base"):
            bank_role = "core_common_bank"
        elif name.startswith("normal"):
            bank_role = "campaign_world_bank"
        elif name.startswith("battle"):
            bank_role = "battle_mode_bank"
        elif name.startswith("master"):
            bank_role = "master_mode_bank"
        else:
            bank_role = "mode_or_presentation_bank"

        banks.append(
            {
                "index": idx,
                "name": name,
                "role_hypothesis": bank_role,
                "sector_offset": item["sector_offset"],
                "sector_span": math.ceil((end_off - start_off) / 2048),
                "byte_offset": start_off,
                "byte_length": end_off - start_off,
                "load_base_lwr_hex": item["load_base_lwr_hex"],
                "header_slots_hex": item["header_slots_hex"],
                "sha256": hashlib.sha256(slice_bytes).hexdigest(),
            }
        )

    non_voice = [b for b in banks if b["role_hypothesis"] != "scsp_voice_bank"]
    voice = [b for b in banks if b["role_hypothesis"] == "scsp_voice_bank"]
    return {
        "detected_format": "hudson_lwr_bank_archive",
        "valid": True,
        "accounting_class": "identified_undecoded",
        "bank_count": len(banks),
        "core_and_sound_bank_count": len(non_voice),
        "voice_bank_count": len(voice),
        "core_and_sound_bank_names": [b["name"] for b in non_voice],
        "banks": banks,
    }


def _inspect_pointer_table_container(data: bytes) -> dict[str, Any] | None:
    """Conservatively test for big-endian offset/size archive headers without false positives."""
    size = len(data)
    if size < 32:
        return None

    count_be = struct.unpack_from(">I", data, 0)[0]
    if 2 <= count_be <= 4096 and 4 + count_be * 8 <= size:
        header_end = 4 + count_be * 8
        pairs = [struct.unpack_from(">II", data, 4 + i * 8) for i in range(count_be)]
        first_nonzero = next((off for off, length in pairs if length > 0), None)
        if first_nonzero is not None and header_end <= first_nonzero <= ((header_end + 2047) // 2048) * 2048 + 2048:
            valid = True
            prev_off = 0
            max_end = first_nonzero
            nonzero_entries = 0
            for off, length in pairs:
                if length == 0 and off == 0:
                    continue
                if off < header_end or off < prev_off or off + length > size:
                    valid = False
                    break
                prev_off = off
                if off + length > max_end:
                    max_end = off + length
                nonzero_entries += 1
            if valid and nonzero_entries >= 2 and size - max_end < 2048:
                return {
                    "scheme": "be_count_offset_length_pairs",
                    "confidence": "hypothesis",
                    "declared_entries": count_be,
                    "nonzero_entries": nonzero_entries,
                    "first_data_offset": first_nonzero,
                    "covered_end_offset": max_end,
                    "trailing_pad_bytes": size - max_end,
                }

    first_off = struct.unpack_from(">I", data, 0)[0]
    if 8 <= first_off <= 16384 and first_off % 4 == 0 and first_off < size:
        num_words = first_off // 4
        if 2 <= num_words <= 4096:
            words = list(struct.unpack_from(f">{num_words}I", data, 0))
            while len(words) > 2 and words[-1] == 0:
                words.pop()
            if len(words) >= 2 and words[0] == first_off:
                monotonic = all(words[i] <= words[i + 1] <= size for i in range(len(words) - 1))
                strict_steps = sum(1 for i in range(len(words) - 1) if words[i] < words[i + 1])
                if monotonic and strict_steps >= 2 and words[-1] <= size:
                    return {
                        "scheme": "be_offset_table_implicit_count",
                        "confidence": "hypothesis",
                        "offset_entry_count": len(words),
                        "distinct_spans": strict_steps,
                        "first_data_offset": first_off,
                        "last_offset": words[-1],
                    }
    return None


def _inspect_text(data: bytes) -> dict[str, Any] | None:
    if not data or len(data) > 262144:
        return None
    trimmed = data.rstrip(b"\x00")
    if trimmed.endswith(b"\x1a"):
        trimmed = trimmed[:-1]
    if not trimmed or b"\x00" in trimmed:
        return None
    # Reject any C0 control characters outside TAB (9), LF (10), CR (13)
    if any(b < 32 and b not in (9, 10, 13) for b in trimmed):
        return None
    if all(b in (9, 10, 13) or 32 <= b <= 126 for b in trimmed):
        lines = trimmed.decode("ascii").splitlines()
        return {
            "detected_format": "ascii_text",
            "valid": True,
            "accounting_class": "decoded",
            "encoding": "ascii",
            "line_count": len(lines),
        }
    try:
        decoded = trimmed.decode("cp932")
    except UnicodeDecodeError:
        return None
    if all(ch.isprintable() or ch in "\r\n\t" for ch in decoded):
        return {
            "detected_format": "shift_jis_text",
            "valid": True,
            "accounting_class": "decoded",
            "encoding": "cp932",
            "line_count": len(decoded.splitlines()),
        }
    return None


def classify_disc_file(
    logical_path: str,
    data: bytes,
    *,
    is_boot_first_read: bool = False,
) -> dict[str, Any]:
    """Classify a single ISO-9660 file by binary content, treating extension as a hypothesis."""
    ext = PurePosixPath(logical_path).suffix.lower()
    entropy = shannon_entropy_bits_per_byte(data)
    magic_hex = data[:16].hex()

    if len(data) == 0 or not any(data):
        return {
            "extension_hypothesis": ext or "<none>",
            "detected_format": "zero_filled",
            "valid": True,
            "accounting_class": "padding",
            "entropy_bits_per_byte": 0.0,
            "magic_16b_hex": magic_hex,
            "container_hypothesis": None,
        }

    if is_boot_first_read:
        return {
            "extension_hypothesis": ext or "<none>",
            "detected_format": "saturn_sh2_boot_executable",
            "valid": True,
            "accounting_class": "executable",
            "entropy_bits_per_byte": entropy,
            "magic_16b_hex": magic_hex,
            "note": "Lowest-LBA root directory boot file loaded by Sega Saturn IP.BIN",
            "container_hypothesis": None,
        }

    for detector in (
        _inspect_sega_film,
        _inspect_aiff,
        _inspect_riff_wave,
        _inspect_bmp,
        _inspect_gif,
        _inspect_jpeg,
        _inspect_saturn_ip_template,
        _inspect_m68k_sound_driver,
        _inspect_sh2_executable_prologue,
        _inspect_scsp_sound_area_map,
        inspect_hudson_lwr_bank_archive,
        _inspect_text,
    ):
        result = detector(data)
        if result is not None:
            return {
                "extension_hypothesis": ext or "<none>",
                **result,
                "entropy_bits_per_byte": entropy,
                "magic_16b_hex": magic_hex,
                "container_hypothesis": None,
            }

    container = _inspect_pointer_table_container(data)
    if container is not None:
        return {
            "extension_hypothesis": ext or "<none>",
            "detected_format": "binary_container_candidate",
            "valid": True,
            "accounting_class": "identified_undecoded",
            "entropy_bits_per_byte": entropy,
            "magic_16b_hex": magic_hex,
            "container_hypothesis": container,
        }

    return {
        "extension_hypothesis": ext or "<none>",
        "detected_format": "unclassified_binary",
        "valid": True,
        "accounting_class": "unknown",
        "entropy_bits_per_byte": entropy,
        "magic_16b_hex": magic_hex,
        "container_hypothesis": None,
    }
