"""Metadata boundaries only: no original game code or binary fixtures are used."""
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import code_inventory as inventory


class CodeInventoryTests(unittest.TestCase):
    def test_canonical_receipts_reproduce_distinct_overlay_identities(self):
        census = inventory.generate()
        inventory.verify(census, inventory.generate())
        self.assertEqual(census["coverage"]["candidate_mappings"], 15)
        self.assertFalse(census["coverage"]["whole_program_complete"])
        self.assertIsNone(census["coverage"]["function_denominator"])
        modules = {row["name"]: row for row in census["candidates"]
                   if row["release"] == "usa-mk81070-v1003"}
        self.assertEqual(modules["KRNL"]["load_address"], modules["XBAND"]["load_address"])
        self.assertNotEqual(modules["KRNL"]["id"], modules["XBAND"]["id"])
        self.assertEqual(modules["SND"]["cpu"], "m68000")
        self.assertEqual(modules["SND"]["bytes"], 0x63D4)

    def test_derived_templates_and_unknown_extents_are_not_original_modules(self):
        census = inventory.generate()
        modules = {row["name"]: row for row in census["candidates"]}
        for name in ("TRAMP", "IP_PATCHED"):
            self.assertFalse(modules[name]["original_byte_extent"])
            self.assertIsNone(modules[name]["bytes"])
            self.assertIsNone(modules[name]["derived_artifact_sha256"])
        self.assertTrue(modules["SAMPLEIP"]["original_byte_extent"])
        self.assertIsNone(modules["SAMPLEIP"]["load_address"])
        japan = [row for row in census["candidates"] if row["release"] == "japan-t14302g-v1000"]
        self.assertEqual([row["source_path"] for row in japan], ["@track01-system-area", "0KRNL.BIN"])

    def test_system_area_is_identified_without_classifying_all_bytes_as_code(self):
        rows = [row for row in inventory.generate()["candidates"] if row["name"] == "SYSTEM_BOOTSTRAP"]
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["bytes"], 32768)
            self.assertEqual(row["source_kind"], "track01-index01-relative-lba0-system-area")
            self.assertIsNone(row["load_address"])
            self.assertIsNone(row["classified_code_bytes"])
            self.assertIsNone(row["function_count"])

    def test_committed_census_matches_current_pinned_receipts(self):
        path = inventory.ROOT / "docs/restart/saturn-code/module-candidates.json"
        value, _ = inventory.read_json(path, 1024**2)
        inventory.verify(value, inventory.generate())

    def test_changed_source_mapping_dropped_overlay_and_false_completion_rejected(self):
        expected = inventory.generate()
        for kind in ("source", "mapping", "drop", "duplicate", "complete", "denominator", "integer-bool"):
            changed = deepcopy(expected)
            if kind == "source":
                changed["candidates"][0]["source_sha256"] = "0" * 64
            elif kind == "mapping":
                changed["candidates"][0]["load_address"] = 0x06002000
            elif kind == "drop":
                changed["candidates"].pop()
            elif kind == "duplicate":
                changed["candidates"].append(deepcopy(changed["candidates"][0]))
            elif kind == "complete":
                changed["coverage"]["whole_program_complete"] = True
            elif kind == "denominator":
                changed["coverage"]["function_denominator"] = 13
            else:
                changed["coverage"]["whole_program_complete"] = 0
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                inventory.verify(changed, expected)

    def test_confined_source_paths_and_duplicate_file_identities(self):
        base = {"schema": "neptune.saturn-disc-inventory.v1", "iso9660": {"files": [
            {"path": "CODE.BIN", "byte_length": 32, "sha256": "a" * 64}]}}
        for path in ("", "/CODE.BIN", "../CODE.BIN", "a/../CODE.BIN", "a\\CODE.BIN", "a//CODE.BIN", "./CODE.BIN"):
            value = deepcopy(base)
            value["iso9660"]["files"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                inventory.files(value)
        value = deepcopy(base)
        value["iso9660"]["files"] *= 2
        with self.assertRaises(ValueError):
            inventory.files(value)
        for rows in ([], "not-a-table"):
            value = deepcopy(base)
            value["iso9660"]["files"] = rows
            with self.assertRaises(ValueError):
                inventory.files(value)

    def test_source_slice_bounds_and_mapping_lifetime(self):
        source = {"CODE.BIN": {"byte_length": 32, "sha256": "a" * 64,
                                "classification": {"detected_format": "synthetic-only"}}}
        definition = ("CODE", "CODE.BIN", 0, 16, "sh2-role-unresolved", 0x200000, "scene-one", "original-slice-lead", [])
        first = inventory.mapping("synthetic", definition, source)
        second = inventory.mapping("synthetic", (*definition[:6], "scene-two", *definition[7:]), source)
        self.assertNotEqual(first["id"], second["id"])
        for offset, length in ((-1, 16), (32, 1), (1, 32), (0, 0), (0, True)):
            changed = (*definition[:2], offset, length, *definition[4:])
            with self.subTest(offset=offset, length=length), self.assertRaises(ValueError):
                inventory.mapping("synthetic", changed, source)

    def test_stale_receipt_hash_rejected_before_build(self):
        wrong = dict(inventory.RECEIPTS)
        wrong["usa-mk81070-v1003"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "identity changed"):
            inventory.build({key: {} for key in inventory.RECEIPTS}, wrong)
        with self.assertRaisesRegex(ValueError, "separate USA and Japan"):
            inventory.build({}, {})

    def test_duplicate_json_empty_symlink_and_size_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "metadata.json"
            for raw in ('{"schema":1,"schema":2}', '[]', ''):
                source.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    inventory.read_json(source, 1024)
            source.write_text('{"schema":"synthetic"}')
            with self.assertRaises(ValueError):
                inventory.read_json(source, 8)
            link = root / "linked.json"
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                inventory.read_json(link, 1024)
            with self.assertRaises(ValueError):
                inventory.read_json(root, 1024)

    def test_cli_exclusive_output_and_stale_census_failure(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            output = Path(directory) / "census.json"
            args = ["--census", str(output)]
            self.assertEqual(inventory.main(["generate", *args]), 0)
            accepted = output.read_bytes()
            self.assertEqual(inventory.main(["verify", *args]), 0)
            self.assertEqual(inventory.main(["generate", *args]), 1)
            self.assertEqual(output.read_bytes(), accepted)
            value = json.loads(accepted)
            value["candidates"].pop()
            output.write_text(json.dumps(value))
            self.assertEqual(inventory.main(["verify", *args]), 1)


if __name__ == "__main__":
    unittest.main()
