"""Protect factory planning against invalid dependency and publication metadata."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "docs/restart/backlog"
spec = importlib.util.spec_from_file_location("neptune_backlog", SOURCE / "build_catalogue.py")
backlog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backlog)


class BacklogContracts(unittest.TestCase):
    def test_cycle_is_rejected_before_task_selection(self):
        with patch.dict(backlog.DEPS, {"SIM-001": ["SIM-002"]}):
            with self.assertRaisesRegex(ValueError, "Dependency cycle"):
                backlog.read_features()

    def test_unknown_prerequisite_is_rejected(self):
        with patch.dict(backlog.DEPS, {"SIM-001": ["MISSING-001"]}):
            with self.assertRaisesRegex(ValueError, "Invalid dependency"):
                backlog.read_features()

    def _fixture(self, directory):
        root = Path(directory)
        for name in ("features.tsv", "catalogue.json", "issue-links.json", "INDEX.md"):
            (root / name).write_text((SOURCE / name).read_text())
        return root

    def _run(self, root, check=True):
        args = ["build_catalogue.py"] + (["--check"] if check else [])
        with patch.object(backlog, "ROOT", root), patch("sys.argv", args):
            with contextlib.redirect_stdout(io.StringIO()):
                backlog.main()

    def test_stale_index_fails_without_rewriting_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._fixture(directory)
            (root / "INDEX.md").write_text("stale index\n")
            with self.assertRaisesRegex(ValueError, "INDEX.md is stale"):
                self._run(root)
            self.assertEqual((root / "INDEX.md").read_text(), "stale index\n")

    def test_unpublished_feature_cannot_pass_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._fixture(directory)
            links = json.loads((root / "issue-links.json").read_text())
            del links["FACTORY-001"]
            (root / "issue-links.json").write_text(json.dumps(links))
            self._run(root, check=False)
            with self.assertRaisesRegex(ValueError, "Not all features"):
                self._run(root)

    def test_duplicate_issue_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._fixture(directory)
            links = json.loads((root / "issue-links.json").read_text())
            links["FACTORY-002"] = links["FACTORY-001"]
            (root / "issue-links.json").write_text(json.dumps(links))
            with self.assertRaisesRegex(ValueError, "Two features linked"):
                self._run(root)


if __name__ == "__main__":
    unittest.main()
