"""CUE sheet parser, safe track confinement and ECMA-130 raw CD sector reader."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
import struct
from typing import Any

SYNC_PATTERN = b"\x00" + (b"\xff" * 10) + b"\x00"
FRAMES_PER_SECOND = 75
PREGAP_LEADIN_FRAMES = 150  # 00:02:00 standard MSF offset for LBA 0

CUE_FILE_RE = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+(\S+)\s*$', re.I)
CUE_TRACK_RE = re.compile(r"^\s*TRACK\s+(\d{1,2})\s+(\S+)\s*$", re.I)
CUE_INDEX_RE = re.compile(r"^\s*INDEX\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\s*$", re.I)
CUE_GAP_RE = re.compile(r"^\s*(PREGAP|POSTGAP)\s+(\d{2}):(\d{2}):(\d{2})\s*$", re.I)
CUE_CATALOG_RE = re.compile(r"^\s*CATALOG\s+(\S+)\s*$", re.I)

SECTOR_MODES: dict[str, int] = {
    "MODE1/2352": 2352,
    "MODE1/2048": 2048,
    "MODE2/2352": 2352,
    "AUDIO": 2352,
}


def _build_edc_table() -> tuple[int, ...]:
    """ECMA-130 CD-ROM EDC CRC-32 table (reflected polynomial 0xD8018001, init 0)."""
    table: list[int] = []
    for index in range(256):
        crc = index
        for _ in range(8):
            crc = (crc >> 1) ^ 0xD8018001 if (crc & 1) else (crc >> 1)
        table.append(crc)
    return tuple(table)


EDC_TABLE = _build_edc_table()


def compute_edc(data: bytes | memoryview) -> int:
    crc = 0
    table = EDC_TABLE
    for byte in data:
        crc = (crc >> 8) ^ table[(crc ^ byte) & 0xFF]
    return crc


class DiscError(Exception):
    """Raised when a CUE sheet, track file or sector header violates format invariants."""


def confined_path(root: Path, relative: str) -> Path:
    """Resolve a normalised POSIX relative path inside root, rejecting symlinks."""
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise DiscError(f"Invalid relative path: {relative!r}")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != relative:
        raise DiscError(f"Path must be normalised and remain within root: {relative!r}")
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise DiscError(f"Symlink component rejected: {relative}")
    if not current.is_file():
        raise DiscError(f"Missing regular file: {relative}")
    if not current.resolve().is_relative_to(root.resolve()):
        raise DiscError(f"Path escapes root: {relative}")
    return current


def msf_to_frames(minutes: int, seconds: int, frames: int) -> int:
    if minutes < 0 or not (0 <= seconds < 60) or not (0 <= frames < FRAMES_PER_SECOND):
        raise DiscError(f"Invalid MSF timestamp: {minutes:02d}:{seconds:02d}:{frames:02d}")
    return (minutes * 60 + seconds) * FRAMES_PER_SECOND + frames


def frames_to_msf(total_frames: int) -> str:
    if total_frames < 0:
        raise DiscError(f"Negative frame count: {total_frames}")
    minutes, rem = divmod(total_frames, 60 * FRAMES_PER_SECOND)
    seconds, frames = divmod(rem, FRAMES_PER_SECOND)
    return f"{minutes:02d}:{seconds:02d}:{frames:02d}"


def decode_bcd(byte: int) -> int:
    high, low = (byte >> 4) & 0x0F, byte & 0x0F
    if high > 9 or low > 9:
        raise DiscError(f"Invalid BCD byte in sector header: 0x{byte:02x}")
    return high * 10 + low


@dataclass(frozen=True)
class CueIndex:
    number: int
    file_offset_frames: int
    msf: str


@dataclass(frozen=True)
class CueTrack:
    number: int
    mode: str
    sector_size: int
    file_relpath: str
    file_path: Path
    file_bytes: int
    file_sha256: str
    total_file_sectors: int
    track_offset_sectors_in_file: int
    track_sectors: int
    index01_offset_sectors_in_file: int
    pregap_sectors_in_file: int
    declared_pregap_frames: int
    declared_postgap_frames: int
    disc_lba_index01: int
    indices: tuple[CueIndex, ...]


@dataclass(frozen=True)
class CueSheet:
    cue_relpath: str
    cue_bytes: int
    cue_sha256: str
    catalog: str | None
    tracks: tuple[CueTrack, ...]


def hash_file_stable(path: Path) -> tuple[int, str]:
    before = path.stat()
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            total += len(chunk)
    after = path.stat()
    if (
        (before.st_size, before.st_mtime_ns, before.st_ino)
        != (after.st_size, after.st_mtime_ns, after.st_ino)
        or total != after.st_size
    ):
        raise DiscError(f"File mutated while hashing: {path.name}")
    return total, digest.hexdigest()


def parse_cue_sheet(root: Path, cue_relpath: str) -> CueSheet:
    cue_path = confined_path(root, cue_relpath)
    cue_bytes, cue_sha256 = hash_file_stable(cue_path)
    text = cue_path.read_text(encoding="utf-8-sig")

    catalog: str | None = None
    file_entries: list[dict[str, Any]] = []
    current_file: dict[str, Any] | None = None
    current_track: dict[str, Any] | None = None
    seen_tracks: set[int] = set()

    for lineno, raw_line in enumerate(text.splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.upper().startswith(("REM ", "REM\t")) or stripped.upper() == "REM":
            continue
        if stripped.upper().startswith(("TITLE ", "PERFORMER ", "SONGWRITER ", "ISRC ", "FLAGS ")):
            continue
        cat_match = CUE_CATALOG_RE.fullmatch(raw_line)
        if cat_match:
            catalog = cat_match.group(1)
            continue
        file_match = CUE_FILE_RE.fullmatch(raw_line)
        if file_match:
            if current_file is not None and not current_file["tracks"]:
                raise DiscError(f"CUE line {lineno}: FILE block has no TRACK declarations")
            fmt = file_match.group(3).upper()
            if fmt != "BINARY":
                raise DiscError(f"CUE line {lineno}: unsupported FILE type {fmt!r} (require BINARY)")
            declared_name = file_match.group(1) or file_match.group(2)
            confined_path(cue_path.parent, declared_name)
            rel = (PurePosixPath(cue_relpath).parent / declared_name).as_posix()
            resolved = confined_path(root, rel)
            f_bytes, f_sha256 = hash_file_stable(resolved)
            current_file = {
                "relpath": rel,
                "path": resolved,
                "bytes": f_bytes,
                "sha256": f_sha256,
                "tracks": [],
            }
            file_entries.append(current_file)
            current_track = None
            continue

        track_match = CUE_TRACK_RE.fullmatch(raw_line)
        if track_match:
            if current_file is None:
                raise DiscError(f"CUE line {lineno}: TRACK declared before FILE")
            number = int(track_match.group(1))
            mode = track_match.group(2).upper()
            if not (1 <= number <= 99):
                raise DiscError(f"CUE line {lineno}: invalid track number {number}")
            if number in seen_tracks:
                raise DiscError(f"CUE line {lineno}: duplicate track number {number}")
            if seen_tracks and number != max(seen_tracks) + 1:
                raise DiscError(f"CUE line {lineno}: non-contiguous track number {number}")
            if mode not in SECTOR_MODES:
                raise DiscError(f"CUE line {lineno}: unsupported track mode {mode!r}")
            seen_tracks.add(number)
            current_track = {
                "number": number,
                "mode": mode,
                "sector_size": SECTOR_MODES[mode],
                "indices": [],
                "pregap": 0,
                "postgap": 0,
            }
            current_file["tracks"].append(current_track)
            continue

        gap_match = CUE_GAP_RE.fullmatch(raw_line)
        if gap_match:
            if current_track is None:
                raise DiscError(f"CUE line {lineno}: {gap_match.group(1)} outside TRACK")
            kind = gap_match.group(1).upper()
            frames = msf_to_frames(
                int(gap_match.group(2)),
                int(gap_match.group(3)),
                int(gap_match.group(4)),
            )
            current_track["pregap" if kind == "PREGAP" else "postgap"] += frames
            continue

        index_match = CUE_INDEX_RE.fullmatch(raw_line)
        if index_match:
            if current_track is None:
                raise DiscError(f"CUE line {lineno}: INDEX outside TRACK")
            idx_num = int(index_match.group(1))
            mm, ss, ff = (
                int(index_match.group(2)),
                int(index_match.group(3)),
                int(index_match.group(4)),
            )
            frames = msf_to_frames(mm, ss, ff)
            if current_track["indices"]:
                prev = current_track["indices"][-1]
                if idx_num <= prev.number or frames < prev.file_offset_frames:
                    raise DiscError(f"CUE line {lineno}: non-monotonic INDEX {idx_num:02d}")
            current_track["indices"].append(
                CueIndex(number=idx_num, file_offset_frames=frames, msf=f"{mm:02d}:{ss:02d}:{ff:02d}")
            )
            continue

        raise DiscError(f"CUE line {lineno}: unrecognised directive: {stripped!r}")

    if not file_entries:
        raise DiscError("CUE contains no FILE declarations")
    if not file_entries[-1]["tracks"]:
        raise DiscError("Final CUE FILE declaration contains no TRACK")

    built_tracks: list[CueTrack] = []
    running_disc_lba = 0

    for f_entry in file_entries:
        f_tracks = f_entry["tracks"]
        sector_sizes = {t["sector_size"] for t in f_tracks}
        if len(sector_sizes) != 1:
            raise DiscError(f"Mixed sector sizes inside single BIN file {f_entry['relpath']} unsupported")
        sector_size = next(iter(sector_sizes))
        if f_entry["bytes"] % sector_size != 0:
            raise DiscError(
                f"Track file {f_entry['relpath']} size {f_entry['bytes']} is not a multiple of {sector_size}"
            )
        total_sectors = f_entry["bytes"] // sector_size
        if total_sectors == 0:
            raise DiscError(f"Track file {f_entry['relpath']} is empty")

        for idx, t_entry in enumerate(f_tracks):
            indices: list[CueIndex] = t_entry["indices"]
            by_num = {item.number: item for item in indices}
            if 1 not in by_num:
                raise DiscError(f"Track {t_entry['number']:02d} missing required INDEX 01")
            start_sector = indices[0].file_offset_frames
            index01_sector = by_num[1].file_offset_frames
            end_sector = (
                f_tracks[idx + 1]["indices"][0].file_offset_frames
                if idx + 1 < len(f_tracks)
                else total_sectors
            )
            if not (0 <= start_sector <= index01_sector < end_sector <= total_sectors):
                raise DiscError(
                    f"Track {t_entry['number']:02d} index offsets out of bounds for {f_entry['relpath']}"
                )
            pregap_in_file = index01_sector - start_sector
            running_disc_lba += t_entry["pregap"] + pregap_in_file
            disc_lba_index01 = running_disc_lba
            active_sectors = end_sector - index01_sector
            running_disc_lba += active_sectors + t_entry["postgap"]

            built_tracks.append(
                CueTrack(
                    number=t_entry["number"],
                    mode=t_entry["mode"],
                    sector_size=sector_size,
                    file_relpath=f_entry["relpath"],
                    file_path=f_entry["path"],
                    file_bytes=f_entry["bytes"],
                    file_sha256=f_entry["sha256"],
                    total_file_sectors=total_sectors,
                    track_offset_sectors_in_file=start_sector,
                    track_sectors=end_sector - start_sector,
                    index01_offset_sectors_in_file=index01_sector,
                    pregap_sectors_in_file=pregap_in_file,
                    declared_pregap_frames=t_entry["pregap"],
                    declared_postgap_frames=t_entry["postgap"],
                    disc_lba_index01=disc_lba_index01,
                    indices=tuple(indices),
                )
            )

    if built_tracks[0].mode not in {"MODE1/2352", "MODE1/2048", "MODE2/2352"}:
        raise DiscError(f"Saturn Track 01 must be a data track, found {built_tracks[0].mode}")

    return CueSheet(
        cue_relpath=cue_relpath,
        cue_bytes=cue_bytes,
        cue_sha256=cue_sha256,
        catalog=catalog,
        tracks=tuple(built_tracks),
    )


class DataTrackReader:
    """Random-access 2048-byte logical block reader with raw CD header & EDC validation."""

    def __init__(self, track: CueTrack) -> None:
        if track.mode not in {"MODE1/2352", "MODE1/2048", "MODE2/2352"}:
            raise DiscError(f"Cannot open non-data track {track.number} ({track.mode}) as DataTrackReader")
        self.track = track
        self._handle = track.file_path.open("rb")
        self.logical_blocks = track.track_sectors - track.pregap_sectors_in_file
        self.edc_verified_lbas: set[int] = set()
        self.edc_mismatch_lbas: list[int] = []
        self.mode2_form2_lbas: list[int] = []

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> DataTrackReader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def read_raw_sector(self, lba: int) -> bytes:
        if not (0 <= lba < self.logical_blocks):
            raise DiscError(f"LBA {lba} out of range (0..{self.logical_blocks - 1})")
        file_sector = self.track.index01_offset_sectors_in_file + lba
        offset = file_sector * self.track.sector_size
        self._handle.seek(offset)
        raw = self._handle.read(self.track.sector_size)
        if len(raw) != self.track.sector_size:
            raise DiscError(f"Short sector read at LBA {lba}")
        return raw

    def read_sector(self, lba: int, *, verify_edc: bool = True) -> bytes:
        """Return 2048-byte user data for LBA relative to Track INDEX 01."""
        raw = self.read_raw_sector(lba)
        if self.track.mode == "MODE1/2048":
            return raw

        if raw[:12] != SYNC_PATTERN:
            raise DiscError(f"LBA {lba}: invalid 12-byte CD-ROM sync header")
        mm = decode_bcd(raw[12])
        ss = decode_bcd(raw[13])
        ff = decode_bcd(raw[14])
        expected_msf_frames = PREGAP_LEADIN_FRAMES + self.track.disc_lba_index01 + lba
        actual_msf_frames = msf_to_frames(mm, ss, ff)
        if actual_msf_frames != expected_msf_frames:
            raise DiscError(
                f"LBA {lba}: sector MSF {mm:02d}:{ss:02d}:{ff:02d} ({actual_msf_frames}) "
                f"!= expected {frames_to_msf(expected_msf_frames)} ({expected_msf_frames})"
            )
        mode_byte = raw[15]
        if mode_byte == 1:
            if verify_edc and lba not in self.edc_verified_lbas:
                expected_edc = struct.unpack_from("<I", raw, 2064)[0]
                actual_edc = compute_edc(memoryview(raw)[:2064])
                if actual_edc != expected_edc:
                    self.edc_mismatch_lbas.append(lba)
                    raise DiscError(
                        f"LBA {lba}: Mode 1 EDC mismatch (stored 0x{expected_edc:08x}, computed 0x{actual_edc:08x})"
                    )
                self.edc_verified_lbas.add(lba)
            return raw[16:2064]
        if mode_byte == 2:
            # CD-ROM XA Mode 2: 8-byte subheader at 16..24 (duplicated at 20..24); bit 5 of submode = Form 2
            submode = raw[18]
            if submode & 0x20:
                self.mode2_form2_lbas.append(lba)
                # Form 2 carries 2324 user bytes; pad/reject if caller expects 2048 ISO block
                return raw[24:2072]
            if verify_edc and lba not in self.edc_verified_lbas:
                expected_edc = struct.unpack_from("<I", raw, 2072)[0]
                actual_edc = compute_edc(memoryview(raw)[16:2072])
                if actual_edc != expected_edc:
                    self.edc_mismatch_lbas.append(lba)
                    raise DiscError(
                        f"LBA {lba}: Mode 2 Form 1 EDC mismatch (stored 0x{expected_edc:08x}, computed 0x{actual_edc:08x})"
                    )
                self.edc_verified_lbas.add(lba)
            return raw[24:2072]
        raise DiscError(f"LBA {lba}: unsupported raw sector mode byte 0x{mode_byte:02x}")

    def read_logical_bytes(self, start_lba: int, byte_length: int, *, verify_edc: bool = False) -> bytes:
        if byte_length < 0:
            raise DiscError(f"Negative byte length: {byte_length}")
        if byte_length == 0:
            return b""
        sectors_needed = (byte_length + 2047) // 2048
        chunks = [self.read_sector(start_lba + i, verify_edc=verify_edc) for i in range(sectors_needed)]
        return b"".join(chunks)[:byte_length]


def summarize_audio_track(track: CueTrack) -> dict[str, Any]:
    """Inspect a 2352-byte 16-bit little-endian stereo PCM CD-DA track without exporting audio."""
    if track.mode != "AUDIO":
        raise DiscError(f"Track {track.number} is not AUDIO")
    zero_pregap_sectors = 0
    zero_active_sectors = 0
    leading_silent_active_sectors = 0
    trailing_silent_active_sectors = 0
    seen_nonzero_active = False
    peak_abs_sample = 0

    with track.file_path.open("rb") as handle:
        handle.seek(track.track_offset_sectors_in_file * 2352)
        for sec_idx in range(track.track_sectors):
            buf = handle.read(2352)
            if len(buf) != 2352:
                raise DiscError(f"Short CD-DA sector read on track {track.number}")
            is_zero = not any(buf)
            if sec_idx < track.pregap_sectors_in_file:
                if is_zero:
                    zero_pregap_sectors += 1
                continue
            if is_zero:
                zero_active_sectors += 1
                if not seen_nonzero_active:
                    leading_silent_active_sectors += 1
                trailing_silent_active_sectors += 1
            else:
                seen_nonzero_active = True
                trailing_silent_active_sectors = 0
                # Sample extrema at 16-bit LE stereo boundaries
                samples = struct.unpack("<1176h", buf)
                local_peak = max(-min(samples), max(samples))
                if local_peak > peak_abs_sample:
                    peak_abs_sample = local_peak

    active_sectors = track.track_sectors - track.pregap_sectors_in_file
    return {
        "active_sectors": active_sectors,
        "active_duration_msf": frames_to_msf(active_sectors),
        "active_seconds_exact_75hz": round(active_sectors / 75.0, 6),
        "pregap_sectors_in_file": track.pregap_sectors_in_file,
        "zero_pregap_sectors": zero_pregap_sectors,
        "zero_active_sectors": zero_active_sectors,
        "leading_silent_active_sectors": leading_silent_active_sectors,
        "trailing_silent_active_sectors": trailing_silent_active_sectors,
        "peak_abs_pcm16": peak_abs_sample,
    }
