"""Strict, dependency-free decoder for the observed Sega FILM 1.04 subset.

Video packets remain compressed Cinepak. PCM is signed 8-bit, planar within
each packet; sample-table video timestamps use their declared rational clock.
Unsupported layouts fail explicitly instead of being guessed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import struct
import wave

MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_HEADER_BYTES = 4 * 1024 * 1024
MAX_SAMPLES = 100_000
MAX_PACKET_BYTES = 8 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_AUDIO_BYTES = 128 * 1024 * 1024
LINEAGE = "prior-assets-unresolved-release"


class FilmError(ValueError):
    """Malformed, unsupported, or over-budget FILM input."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def rational(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


@dataclass(frozen=True)
class Sample:
    index: int
    offset: int
    length: int
    timestamp: int
    duration: int

    @property
    def audio(self) -> bool:
        return self.timestamp == 0xFFFFFFFF


@dataclass(frozen=True)
class Film:
    data: bytes
    header_bytes: int
    width: int
    height: int
    channels: int
    sample_rate: int
    clock: int
    samples: tuple[Sample, ...]

    def packet(self, sample: Sample) -> bytes:
        start = self.header_bytes + sample.offset
        return self.data[start : start + sample.length]

    def pcm_s8(self) -> bytes:
        """Interleave each independently planar packet without changing samples."""
        output = bytearray()
        for sample in self.samples:
            if sample.audio:
                packet = self.packet(sample)
                count = len(packet) // self.channels
                interleaved = bytearray(len(packet))
                for channel in range(self.channels):
                    interleaved[channel::self.channels] = packet[channel * count : (channel + 1) * count]
                output.extend(interleaved)
        return bytes(output)

    def sample_table(self) -> list[dict[str, object]]:
        result = []
        audio_frame = 0
        for sample in self.samples:
            row: dict[str, object] = {
                "index": sample.index,
                "kind": "audio" if sample.audio else "video",
                "source_offset": self.header_bytes + sample.offset,
                "bytes": sample.length,
                "sha256": digest(self.packet(sample)),
            }
            if sample.audio:
                frames = sample.length // self.channels
                row.update(start_sample_frame=audio_frame, sample_frames=frames)
                audio_frame += frames
            else:
                row.update(pts_ticks=sample.timestamp & 0x7FFFFFFF,
                           duration_ticks=sample.duration,
                           keyframe=not bool(sample.timestamp & 0x80000000))
            result.append(row)
        return result

    def report(self) -> dict[str, object]:
        video = [sample for sample in self.samples if not sample.audio]
        audio = [sample for sample in self.samples if sample.audio]
        pcm = self.pcm_s8()
        video_end = (video[-1].timestamp & 0x7FFFFFFF) + video[-1].duration
        audio_frames = len(pcm) // self.channels
        video_duration = Fraction(video_end, self.clock)
        audio_duration = Fraction(audio_frames, self.sample_rate)
        table = self.sample_table()
        return {
            "schema": "neptune.saturn-film-recovery.v1",
            "format": "Sega FILM 1.04",
            "source": {"sha256": digest(self.data), "bytes": len(self.data),
                       "lineage": LINEAGE, "release_identity": "unresolved",
                       "pinned_usa_or_japan_original": False},
            "accounting": {"header_bytes": self.header_bytes,
                           "packet_bytes": len(self.data) - self.header_bytes,
                           "packets": len(self.samples), "unaccounted_bytes": 0,
                           "packet_table_sha256": digest(canonical(table))},
            "video": {"codec": "cvid", "width": self.width, "height": self.height,
                      "bits_per_pixel": 24, "frames": len(video),
                      "clock_hz": self.clock, "start_pts_ticks": 0,
                      "end_pts_ticks": video_end,
                      "duration_seconds": rational(video_duration),
                      "duration_ticks_histogram": dict(sorted(Counter(str(s.duration) for s in video).items())),
                      "average_frames_per_second": rational(Fraction(len(video), 1) / video_duration),
                      "compressed_packets_decoded_to_pixels": False},
            "audio": {"source_format": "signed-8-planar-per-packet",
                      "recovered_format": "signed-8-interleaved",
                      "channels": self.channels, "sample_rate_hz": self.sample_rate,
                      "packets": len(audio), "sample_frames": audio_frames,
                      "pcm_bytes": len(pcm), "pcm_s8_sha256": digest(pcm),
                      "duration_seconds": rational(audio_duration)},
            "audio_minus_video_seconds": rational(audio_duration - video_duration),
            "limitations": ["Prior asset container; release not authenticated against a supplied disc.",
                            "Cinepak packets/timing inspected; pixels require an external decoder.",
                            "PCM samples recovered; game trigger mapping and SCSP behaviour remain open.",
                            "No emulator, gameplay, hardware accuracy or Neptune parity established."],
        }


def parse(data: bytes) -> Film:
    """Parse only the measured, contiguous FILM 1.04 subset, with strict budgets."""
    if not isinstance(data, bytes) or not 64 <= len(data) <= MAX_FILE_BYTES:
        raise FilmError("FILM size outside 64-byte..256-MiB budget")
    if data[:4] != b"FILM" or data[8:12] != b"1.04" or data[12:16] != bytes(4):
        raise FilmError("Expected FILM 1.04 and zero reserved header word")
    header = struct.unpack_from(">I", data, 4)[0]
    if not 64 <= header <= min(len(data), MAX_HEADER_BYTES):
        raise FilmError("Invalid or over-budget FILM header length")
    # This measured subset has exactly FDSC then STAB, no extensions/padding.
    if data[16:20] != b"FDSC" or struct.unpack_from(">I", data, 20)[0] != 32:
        raise FilmError("Expected exactly one 32-byte FDSC at offset 16")
    if data[24:28] != b"cvid":
        raise FilmError("Unsupported video codec; expected Cinepak cvid")
    height, width = struct.unpack_from(">II", data, 28)
    bpp, channels, bits, compression = data[36:40]
    rate = struct.unpack_from(">H", data, 40)[0]
    if not (0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION and bpp == 24):
        raise FilmError("Unsupported Cinepak dimensions or bit depth")
    if channels not in (1, 2) or bits != 8 or compression != 0 or not 1 <= rate <= 48000:
        raise FilmError("Unsupported audio; require mono/stereo uncompressed signed 8-bit PCM")
    if data[42:48] != bytes(6):
        raise FilmError("Unsupported FDSC extension/reserved bytes")
    if data[48:52] != b"STAB":
        raise FilmError("Expected exactly one STAB following FDSC")
    stab_length, clock, count = struct.unpack_from(">III", data, 52)
    if not 1 <= clock <= 1_000_000 or not 1 <= count <= MAX_SAMPLES:
        raise FilmError("Invalid or over-budget STAB clock/sample count")
    if stab_length != 16 + count * 16 or header != 48 + stab_length:
        raise FilmError("STAB table length/count/header mismatch")
    expected_offset = 0
    video_end = 0
    audio_bytes = 0
    have_video = False
    have_audio = False
    samples = []
    for index in range(count):
        offset, length, timestamp, duration = struct.unpack_from(">4I", data, 64 + index * 16)
        if not 1 <= length <= MAX_PACKET_BYTES or offset != expected_offset:
            raise FilmError(f"Packet {index}: invalid length, overlap, gap, or nonsequential range")
        expected_offset = offset + length
        if header + expected_offset > len(data):
            raise FilmError(f"Packet {index}: truncated payload")
        if timestamp == 0xFFFFFFFF:
            if length % channels or duration != 1:
                raise FilmError(f"Packet {index}: incomplete PCM frame or unsupported audio tag")
            audio_bytes += length
            if audio_bytes > MAX_AUDIO_BYTES:
                raise FilmError("Decoded audio exceeds 128-MiB budget")
            have_audio = True
        else:
            pts = timestamp & 0x7FFFFFFF
            if duration == 0 or pts != video_end or (not have_video and timestamp & 0x80000000):
                raise FilmError(f"Packet {index}: video timeline must start at keyframe 0 and be contiguous")
            video_end = pts + duration
            have_video = True
        samples.append(Sample(index, offset, length, timestamp, duration))
    if header + expected_offset != len(data):
        raise FilmError("Unaccounted trailing bytes")
    if not have_video or not have_audio:
        raise FilmError("This subset requires both Cinepak video and PCM audio")
    return Film(data, header, width, height, channels, rate, clock, tuple(samples))


def load(path: Path) -> Film:
    """Reject symlink components and oversize files before reading."""
    path = path.absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise FilmError("Symlink input paths are unsupported")
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise FilmError("Input missing, non-regular, or over file budget")
    with path.open("rb") as source:
        data = source.read(MAX_FILE_BYTES + 1)
    return parse(data)


def extract(film: Film, output: Path) -> dict[str, object]:
    """Write a fresh private directory; clean only our partial output on failure."""
    output = output.absolute()
    if any(part.is_symlink() for part in (output, *output.parents)):
        raise FilmError("Symlink output paths are unsupported")
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        pcm = film.pcm_s8()
        native = output / "audio.s8"
        native.write_bytes(pcm)
        wav = output / "audio.wav"
        with wave.open(str(wav), "wb") as stream:
            stream.setnchannels(film.channels)
            stream.setsampwidth(1)
            stream.setframerate(film.sample_rate)
            # RIFF 8-bit PCM is unsigned; XOR preserves every source sample.
            stream.writeframes(pcm.translate(bytes(i ^ 128 for i in range(256))))
        (output / "sample-table.json").write_bytes(canonical(film.sample_table()))
        report = film.report()
        report["artifacts"] = {
            "audio.s8": {"bytes": len(pcm), "sha256": digest(pcm)},
            "audio.wav": {"bytes": wav.stat().st_size, "sha256": digest(wav.read_bytes())},
            "sample-table.json": {"sha256": digest((output / "sample-table.json").read_bytes())},
        }
        (output / "report.json").write_bytes(canonical(report))
        return report
    except BaseException:
        shutil.rmtree(output)
        raise
