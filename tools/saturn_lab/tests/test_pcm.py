"""Synthetic PCM file/stream contracts only; no original media or Godot parity."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pcm


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def samples(*pairs):
    return b"".join(struct.pack("<hh", *pair) for pair in pairs)


def observation(frame, raw, inputs=None):
    return {"frame": frame, "audio_frames": len(raw) // 4, "audio_sha256": digest(raw),
            "inputs": [0] * 12 if inputs is None else inputs,
            "video": {"width": 2, "height": 1, "pixel_format": "XRGB8888-le", "sha256": digest(str(frame).encode())}}


def observations(frames):
    return {"schema": "neptune.libretro-observations.v1",
            "identity": {key: digest(("synthetic/" + key).encode()) for key in pcm.IDENTITY_KEYS},
            "av": {"fps": 59.5, "fps_binary64": float(59.5).hex(), "sample_rate": 44100.0,
                   "base_width": 2, "base_height": 1}, "frames": frames}


class PCMTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def capture(self, name, raws=None, start=7, inputs=None, checkpoint=None):
        if raws is None:
            raws = [samples((0, 0)), samples((-32768, 32767), (-1, 1)), b"", samples((20, -30))]
        root = self.root / name
        root.mkdir()
        writer = pcm.PCMWriter(root)
        frames = [observation(start + index, raw, inputs) for index, raw in enumerate(raws)]
        try:
            for frame, raw in zip(frames, raws):
                writer.append(frame, raw)
        finally:
            writer.close()
        path = root / "observations.json"
        path.write_text(json.dumps(observations(frames)))
        result = writer.finish(path, checkpoint_sha256=checkpoint)
        return root / "audio.json", result

    def manifest(self, path):
        return json.loads(path.read_text())

    def rewrite_manifest(self, path, value):
        path.write_text(json.dumps(value))

    def rewrite_observations(self, path, change):
        manifest = self.manifest(path)
        target = path.parent / manifest["observations"]["path"]
        value = json.loads(target.read_text())
        change(value)
        target.write_text(json.dumps(value))
        manifest["observations"]["sha256"] = digest(target.read_bytes())
        self.rewrite_manifest(path, manifest)

    def test_lossless_signed_stereo_zero_frame_and_closed_finish(self):
        raws = [samples((-32768, 32767), (-1, 1)), b"", samples((0, 0))]
        path, summary = self.capture("retained", raws, checkpoint="a" * 64)
        loaded = pcm.load_capture(path)
        self.assertEqual((path.parent / "audio.s16le").read_bytes(), b"".join(raws))
        self.assertEqual(summary["sample_frames"], 3)
        self.assertEqual(summary["manifest_sha256"], digest(path.read_bytes()))
        self.assertEqual(summary["pcm_sha256"], digest(b"".join(raws)))
        manifest = loaded["manifest"]
        self.assertEqual(manifest["format"]["sample_rate"], {"numerator": 44100, "denominator": 1})
        self.assertEqual(manifest["format"]["sample_rate_binary64"], float(44100).hex())
        self.assertEqual([frame["sample_offset"] for frame in manifest["frames"]], [0, 2, 2])
        self.assertEqual(manifest["origin"], {"start_frame": 7, "sample_frame": 0, "checkpoint_sha256": "a" * 64})
        self.assertIn("not certified", summary["scope"])

    def test_equal_and_explicit_restored_suffix_replay(self):
        original, _ = self.capture("original")
        repeated, _ = self.capture("repeated")
        result = pcm.compare_captures(original, repeated)
        self.assertTrue(result["match"])
        self.assertEqual((result["matched_frames"], result["matched_sample_frames"]), (4, 4))
        restored, _ = self.capture("restored", [b"", samples((20, -30))], start=9, checkpoint="b" * 64)
        with self.assertRaisesRegex(pcm.LabError, "starting frame"):
            pcm.compare_captures(original, restored)
        result = pcm.compare_captures(original, restored, 2)
        self.assertTrue(result["match"])
        self.assertEqual((result["start_frame"], result["matched_frames"], result["matched_sample_frames"]), (9, 2, 1))
        for index in (-1, True, 4, 1.5):
            with self.subTest(index=index), self.assertRaises(pcm.LabError):
                pcm.compare_captures(original, repeated, index)

    def test_one_sample_mutation_reports_sample_and_channel_without_values(self):
        original, _ = self.capture("original")
        changed, _ = self.capture("changed", [samples((0, 0)), samples((-32768, 32767), (-1, 2)), b"", samples((20, -30))])
        report = pcm.compare_captures(original, changed)
        self.assertFalse(report["match"])
        self.assertEqual((report["first_frame"], report["sample_frame"], report["channel"]), (8, 2, 1))
        self.assertEqual(report["reason"], "PCM sample mismatch")
        self.assertNotIn("reference_value", report)
        self.assertNotIn("candidate_value", report)

    def test_channel_swap_shifted_dropped_and_repeated_samples_fail(self):
        a, b, c = samples((1, -2)), samples((3, -4)), samples((5, -6))
        original, _ = self.capture("original", [a + b + c])
        for name, raw in (("channels", samples((-2, 1), (-4, 3), (-6, 5))),
                          ("shifted", c + a + b), ("dropped", a + c), ("repeated", a + b + b + c)):
            changed, _ = self.capture(name, [raw])
            with self.subTest(name=name):
                self.assertFalse(pcm.compare_captures(original, changed)["match"])

    def test_identical_bytes_with_changed_frame_boundaries_fail(self):
        a, b = samples((1, 2)), samples((3, 4))
        original, _ = self.capture("original", [a, b])
        changed, _ = self.capture("changed", [a + b, b""])
        self.assertEqual((original.parent / "audio.s16le").read_bytes(), (changed.parent / "audio.s16le").read_bytes())
        result = pcm.compare_captures(original, changed)
        self.assertFalse(result["match"])
        self.assertEqual((result["first_frame"], result["sample_frame"], result["reason"]), (7, 0, "frame/sample boundary mismatch"))

    def test_extra_and_missing_capture_frames_fail(self):
        a = samples((1, 2))
        original, _ = self.capture("original", [a, a])
        short, _ = self.capture("short", [a])
        for left, right in ((original, short), (short, original)):
            result = pcm.compare_captures(left, right)
            self.assertFalse(result["match"])
            self.assertEqual((result["first_frame"], result["sample_frame"]), (8, 1))

    def test_input_timeline_and_component_identity_are_not_inferred_from_audio(self):
        original, _ = self.capture("original")
        changed, _ = self.capture("changed", inputs=[1] + [0] * 11)
        with self.assertRaisesRegex(pcm.LabError, "input timelines"):
            pcm.compare_captures(original, changed)
        self.rewrite_observations(changed, lambda value: value["identity"].update(core_sha256="a" * 64))
        with self.assertRaisesRegex(pcm.LabError, "component/AV"):
            pcm.compare_captures(original, changed)

    def test_rate_changes_cannot_be_normalized_or_resampled(self):
        original, _ = self.capture("original")
        changed, _ = self.capture("changed")
        self.rewrite_observations(changed, lambda value: value["av"].update(sample_rate=48000.0))
        manifest = self.manifest(changed)
        av = json.loads((changed.parent / "observations.json").read_text())["av"]
        manifest["format"] = pcm.audio_format(av)
        self.rewrite_manifest(changed, manifest)
        pcm.load_capture(changed)
        with self.assertRaisesRegex(pcm.LabError, "component/AV"):
            pcm.compare_captures(original, changed)

    def test_raw_tampering_truncation_and_trailing_bytes_are_rejected(self):
        for name, change in (("tamper", lambda raw: b"\x01" + raw[1:]),
                             ("truncate", lambda raw: raw[:-1]), ("trailing", lambda raw: raw + b"\x00")):
            path, _ = self.capture(name)
            raw_path = path.parent / "audio.s16le"
            raw_path.write_bytes(change(raw_path.read_bytes()))
            with self.subTest(name=name), self.assertRaises(pcm.LabError):
                pcm.load_capture(path)

    def test_same_size_mtime_restored_tampering_after_validation_cannot_pass(self):
        original_load = pcm.load_capture
        for coarse_metadata in (False, True):
            prefix = "coarse" if coarse_metadata else "real"
            original, _ = self.capture(prefix + "-original", [samples((1, 2))])
            candidate, _ = self.capture(prefix + "-candidate", [samples((1, 2))])
            loaded = []

            def race(path):
                result = original_load(path)
                loaded.append(result)
                if len(loaded) == 2:
                    # Both streams still agree with one another, but no longer
                    # agree with the evidence validated moments earlier.
                    for capture in loaded:
                        target = capture["pcm_path"]
                        before = target.stat()
                        target.write_bytes(samples((8, 9)))
                        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
                return result

            # Coarse/stale metadata additionally exercises the read-time digest
            # check instead of relying solely on the host's timestamp precision.
            metadata = patch.object(pcm, "signature", return_value=()) if coarse_metadata else patch.object(pcm, "signature", wraps=pcm.signature)
            with self.subTest(coarse_metadata=coarse_metadata), metadata, patch.object(pcm, "load_capture", side_effect=race):
                with self.assertRaisesRegex(pcm.LabError, "changed"):
                    pcm.compare_captures(original, candidate)

    def test_bad_maps_origins_rates_counts_and_bindings_cannot_self_compare(self):
        changes = [lambda m: m["frames"][0].update(sample_offset=1),
                   lambda m: m["frames"][1].update(sample_offset=0),
                   lambda m: m["frames"][0].update(sample_frames=True),
                   lambda m: m["frames"][0].update(frame=True),
                   lambda m: m["frames"][0].update(sha256="a" * 64),
                   lambda m: m["frames"].pop(), lambda m: m["pcm"].update(sample_frames=True),
                   lambda m: m["pcm"].update(bytes=3), lambda m: m["pcm"].update(sha256="b" * 64),
                   lambda m: m["observations"].update(sha256="c" * 64),
                   lambda m: m["format"].update(channels=1),
                   lambda m: m["format"].update(sample_rate_binary64=float(48000).hex()),
                   lambda m: m["format"]["sample_rate"].update(numerator=True),
                   lambda m: m["origin"].update(start_frame=8),
                   lambda m: m["origin"].update(sample_frame=True),
                   lambda m: m["origin"].update(checkpoint_sha256="bad"),
                   lambda m: m.update(extra="unknown"), lambda m: m.update(schema="future")]
        for index, change in enumerate(changes):
            path, _ = self.capture(str(index))
            manifest = self.manifest(path)
            change(manifest)
            self.rewrite_manifest(path, manifest)
            with self.subTest(index=index), self.assertRaises(pcm.LabError):
                pcm.compare_captures(path, path)

    def test_observation_metadata_must_be_complete_bounded_and_unchanged(self):
        changes = [lambda o: o.update(identity={}), lambda o: o.update(av={}),
                   lambda o: o["av"].update(sample_rate=True), lambda o: o["av"].update(fps_binary64="wrong"),
                   lambda o: o["frames"][0].update(audio_frames=pcm.MAX_FRAME_SAMPLES + 1),
                   lambda o: o["frames"][0].update(frame=True), lambda o: o["frames"][1].update(frame=10),
                   lambda o: o["frames"][0].update(inputs=[0]), lambda o: o["frames"][0].update(inputs=[True] * 12),
                   lambda o: o["frames"][0]["video"].update(width=True),
                   lambda o: o["frames"][0].update(audio_sha256="bad"), lambda o: o.update(extra="unknown")]
        for index, change in enumerate(changes):
            path, _ = self.capture(str(index))
            self.rewrite_observations(path, change)
            with self.subTest(index=index), self.assertRaises(pcm.LabError):
                pcm.load_capture(path)

    def test_empty_capture_fails_but_nonempty_silence_is_valid(self):
        path, _ = self.capture("silence", [b"", bytes(8), b""])
        self.assertTrue(pcm.compare_captures(path, path)["match"])
        for name, frames in (("empty", []), ("zero", [observation(0, b"")])):
            root = self.root / name
            root.mkdir()
            writer = pcm.PCMWriter(root)
            self.addCleanup(writer.close)
            for frame in frames:
                writer.append(frame, b"")
            observations_path = root / "observations.json"
            observations_path.write_text(json.dumps(observations(frames)))
            with self.assertRaisesRegex(pcm.LabError, "Empty PCM"):
                writer.finish(observations_path)
            self.assertFalse((root / "audio.json").exists())

    def test_append_and_budget_failures_never_publish_success(self):
        good = samples((1, 2))
        cases = [(observation(0, good), b"bad"),
                 (dict(observation(0, good), audio_sha256="a" * 64), good),
                 (dict(observation(0, good), audio_frames=True), good)]
        for index, (frame, raw) in enumerate(cases):
            root = self.root / str(index)
            root.mkdir()
            writer = pcm.PCMWriter(root)
            self.addCleanup(writer.close)
            with self.assertRaises(pcm.LabError):
                writer.append(frame, raw)
            with self.assertRaises(pcm.LabError):
                writer.finish(root / "observations.json")
            self.assertFalse((root / "audio.json").exists())
        root = self.root / "budget"
        root.mkdir()
        writer = pcm.PCMWriter(root, max_bytes=4)
        self.addCleanup(writer.close)
        writer.append(observation(0, good), good)
        with self.assertRaisesRegex(pcm.LabError, "budget"):
            writer.append(observation(1, good), good)
        self.assertFalse((root / "audio.json").exists())

    def test_close_is_repeatable_and_finish_rejects_changed_observations_or_raw(self):
        for name, target in (("observations", "observations.json"), ("raw", "audio.s16le")):
            root = self.root / name
            root.mkdir()
            raw = samples((1, 2))
            frame = observation(0, raw)
            writer = pcm.PCMWriter(root)
            writer.append(frame, raw)
            writer.close()
            writer.close()
            path = root / "observations.json"
            value = observations([frame])
            if target == "observations.json":
                value["frames"][0]["inputs"][0] = 1
            else:
                (root / target).write_bytes(samples((9, 9)))
            path.write_text(json.dumps(value))
            with self.assertRaises(pcm.LabError):
                writer.finish(path)
            self.assertFalse((root / "audio.json").exists())

    def test_write_errors_and_invalid_limits_are_not_success(self):
        root = self.root / "writer"
        root.mkdir()
        for bound in (0, 3, True, pcm.MAX_PCM_BYTES + 4):
            with self.subTest(bound=bound), self.assertRaises(pcm.LabError):
                pcm.PCMWriter(root, max_bytes=bound)
        writer = pcm.PCMWriter(root)
        original = writer.stream
        raw = samples((1, 2))
        try:
            with patch.object(writer, "stream") as stream:
                stream.closed = False
                stream.write.side_effect = OSError("synthetic disk full")
                with self.assertRaisesRegex(OSError, "disk full"):
                    writer.append(observation(0, raw), raw)
            with self.assertRaises(pcm.LabError):
                writer.finish(root / "observations.json")
        finally:
            original.close()
        self.assertFalse((root / "audio.json").exists())

    def test_no_overwrite_and_no_symlink_or_traversal(self):
        for name in ("audio.json", "audio.s16le"):
            root = self.root / name.replace(".", "_")
            root.mkdir()
            (root / name).write_bytes(b"preserve")
            with self.assertRaises(pcm.LabError):
                pcm.PCMWriter(root)
            self.assertEqual((root / name).read_bytes(), b"preserve")
        path, _ = self.capture("valid")
        for index, unsafe in enumerate(("../escape", str(path.parent / "audio.s16le"), "alias.s16le")):
            changed = self.manifest(path)
            changed["pcm"]["path"] = unsafe
            if unsafe == "alias.s16le":
                (path.parent / unsafe).symlink_to(path.parent / "audio.s16le")
            target = path.parent / f"bad-{index}.json"
            self.rewrite_manifest(target, changed)
            with self.assertRaises(pcm.LabError):
                pcm.load_capture(target)
        alias = self.root / "directory-alias"
        alias.symlink_to(path.parent, target_is_directory=True)
        with self.assertRaises(pcm.LabError):
            pcm.load_capture(alias / "audio.json")
        with self.assertRaises(pcm.LabError):
            pcm.PCMWriter(alias)

    def test_manifest_publication_cannot_overwrite_concurrent_output(self):
        root = self.root / "publication"
        root.mkdir()
        writer = pcm.PCMWriter(root)
        self.addCleanup(writer.close)
        raw = samples((1, 2))
        frame = observation(0, raw)
        writer.append(frame, raw)
        writer.close()
        path = root / "observations.json"
        path.write_text(json.dumps(observations([frame])))
        original_link = os.link

        def collision(source, target):
            target.write_bytes(b"preserve concurrent output")
            return original_link(source, target)

        with patch.object(pcm.os, "link", side_effect=collision):
            with self.assertRaises(FileExistsError):
                writer.finish(path)
        self.assertEqual((root / "audio.json").read_bytes(), b"preserve concurrent output")
        self.assertEqual(list(root.glob(".audio-manifest-*")), [])

    def test_missing_files_duplicate_json_and_size_bounds_fail(self):
        for name in ("audio.s16le", "observations.json"):
            path, _ = self.capture(name.replace(".", "_"))
            (path.parent / name).unlink()
            with self.assertRaises(pcm.LabError):
                pcm.load_capture(path)
        duplicate = self.root / "duplicate.json"
        duplicate.write_text('{"schema":"one","schema":"two"}')
        with self.assertRaisesRegex(pcm.LabError, "Duplicate"):
            pcm.load_capture(duplicate)
        oversized = self.root / "oversized.json"
        with oversized.open("wb") as stream:
            stream.truncate(pcm.MAX_MANIFEST_BYTES + 1)
        with self.assertRaisesRegex(pcm.LabError, "byte bound"):
            pcm.load_capture(oversized)
        path, _ = self.capture("big-pcm")
        with (path.parent / "audio.s16le").open("wb") as stream:
            stream.truncate(pcm.MAX_PCM_BYTES + 4)
        with self.assertRaises(pcm.LabError):
            pcm.load_capture(path)

    def test_cli_match_divergence_and_invalid_evidence_exit_codes(self):
        original, _ = self.capture("original", [samples((1, 2))])
        same, _ = self.capture("same", [samples((1, 2))])
        changed, _ = self.capture("changed", [samples((1, 3))])
        malformed = self.root / "malformed.json"
        malformed.write_text("{}")
        cli = Path(pcm.__file__).parent / "compare_pcm.py"
        for target, code in ((same, 0), (changed, 1), (malformed, 2)):
            result = subprocess.run([sys.executable, str(cli), str(original), str(target)],
                                    capture_output=True, text=True, timeout=10)
            with self.subTest(code=code):
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["match"], code == 0)


if __name__ == "__main__":
    unittest.main()
