"""Native auto-merge must wait for applicable preparation, including rename sources."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import provision_applicability as p


class ApplicabilityTests(unittest.TestCase):
    def test_real_preparation_paths_and_unrelated_paths(self):
        for path in ("tools/factory/provision_call_trace.h", "tools/factory/provision-lock.json",
                     "tools/factory/tests/test_provision_ocr.py", "tools/godot/install.py",
                     "tools/godot/toolchain.json", ".github/workflows/tool-provisioning.yml",
                     "tools/saturn_lab/m68k_scsp_dsp.py", "tools/saturn_lab/m68k_scsp_state.py",
                     "tools/saturn_lab/m68k_consumer_native.py", "tools/saturn_lab/tests/test_m68k_scsp_state.py", "tools/saturn_lab/scsp-dsp-source-lock.json",
                     "tools/saturn_lab/tests/test_m68k_scsp_dsp.py", "tools/saturn_lab/m68k_probe_backend.c", "tools/saturn_lab/probe_kernel.py"):
            with self.subTest(path=path):
                self.assertTrue(p.required(["docs/README.md", path]))
        self.assertFalse(p.required(["docs/README.md", "shared/game.gd", "tools/saturn_lab/probe_netlink_initializer.py"]))
        for paths in ([], None, [""], ["../escape"], ["/absolute"], ["tools/../docs"], ["a\\b"], ["bad\nname"]):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                p.required(paths)

    def passing(self, required=True):
        selected = {"identity": {"base": "b" * 40, "head": "a" * 40},
                    "required": required, "paths": ["tools/factory/provision.py"] if required else ["README.md"]}
        needs = {"applicability": {"result": "success", "outputs": {
            "required": str(required).lower(), "selection_sha256": p.digest(selected)}}}
        needs.update({name: {"result": "success" if required else "skipped"} for name in p.CHILDREN})
        return selected, needs

    def test_explicit_non_applicability_and_complete_success(self):
        for required in (False, True):
            selected, needs = self.passing(required)
            self.assertEqual(p.assert_needs(needs, selected)["required"], required)

    def test_required_missing_skipped_failed_and_unknown_results_never_pass(self):
        for job in ("applicability", *p.CHILDREN):
            for status in (None, "skipped", "failure", "cancelled", "neutral", "timed_out", "running"):
                selected, needs = self.passing()
                needs[job]["result"] = status
                with self.subTest(job=job, status=status), self.assertRaises(ValueError):
                    p.assert_needs(needs, selected)
            selected, needs = self.passing()
            del needs[job]
            with self.assertRaises(ValueError):
                p.assert_needs(needs, selected)

    def test_false_output_stale_selection_and_missing_output_fail(self):
        selected, needs = self.passing()
        for outputs in ({}, {"required": "false", "selection_sha256": p.digest(selected)},
                        {"required": "true", "selection_sha256": "0" * 64}):
            changed = deepcopy(needs)
            changed["applicability"]["outputs"] = outputs
            with self.subTest(outputs=outputs), self.assertRaises(ValueError):
                p.assert_needs(changed, selected)
        changed = deepcopy(selected)
        changed["identity"]["head"] = "c" * 40
        with self.assertRaises(ValueError):
            p.assert_needs(needs, changed)
        selected, needs = self.passing(False)
        needs["ocr"]["result"] = "failure"
        with self.assertRaises(ValueError):
            p.assert_needs(needs, selected)

    def test_duplicate_and_oversized_metadata_are_rejected(self):
        for raw in ('{"same":1,"same":2}', ' ' * (1024**2 + 1)):
            with self.assertRaises(ValueError):
                p.bounded_json(raw)


class RealGitSelection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Preparation Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        for name in ("tools/factory/provision-old.py", "tools/godot/install.py", "docs/README.md"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("owned fixture " + name)
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.git("switch", "-qc", "candidate")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.STDOUT,
                                       text=True, timeout=10)

    def merge(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "candidate")
        head = self.git("rev-parse", "HEAD").strip()
        self.git("switch", "-q", "main")
        self.git("merge", "--no-ff", "candidate", "-qm", "synthetic PR merge")
        return {"number": 123, "pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}

    def test_actual_renamed_out_installer_and_deleted_installer_require_preparation(self):
        self.git("mv", "tools/factory/provision-old.py", "docs/moved.py")
        self.git("rm", "-q", "tools/godot/install.py")
        event = self.merge()
        selected = p.selection(event, "pull_request", self.root)
        self.assertTrue(selected["required"])
        self.assertIn("tools/factory/provision-old.py", selected["paths"])
        self.assertIn("tools/godot/install.py", selected["paths"])
        self.assertIn("docs/moved.py", selected["paths"])
        wrong = deepcopy(event)
        wrong["pull_request"]["head"]["sha"] = self.base
        with self.assertRaisesRegex(ValueError, "Stale/different"):
            p.selection(wrong, "pull_request", self.root)

    def test_actual_metadata_merge_is_proven_unrelated_and_manual_is_full(self):
        (self.root / "docs/README.md").write_text("changed owned fixture")
        event = self.merge()
        selected = p.selection(event, "pull_request", self.root)
        self.assertFalse(selected["required"])
        self.assertEqual(selected["paths"], ["docs/README.md"])
        self.assertTrue(p.selection({}, "workflow_dispatch", self.root)["required"])
        with self.assertRaises(ValueError):
            p.selection(event, "unknown", self.root)


if __name__ == "__main__":
    unittest.main()
