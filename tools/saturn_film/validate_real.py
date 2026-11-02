#!/usr/bin/env python3
"""Optional bounded FFmpeg/ffprobe cross-check of explicitly supplied FILM files.

No downloads. All media outputs stay in a fresh private directory. The receipt
contains hashes, relative artifact names and commands with input/output tokens;
it contains neither raw samples nor absolute private paths.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.saturn_film.film import FilmError, Film, canonical, digest, extract, load, parse

MAX_INPUTS = 8
MAX_TOTAL_SOURCE_BYTES = 512 * 1024 * 1024


def packet_timing_matches(film: Film, packets: list[dict[str, object]]) -> bool:
    video = [sample for sample in film.samples if not sample.audio]
    return len(packets) == len(video) and all(
        packet.get("pts") == (sample.timestamp & 0x7FFFFFFF)
        and packet.get("duration") == sample.duration
        and ("K" in str(packet.get("flags", ""))) == (not bool(sample.timestamp & 0x80000000))
        for packet, sample in zip(packets, video)
    )


def parser_controls(film: Film) -> dict[str, bool]:
    result = {}

    def reject(name: str, data: bytes) -> None:
        try:
            parse(data)
        except FilmError:
            result[name] = True
        else:
            result[name] = False

    reject("truncated_payload_rejected", film.data[:-1])
    overlap = bytearray(film.data)
    struct.pack_into(">I", overlap, 80, 0)
    reject("overlapping_packet_rejected", bytes(overlap))
    del overlap
    timing = bytearray(film.data)
    video = next(sample for sample in film.samples if not sample.audio)
    struct.pack_into(">I", timing, 64 + video.index * 16 + 12, video.duration + 1)
    reject("one_tick_duration_drift_rejected", bytes(timing))
    del timing
    version = bytearray(film.data)
    version[8:12] = b"1.09"
    reject("unsupported_version_rejected", bytes(version))
    return result


def validate(inputs: list[Path], output: Path, timeout: int = 120) -> dict[str, object]:
    if not 1 <= len(inputs) <= MAX_INPUTS or not 1 <= timeout <= 120:
        raise FilmError("Require 1..8 inputs and timeout 1..120 seconds per process")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", source.stem) for source in inputs):
        raise FilmError("Input basenames require 1..64 ASCII letters, digits, underscores or hyphens")
    if len({source.stem for source in inputs}) != len(inputs):
        raise FilmError("Duplicate output stems")
    executables = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    if not all(executables.values()):
        raise FilmError("Optional real validation requires installed ffmpeg and ffprobe; nothing downloaded")
    if sum(source.stat().st_size for source in inputs) > MAX_TOTAL_SOURCE_BYTES:
        raise FilmError("Combined inputs exceed 512-MiB validation budget")
    output = output.absolute()
    if any(part.is_symlink() for part in (output, *output.parents)):
        raise FilmError("Symlink output paths are unsupported")
    # Parse all sources before creating anything; original inputs are never opened writable.
    films = [(source, load(source)) for source in inputs]
    output.mkdir(mode=0o700, exist_ok=False)
    commands: list[dict[str, object]] = []

    def run(name: str, arguments: list[str], source: Path | None = None) -> bytes:
        template = [name, *arguments]
        for index, argument in enumerate(template):
            if source is not None and argument == str(source):
                template[index] = "$INPUT/" + source.name
            elif argument.startswith(str(output) + "/"):
                template[index] = "$OUTPUT/" + argument[len(str(output)) + 1:]
        command = [str(executables[name]), *arguments]
        process = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
        # Do not echo ffmpeg's path-bearing stderr into the shareable receipt.
        if process.returncode:
            raise FilmError(f"{name} failed with exit {process.returncode}; diagnostic SHA-256 {digest(process.stderr)}")
        commands.append({"argv": template, "exit_code": process.returncode,
                         "stdout_sha256": digest(process.stdout),
                         "stderr_sha256": digest(process.stderr)})
        return process.stdout

    try:
        versions = {name: run(name, ["-version"]).decode().splitlines()[0] for name in executables}
        receipt: dict[str, object] = {
            "schema": "neptune.prior-assets-film-experiment.v1",
            "lineage": "prior-assets-unresolved-release",
            "python": sys.version.split()[0],
            "timeout_seconds_per_process": timeout,
            "tools": {name: {"version": versions[name], "executable_sha256": digest(Path(str(path)).read_bytes())}
                      for name, path in executables.items()},
            "tool_sources": {path.name: digest(path.read_bytes())
                             for path in sorted(Path(__file__).parent.glob("*.py"))},
            "commands": commands,
            "results": [],
        }
        for source, film in films:
            directory = output / source.stem
            report = extract(film, directory)
            expected = film.pcm_s8()
            external = directory / "ffmpeg-audio.s8"
            run("ffmpeg", ["-v", "error", "-xerror", "-nostdin", "-n", "-threads", "1",
                           "-i", str(source), "-map", "0:a:0", "-c:a", "pcm_s8", "-f", "s8",
                           "-fs", str(len(expected) + 1), str(external)], source)
            if external.read_bytes() != expected:
                raise FilmError(f"{source.name}: complete decoded PCM differs from FFmpeg")
            wav_external = directory / "ffmpeg-wave-roundtrip.s8"
            run("ffmpeg", ["-v", "error", "-xerror", "-nostdin", "-n", "-threads", "1",
                           "-i", str(directory / "audio.wav"), "-map", "0:a:0", "-c:a", "pcm_s8",
                           "-f", "s8", "-fs", str(len(expected) + 1), str(wav_external)], source)
            if wav_external.read_bytes() != expected:
                raise FilmError(f"{source.name}: WAV roundtrip differs from original PCM")
            video_hashes = []
            video_rows = []
            for repeat in (1, 2):
                target = directory / f"video-run{repeat}.framehash"
                run("ffmpeg", ["-v", "error", "-xerror", "-nostdin", "-n", "-threads", "1",
                               "-i", str(source), "-map", "0:v:0", "-an", "-pix_fmt", "rgb24",
                               "-fps_mode", "passthrough", "-threads", "1", "-f", "framehash", str(target)], source)
                video_hashes.append(digest(target.read_bytes()))
                video_rows.append([line for line in target.read_text().splitlines() if line and not line.startswith("#")])
            if video_hashes[0] != video_hashes[1] or len(video_rows[0]) != report["video"]["frames"]:
                raise FilmError(f"{source.name}: complete video decode repeat/count mismatch")
            probe = json.loads(run("ffprobe", ["-v", "error", "-show_entries",
                "format=duration:stream=index,codec_type,time_base,duration,r_frame_rate", "-of", "json", str(source)], source))
            packets = json.loads(run("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_packets",
                "-show_entries", "packet=pts,duration,flags", "-of", "json", str(source)], source))["packets"]
            if not packet_timing_matches(film, packets):
                raise FilmError(f"{source.name}: ffprobe packet PTS/duration/keyframe mismatch")
            bad_packets = deepcopy(packets)
            bad_packets[0]["pts"] += 1
            mutated = bytearray(expected)
            mutated[len(mutated) // 2] ^= 1
            planar = b"".join(film.packet(sample) for sample in film.samples if sample.audio)
            controls = parser_controls(film)
            controls.update(changed_recovered_audio_bit_detected=bytes(mutated) != expected,
                            wrong_planar_passthrough_detected=planar != expected,
                            changed_packet_tick_detected=not packet_timing_matches(film, bad_packets))
            if not all(controls.values()):
                raise FilmError(f"{source.name}: negative control did not fail")
            current = load(source)
            if digest(current.data) != report["source"]["sha256"]:
                raise FilmError(f"{source.name}: source changed during validation")
            receipt["results"].append({
                "asset_name": source.name, "report": report,
                "external_validation": {
                    "ffmpeg_pcm_s8_sha256": digest(expected), "pcm_matches_all_samples": True,
                    "wave_decodes_to_same_pcm": True,
                    "video_decoded_frames": len(video_rows[0]),
                    "two_video_framehash_runs_identical": True,
                    "video_framehash_sha256": video_hashes[0],
                    "first_frame": video_rows[0][0], "last_frame": video_rows[0][-1],
                    "ffprobe": probe, "all_ffprobe_packet_pts_durations_and_keyframes_match_stab": True,
                    "ffprobe_stream_duration_used_as_timing_oracle": False,
                }, "negative_controls": controls, "source_unchanged": True})
        (output / "receipt.json").write_bytes(canonical(receipt))
        return receipt
    except BaseException:
        # Preserve failed-run diagnostics privately, explicitly marked incomplete.
        (output / "INCOMPLETE.txt").write_text("Validation did not complete; do not publish as successful evidence.\n")
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh private directory with an existing parent")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        receipt = validate(args.input, args.output, args.timeout_seconds)
    except (FilmError, OSError, subprocess.TimeoutExpired, KeyError, json.JSONDecodeError) as error:
        # OSError/TimeoutExpired can embed private paths; keep public error class only.
        if isinstance(error, FilmError):
            print(f"Real FILM validation failed: {error}", file=sys.stderr)
        else:
            print(f"Real FILM validation failed ({type(error).__name__}); inspect private output", file=sys.stderr)
        return 1
    print(canonical(receipt).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
