"""Sega Saturn IP.BIN (System Area LBAs 0..15) parser and release metadata validator."""

from __future__ import annotations

from datetime import date
import hashlib
import struct
from typing import Any

from .cue import DataTrackReader, DiscError

SATURN_HARDWARE_ID = b"SEGA SEGASATURN "
SYSTEM_AREA_SECTORS = 16
SYSTEM_AREA_BYTES = SYSTEM_AREA_SECTORS * 2048  # 32,768 bytes

AREA_SYMBOL_MEANINGS: dict[str, dict[str, str]] = {
    "J": {"region": "japan", "video_standard": "NTSC", "description": "Japan (NTSC)"},
    "T": {"region": "asia_ntsc", "video_standard": "NTSC", "description": "Asia NTSC"},
    "U": {"region": "usa", "video_standard": "NTSC", "description": "North America (NTSC)"},
    "E": {"region": "europe", "video_standard": "PAL", "description": "Europe / PAL"},
}

PERIPHERAL_CODES: dict[str, str] = {
    "J": "Control Pad (standard 3-axis/button digital pad)",
    "A": "Analog Controller (Mission Stick / 3D Control Pad)",
    "M": "Sega Saturn Mouse",
    "K": "Saturn Keyboard",
    "S": "Arcade Racer / Steering Controller",
    "T": "Multitap (6Player Adaptor)",
    "E": "Analog / Multitap extended peripheral code",
    "G": "Virtua Gun",
    "W": "RAM Cartridge",
    "X": "Modem / NetLink",
    "C": "MPEG Card / DirectLink",
    "D": "DirectLink Cable",
    "F": "Floppy Disk Drive",
}


def _decode_ascii_field(raw: bytes, field_name: str) -> str:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise DiscError(f"IP.BIN {field_name} contains non-ASCII bytes: {raw!r}") from exc
    return text


def _decode_title(raw: bytes) -> str:
    # Saturn game titles in IP.BIN are ASCII or Shift-JIS/CP932 padded with spaces (0x20).
    trimmed = raw.rstrip(b" \x00")
    try:
        return trimmed.decode("ascii")
    except UnicodeDecodeError:
        return trimmed.decode("cp932", errors="replace")


def parse_ip_bin(system_area: bytes) -> dict[str, Any]:
    """Validate and decode a 32,768-byte Sega Saturn System Area (LBAs 0..15)."""
    if len(system_area) != SYSTEM_AREA_BYTES:
        raise DiscError(
            f"Saturn System Area must be {SYSTEM_AREA_BYTES} bytes (16 sectors), got {len(system_area)}"
        )
    if system_area[:16] != SATURN_HARDWARE_ID:
        raise DiscError(
            f"Invalid Sega Saturn hardware ID at LBA 0: expected {SATURN_HARDWARE_ID!r}, got {system_area[:16]!r}"
        )

    hardware_id = _decode_ascii_field(system_area[0x00:0x10], "hardware_id")
    maker_id = _decode_ascii_field(system_area[0x10:0x20], "maker_id")
    product_number = _decode_ascii_field(system_area[0x20:0x2A], "product_number")
    version = _decode_ascii_field(system_area[0x2A:0x30], "version")
    release_date_raw = _decode_ascii_field(system_area[0x30:0x38], "release_date")
    device_info = _decode_ascii_field(system_area[0x38:0x40], "device_info")
    area_symbols_raw = _decode_ascii_field(system_area[0x40:0x4A], "compatible_area_symbols")
    reserved_4a = _decode_ascii_field(system_area[0x4A:0x50], "reserved_4a")
    peripherals_raw = _decode_ascii_field(system_area[0x50:0x60], "peripherals")
    game_title = _decode_title(system_area[0x60:0xD0])

    # Parse release date YYYYMMDD
    release_date_iso: str | None = None
    stripped_date = release_date_raw.strip()
    if len(stripped_date) == 8 and stripped_date.isdigit():
        parsed = date(int(stripped_date[:4]), int(stripped_date[4:6]), int(stripped_date[6:8]))
        release_date_iso = parsed.isoformat()
    else:
        raise DiscError(f"IP.BIN invalid release date field: {release_date_raw!r}")

    # Parse area symbols
    area_codes: list[str] = []
    for ch in area_symbols_raw:
        if ch == " ":
            continue
        if ch not in AREA_SYMBOL_MEANINGS:
            raise DiscError(f"IP.BIN unrecognised area symbol {ch!r} in {area_symbols_raw!r}")
        if ch not in area_codes:
            area_codes.append(ch)
    if not area_codes:
        raise DiscError("IP.BIN specifies no compatible area symbols")

    peripheral_codes = [ch for ch in peripherals_raw if ch != " "]
    (
        ip_size,
        reserved_e4,
        master_stack_addr,
        slave_stack_addr,
        first_read_addr,
        first_read_size,
    ) = struct.unpack_from(">6I", system_area, 0xE0)

    video_standards = sorted({AREA_SYMBOL_MEANINGS[c]["video_standard"] for c in area_codes})
    regions = [AREA_SYMBOL_MEANINGS[c]["region"] for c in area_codes]

    return {
        "lba_start": 0,
        "sector_count": SYSTEM_AREA_SECTORS,
        "byte_length": SYSTEM_AREA_BYTES,
        "system_area_sha256": hashlib.sha256(system_area).hexdigest(),
        "header_256b_sha256": hashlib.sha256(system_area[:256]).hexdigest(),
        "boot_code_sha256": hashlib.sha256(system_area[256:]).hexdigest(),
        "hardware_id": hardware_id.strip(),
        "maker_id": maker_id.strip(),
        "product_number": product_number.strip(),
        "version": version.strip(),
        "release_date_raw": stripped_date,
        "release_date_iso": release_date_iso,
        "device_information": device_info.strip(),
        "area_symbols": area_codes,
        "area_details": [AREA_SYMBOL_MEANINGS[c] for c in area_codes],
        "compatible_regions": regions,
        "nominal_video_standards": video_standards,
        "timing_note": (
            "Nominal NTSC/PAL standard from IP.BIN area symbols only; exact frame/tick rate "
            "must be queried from the pinned core and VDP2 TVMD register (never assumed 60.0/50.0 Hz)."
        ),
        "reserved_4a": reserved_4a,
        "peripheral_codes": peripheral_codes,
        "peripheral_descriptions": [
            {"code": c, "description": PERIPHERAL_CODES.get(c, "Unclassified Saturn peripheral code")}
            for c in peripheral_codes
        ],
        "game_title": game_title,
        "ip_size_bytes": ip_size,
        "reserved_e4": reserved_e4,
        "master_sh2_stack_addr_hex": f"0x{master_stack_addr:08x}",
        "slave_sh2_stack_addr_hex": f"0x{slave_stack_addr:08x}",
        "first_read_load_addr_hex": f"0x{first_read_addr:08x}",
        "first_read_size_bytes": first_read_size,
    }


def read_ip_bin(reader: DataTrackReader) -> dict[str, Any]:
    if reader.logical_blocks < SYSTEM_AREA_SECTORS:
        raise DiscError(f"Track 01 has fewer than {SYSTEM_AREA_SECTORS} logical blocks")
    raw = reader.read_logical_bytes(0, SYSTEM_AREA_BYTES, verify_edc=True)
    return parse_ip_bin(raw)
