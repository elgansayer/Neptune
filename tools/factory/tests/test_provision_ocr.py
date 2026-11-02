"""OCR recipe negative cases; real upstream build/recognition is separate evidence."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import provision as p
import provision_ocr as ocr


class OcrTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.recipe = json.loads((p.ROOT / "tools/factory/provision-lock.json").read_text())["tools"]["tesseract"]

    def test_only_reviewed_versioned_upstream_sources_are_accepted(self):
        ocr.validate(self.recipe)
        for field, value in [("url", "https://example.com/model"), ("sha256", "bad"),
                             ("bytes", True), ("bytes", 101 * 1024**2)]:
            recipe = copy.deepcopy(self.recipe)
            recipe["sources"]["english"][field] = value
            with self.subTest(field=field), self.assertRaises(p.ProvisionError):
                ocr.validate(recipe)
        for change in [dict(version="5.6-beta"), dict(cmake_version="4.4.6"),
                       dict(commands=["untrusted issue command"])]:
            with self.subTest(change=change), self.assertRaises(p.ProvisionError):
                ocr.validate(dict(self.recipe, **change))

    def test_download_hash_and_length_are_required(self):
        data = b"public source fixture"
        source = dict(url="https://example.invalid/test", bytes=len(data),
                      sha256=hashlib.sha256(data).hexdigest())
        for name, content, accepted in [("correct", data, True), ("short", data[:-1], False),
                                         ("long", data + b"!", False), ("changed", b"x" * len(data), False)]:
            with self.subTest(name=name), patch.object(ocr.urllib.request, "urlopen", return_value=io.BytesIO(content)):
                target = self.home / name
                if accepted:
                    ocr.fetch(source, target)
                    self.assertEqual(target.read_bytes(), data)
                else:
                    with self.assertRaises(p.ProvisionError):
                        ocr.fetch(source, target)

    def archive(self, members):
        path = self.home / "source.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, kind in members:
                member = tarfile.TarInfo(name)
                if kind == "link":
                    member.type, member.linkname = tarfile.SYMTYPE, "../../outside"
                else:
                    member.size = 3
                    member.mode = 0o6755
                archive.addfile(member, io.BytesIO(b"abc") if kind != "link" else None)
        return path

    def test_source_archives_reject_escape_links_duplicates_and_multiple_roots(self):
        for index, members in enumerate([
                [("../outside", "file")], [("/outside", "file")], [("root/link", "link")],
                [("root/file", "file"), ("root/file", "file")],
                [("root/file", "file"), ("other/file", "file")]]):
            with self.subTest(members=members), self.assertRaises(p.ProvisionError):
                ocr.unpack(self.archive(members), self.home / str(index))
            self.assertFalse((self.home / str(index)).exists())

    def test_regular_source_files_are_preserved_without_privileged_modes(self):
        tree = ocr.unpack(self.archive([("root/bin/tool", "file")]), self.home / "tree")
        self.assertEqual((tree / "bin/tool").read_bytes(), b"abc")
        self.assertEqual((tree / "bin/tool").stat().st_mode & 0o7777, 0o755)

    def runner(self):
        runner = MagicMock()
        runner.evidence = self.home / "evidence"
        runner.evidence.mkdir(exist_ok=True)
        runner.run.side_effect = ["tesseract 5.5.4\n leptonica-1.87.0", ocr.TEXT]
        return runner

    def model(self):
        data = self.home / "tessdata/eng.traineddata"
        data.parent.mkdir(exist_ok=True)
        data.write_bytes(b"synthetic model for smoke-contract tests only")
        self.recipe["sources"]["english"]["sha256"] = p.digest(data)
        return data

    def test_smoke_requires_model_identity_versions_and_correct_actual_text(self):
        data = self.model()
        result = ocr.smoke(self.recipe, self.home / "tesseract", self.runner())
        self.assertEqual(result["text"], "NEPTUNE READY")
        self.assertEqual(result["traineddata_sha256"], p.digest(data))
        for actual in ["", "NEPTUNE", "NEPTUNE READV"]:
            runner = self.runner()
            runner.run.side_effect = ["tesseract 5.5.4\n leptonica-1.87.0", actual]
            with self.subTest(actual=actual), self.assertRaises(p.ProvisionError):
                ocr.smoke(self.recipe, self.home / "tesseract", runner)
        runner = self.runner()
        runner.run.side_effect = ["tesseract 5.5.0\n leptonica-1.84.1"]
        with self.assertRaises(p.ProvisionError):
            ocr.smoke(self.recipe, self.home / "tesseract", runner)
        data.write_bytes(b"tampered")
        with self.assertRaises(p.ProvisionError):
            ocr.smoke(self.recipe, self.home / "tesseract", self.runner())
        data.unlink()
        with self.assertRaises(p.ProvisionError):
            ocr.smoke(self.recipe, self.home / "tesseract", self.runner())

    def test_missing_build_tool_stops_before_download_or_model_execution(self):
        runner = self.runner()
        with patch.object(ocr.shutil, "which", return_value=None), self.assertRaises(p.ProvisionError):
            ocr.install(self.recipe, self.home, self.home, runner, p.ROOT)
        runner.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
