"""Bounded lossless libretro callback PCM retention and same-core replay checks.

Hashes bind the supplied files, not their authenticity or hardware accuracy.
This module intentionally does not import the frontend or run an emulator.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from cli import LabError, confined_file

SCHEMA = "neptune.libretro-pcm.v1"
COMPARISON = "neptune.libretro-pcm-comparison.v1"
MAX_PCM_BYTES = 64 * 1024**2
MAX_FRAME_SAMPLES = 65536
MAX_FRAMES = 60000
MAX_MANIFEST_BYTES = 16 * 1024**2
MAX_OBSERVATION_BYTES = 64 * 1024**2
SCOPE = ("Equality of retained libretro callback PCM in the same pinned replay setup only; "
         "source authenticity, hardware accuracy and Godot/game fidelity are not certified.")
IDENTITY_KEYS = {"lock_sha256", "core_sha256", "settings_sha256", "frontend_sha256", "python_sha256"}


def require(condition, message):
    if not condition:
        raise LabError(message)


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def signature(stat):
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino, stat.st_dev


def safe_path(path):
    path = Path(path).absolute()
    require(not any(item.is_symlink() for item in (path, *path.parents)), "PCM evidence path contains a symlink")
    return path


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate PCM evidence JSON key")
        result[key] = value
    return result


def read_document(path, limit):
    path = safe_path(path)
    require(path.is_file(), "Missing regular PCM evidence file")
    before = path.stat()
    require(before.st_size <= limit, "PCM evidence JSON exceeds its byte bound")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit and len(raw) == before.st_size and signature(before) == signature(path.stat()),
            "PCM evidence JSON changed or exceeds its byte bound")
    value = json.loads(raw, object_pairs_hook=unique_object,
                       parse_constant=lambda _: (_ for _ in ()).throw(LabError("Nonfinite PCM evidence number")))
    return value, hashlib.sha256(raw).hexdigest()


def validate_observation(observation):
    require(isinstance(observation, dict) and set(observation) == {"frame", "video", "audio_sha256", "audio_frames", "inputs"},
            "Invalid PCM frame observation")
    require(type(observation["frame"]) is int and observation["frame"] >= 0, "Invalid PCM emulated frame index")
    require(type(observation["audio_frames"]) is int and 0 <= observation["audio_frames"] <= MAX_FRAME_SAMPLES,
            "Invalid PCM per-frame sample count")
    require(sha(observation["audio_sha256"]), "Invalid PCM frame digest")
    inputs = observation["inputs"]
    require(isinstance(inputs, list) and len(inputs) == 12
            and all(type(mask) is int and 0 <= mask <= 65535 for mask in inputs), "Invalid PCM input timeline")
    video = observation["video"]
    require(isinstance(video, dict) and set(video) == {"width", "height", "pixel_format", "sha256"}
            and video["pixel_format"] == "XRGB8888-le" and sha(video["sha256"])
            and all(type(video[key]) is int and 0 < video[key] <= 1024 for key in ("width", "height")),
            "Invalid PCM-bound video observation")


def validate_observations(observations):
    require(isinstance(observations, dict) and set(observations) == {"schema", "identity", "av", "frames"}
            and observations["schema"] == "neptune.libretro-observations.v1", "Invalid PCM-bound observations")
    identity = observations["identity"]
    require(isinstance(identity, dict) and set(identity) == IDENTITY_KEYS and all(sha(value) for value in identity.values()),
            "Missing pinned PCM component identities")
    av = observations["av"]
    require(isinstance(av, dict) and set(av) == {"fps", "fps_binary64", "sample_rate", "base_width", "base_height"},
            "Invalid PCM AV identity")
    for key, maximum in (("fps", 1000), ("sample_rate", 384000)):
        rate = av[key]
        require(type(rate) in (int, float) and math.isfinite(rate) and 0 < rate <= maximum, "Invalid PCM core-reported rate")
    require(av["fps_binary64"] == float(av["fps"]).hex(), "PCM video rate binary64 mismatch")
    require(all(type(av[key]) is int and 0 < av[key] <= 1024 for key in ("base_width", "base_height")),
            "Invalid PCM video dimensions")
    frames = observations["frames"]
    require(isinstance(frames, list) and 1 <= len(frames) <= MAX_FRAMES, "Empty or excessive PCM frame observations")
    for index, frame in enumerate(frames):
        validate_observation(frame)
        if index:
            require(frame["frame"] == frames[index - 1]["frame"] + 1, "Noncontiguous PCM frame observations")


def audio_format(av):
    rate = float(av["sample_rate"])
    numerator, denominator = rate.as_integer_ratio()
    return {"encoding": "s16le", "channels": 2, "channel_order": ["left", "right"],
            "sample_rate_binary64": rate.hex(), "sample_rate": {"numerator": numerator, "denominator": denominator}}


def publish_manifest(manifest, path):
    """Publish complete JSON atomically without replacing another writer's file."""
    body = (json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    require(len(body) <= MAX_MANIFEST_BYTES, "PCM manifest exceeds its byte bound")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".audio-manifest-", delete=False) as stream:
            temporary = Path(stream.name)
            require(stream.write(body) == len(body), "Incomplete PCM manifest write")
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return hashlib.sha256(body).hexdigest()


class PCMWriter:
    """Append one bounded emulated frame at a time; publish only on finish()."""

    def __init__(self, output_dir: Path, max_bytes=MAX_PCM_BYTES):
        require(type(max_bytes) is int and 4 <= max_bytes <= MAX_PCM_BYTES and max_bytes % 4 == 0,
                "PCM byte budget must be a positive stereo-aligned bound up to 64 MiB")
        self.output_dir = safe_path(output_dir)
        require(self.output_dir.is_dir(), "PCM output directory must already exist")
        self.manifest_path = self.output_dir / "audio.json"
        self.pcm_path = self.output_dir / "audio.s16le"
        require(not self.manifest_path.exists() and not self.manifest_path.is_symlink()
                and not self.pcm_path.exists() and not self.pcm_path.is_symlink(), "Refusing to overwrite PCM output")
        self.stream = self.pcm_path.open("xb")
        self.max_bytes = max_bytes
        self.frames = []
        self.observation_digests = []
        self.samples = 0
        self.digest = hashlib.sha256()
        self.failed = False
        self.finished = False

    def append(self, observation: dict, raw: bytes):
        try:
            require(not self.failed and not self.finished and not self.stream.closed, "PCM writer is closed or failed")
            validate_observation(observation)
            require(type(raw) is bytes and len(raw) == observation["audio_frames"] * 4, "PCM frame byte/sample count mismatch")
            require(hashlib.sha256(raw).hexdigest() == observation["audio_sha256"], "PCM bytes differ from frame observation")
            require(len(self.frames) < MAX_FRAMES, "PCM frame bound exceeded")
            if self.frames:
                require(observation["frame"] == self.frames[-1]["frame"] + 1, "PCM frames must be contiguous")
            require((self.samples + observation["audio_frames"]) * 4 <= self.max_bytes, "PCM byte budget exceeded")
            require(self.stream.write(raw) == len(raw), "Incomplete PCM write")
            self.frames.append({"frame": observation["frame"], "sample_offset": self.samples,
                                "sample_frames": observation["audio_frames"], "sha256": observation["audio_sha256"]})
            self.observation_digests.append(hashlib.sha256(canonical(observation).encode()).hexdigest())
            self.samples += observation["audio_frames"]
            self.digest.update(raw)
        except (LabError, OSError, ValueError, TypeError):
            self.failed = True
            raise

    def close(self):
        if not self.stream.closed:
            try:
                self.stream.close()
            except OSError:
                self.failed = True
                raise

    def finish(self, observations_path: Path, checkpoint_sha256=None):
        try:
            self.close()
            require(not self.failed and not self.finished, "PCM writer already finished or failed")
            require(self.samples > 0 and self.frames, "Empty PCM capture cannot succeed")
            require(checkpoint_sha256 is None or sha(checkpoint_sha256), "Invalid PCM origin checkpoint digest")
            observations_path = safe_path(observations_path)
            require(observations_path.is_relative_to(self.output_dir), "PCM observations must remain within the output directory")
            relative = observations_path.relative_to(self.output_dir).as_posix()
            require(relative not in ("audio.json", "audio.s16le"), "PCM observations need a separate file")
            observations, observations_sha = read_document(confined_file(self.output_dir, relative), MAX_OBSERVATION_BYTES)
            validate_observations(observations)
            require(len(observations["frames"]) == len(self.frames), "PCM observations frame count mismatch")
            for observed, expected in zip(observations["frames"], self.observation_digests):
                require(hashlib.sha256(canonical(observed).encode()).hexdigest() == expected,
                        "Retained PCM observations differ from appended frames")
            require(not self.manifest_path.exists() and not self.manifest_path.is_symlink(), "Refusing to overwrite PCM manifest")
            manifest = {"schema": SCHEMA, "scope": SCOPE, "format": audio_format(observations["av"]),
                        "origin": {"start_frame": self.frames[0]["frame"], "sample_frame": 0,
                                   "checkpoint_sha256": checkpoint_sha256},
                        "observations": {"path": relative, "sha256": observations_sha},
                        "pcm": {"path": "audio.s16le", "bytes": self.samples * 4,
                                "sample_frames": self.samples, "sha256": self.digest.hexdigest()},
                        "frames": self.frames}
            # Check retained bytes and per-frame associations before publication.
            validate_capture(self.output_dir, manifest, observations)
            manifest_sha = publish_manifest(manifest, self.manifest_path)
            self.finished = True
            return {"manifest": "audio.json", "manifest_sha256": manifest_sha,
                    "pcm": "audio.s16le", "pcm_sha256": manifest["pcm"]["sha256"],
                    "sample_frames": self.samples, "scope": SCOPE}
        except (LabError, OSError, ValueError, TypeError):
            self.failed = True
            raise


def validate_capture(root, manifest, observations):
    require(isinstance(manifest, dict) and set(manifest) == {"schema", "scope", "format", "origin", "observations", "pcm", "frames"}
            and manifest["schema"] == SCHEMA and manifest["scope"] == SCOPE, "Invalid PCM manifest")
    validate_observations(observations)
    require(canonical(manifest["format"]) == canonical(audio_format(observations["av"])), "PCM format/rate mismatch")
    binding = manifest["observations"]
    require(isinstance(binding, dict) and set(binding) == {"path", "sha256"} and sha(binding["sha256"]),
            "Invalid PCM observation binding")
    info = manifest["pcm"]
    require(isinstance(info, dict) and set(info) == {"path", "bytes", "sample_frames", "sha256"}
            and type(info["sample_frames"]) is int and info["sample_frames"] > 0
            and type(info["bytes"]) is int and 0 < info["bytes"] <= MAX_PCM_BYTES
            and info["bytes"] == info["sample_frames"] * 4 and sha(info["sha256"]), "Invalid PCM byte/sample identity")
    path = confined_file(root, info["path"])
    require(info["path"] != binding["path"], "PCM and observations must be separate files")
    before = path.stat()
    require(before.st_size == info["bytes"], "PCM file length mismatch")
    frames = manifest["frames"]
    require(isinstance(frames, list) and len(frames) == len(observations["frames"]), "PCM frame map length mismatch")
    origin = manifest["origin"]
    require(isinstance(origin, dict) and set(origin) == {"start_frame", "sample_frame", "checkpoint_sha256"}
            and type(origin["start_frame"]) is int and origin["start_frame"] == observations["frames"][0]["frame"]
            and type(origin["sample_frame"]) is int and origin["sample_frame"] == 0
            and (origin["checkpoint_sha256"] is None or sha(origin["checkpoint_sha256"])), "Invalid PCM capture origin")
    samples = 0
    whole = hashlib.sha256()
    with path.open("rb") as stream:
        for segment, observation in zip(frames, observations["frames"]):
            require(isinstance(segment, dict) and set(segment) == {"frame", "sample_offset", "sample_frames", "sha256"},
                    "Invalid PCM frame map")
            require(all(type(segment[key]) is int for key in ("frame", "sample_offset", "sample_frames")),
                    "PCM frame map counts must be integers")
            require(segment["frame"] == observation["frame"] and segment["sample_offset"] == samples
                    and segment["sample_frames"] == observation["audio_frames"]
                    and segment["sha256"] == observation["audio_sha256"], "PCM frame map differs from observations")
            raw = stream.read(segment["sample_frames"] * 4)
            require(len(raw) == segment["sample_frames"] * 4
                    and hashlib.sha256(raw).hexdigest() == segment["sha256"], "PCM frame bytes/digest mismatch")
            whole.update(raw)
            samples += segment["sample_frames"]
        require(not stream.read(1), "Unmapped trailing PCM bytes")
    require(samples == info["sample_frames"] and whole.hexdigest() == info["sha256"], "PCM stream digest/sample mismatch")
    require(signature(before) == signature(path.stat()), "PCM file changed while validating")
    return path, signature(before)


def load_capture(manifest_path):
    manifest_path = safe_path(manifest_path)
    manifest, manifest_sha = read_document(manifest_path, MAX_MANIFEST_BYTES)
    require(isinstance(manifest, dict) and isinstance(manifest.get("observations"), dict)
            and set(manifest["observations"]) == {"path", "sha256"}, "Missing PCM observation binding")
    root = manifest_path.parent
    observations_path = confined_file(root, manifest["observations"]["path"])
    require(observations_path != manifest_path, "PCM manifest cannot serve as its observations")
    observations, actual_sha = read_document(observations_path, MAX_OBSERVATION_BYTES)
    require(actual_sha == manifest["observations"]["sha256"], "Retained PCM observation digest mismatch")
    pcm_path, pcm_signature = validate_capture(root, manifest, observations)
    require(pcm_path != manifest_path, "PCM manifest cannot serve as its raw stream")
    return {"manifest": manifest, "manifest_sha256": manifest_sha, "observations": observations,
            "pcm_path": pcm_path, "pcm_signature": pcm_signature}


def compare_captures(reference_path, candidate_path, reference_start=0):
    reference, candidate = load_capture(reference_path), load_capture(candidate_path)
    left_obs, right_obs = reference["observations"], candidate["observations"]
    require(type(reference_start) is int and 0 <= reference_start < len(left_obs["frames"]), "Invalid PCM reference-start frame index")
    require(canonical(left_obs["identity"]) == canonical(right_obs["identity"])
            and canonical(left_obs["av"]) == canonical(right_obs["av"]), "PCM component/AV identities differ; same-core replay only")
    left = reference["manifest"]["frames"][reference_start:]
    right = candidate["manifest"]["frames"]
    require(left[0]["frame"] == right[0]["frame"], "PCM absolute starting frame mismatch; no inferred alignment")
    report = {"schema": COMPARISON, "match": True, "reference_sha256": reference["manifest_sha256"],
              "candidate_sha256": candidate["manifest_sha256"], "reference_start": reference_start,
              "start_frame": left[0]["frame"], "scope": SCOPE}
    origin = left[0]["sample_offset"]
    compared = 0
    with reference["pcm_path"].open("rb") as a, candidate["pcm_path"].open("rb") as b:
        require(signature(os.fstat(a.fileno())) == reference["pcm_signature"]
                and signature(os.fstat(b.fileno())) == candidate["pcm_signature"], "PCM file changed before comparison")
        a.seek(origin * 4)
        for index, (first, second) in enumerate(zip(left, right)):
            frame = first["frame"]
            if frame != second["frame"] or first["sample_frames"] != second["sample_frames"]:
                report.update(match=False, first_frame=frame, sample_frame=compared, reason="frame/sample boundary mismatch")
                break
            if left_obs["frames"][reference_start + index]["inputs"] != right_obs["frames"][index]["inputs"]:
                raise LabError("PCM input timelines differ; replay inputs must match")
            count = first["sample_frames"] * 4
            first_raw, second_raw = a.read(count), b.read(count)
            require(len(first_raw) == count and len(second_raw) == count, "PCM stream shortened during comparison")
            require(hashlib.sha256(first_raw).hexdigest() == first["sha256"]
                    and hashlib.sha256(second_raw).hexdigest() == second["sha256"], "PCM frame changed after validation")
            if first_raw != second_raw:
                byte = next(offset for offset, pair in enumerate(zip(first_raw, second_raw)) if pair[0] != pair[1])
                report.update(match=False, first_frame=frame, sample_frame=compared + byte // 4,
                              channel=(byte % 4) // 2, reason="PCM sample mismatch")
                break
            compared += first["sample_frames"]
        else:
            if len(left) != len(right):
                index = min(len(left), len(right))
                frame = left[index]["frame"] if index < len(left) else right[index]["frame"]
                report.update(match=False, first_frame=frame, sample_frame=compared, reason="capture frame count mismatch")
            else:
                report.update(matched_frames=len(left), matched_sample_frames=compared)
        require(signature(os.fstat(a.fileno())) == reference["pcm_signature"]
                and signature(os.fstat(b.fileno())) == candidate["pcm_signature"], "PCM file changed during comparison")
    return report
