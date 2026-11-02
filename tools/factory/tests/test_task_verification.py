"""Real Git task boundaries with synthetic check results; no fidelity/authenticity claim."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import readiness
import verify


class TaskVerificationTests(unittest.TestCase):
    FAILURES = (ValueError, OSError, subprocess.SubprocessError)
    OWNED = "docs/owned.md"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name)
        self.root = self.private / "repo"
        self.root.mkdir()
        self.git("init", "--quiet", "-b", "main")
        self.git("config", "user.name", "Synthetic task fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.hooksPath", "/dev/null")
        self.write(".gitignore", ".godot/\n")
        self.write(self.OWNED, "base\n")
        self.write("docs/rename-source.md", "rename witness\n")
        self.write("protected.md", "outside the bounded task\n")
        self.commit("initial fixture")
        self.base = self.git("rev-parse", "HEAD")
        self.write(self.OWNED, "candidate\n")
        self.commit("bounded change")
        self.head = self.git("rev-parse", "HEAD")
        self.now = 1000
        self.intake = self.private / "intake.json"
        self.cache = self.private / "unused-cache"
        self.paths = [self.OWNED]
        self.calls = []
        self.save_snapshot()

    def git(self, *arguments):
        result = subprocess.run(["git", *arguments], cwd=self.root, check=True,
                                capture_output=True, text=True, timeout=10)
        return result.stdout.strip()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "--quiet", "--no-gpg-sign", "-m", message)

    def snapshot(self):
        return {"schema": "neptune.factory-intake.v1", "captured_at": 1000,
                "base_sha": self.base,
                "task": {"repository": "elgansayer/Neptune-Bomberman", "issue": 559,
                         "feature_id": "FACTORY-006", "revision": "b" * 64,
                         "kind": "implementation", "state": "open",
                         "acceptance": ["Reject a candidate outside the accepted task scope"],
                         "evidence": ["Retain exact Git and command identities"],
                         "prerequisites": [], "capabilities": ["python"],
                         "scope": {"goal": "Enforce a bounded candidate contract",
                                   "paths": ["docs"], "max_files": 4}},
                "available_capabilities": ["python"], "prerequisite_evidence": {},
                "active_work": []}

    def save_snapshot(self, snapshot=None):
        snapshot = self.snapshot() if snapshot is None else snapshot
        self.intake.write_text(json.dumps(snapshot, sort_keys=True))
        return snapshot

    def bind(self, paths=None):
        return verify.task_binding(self.intake, self.paths if paths is None else paths,
                                   self.root, lambda: self.now)

    def runner(self, command, **kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    def run_verification(self, name="verification", runner=None, intake=True):
        kwargs = {"root": self.root, "runner": runner or self.runner}
        if intake:
            kwargs.update(intake=self.intake, now=lambda: self.now)
        with contextlib.redirect_stdout(io.StringIO()):
            return verify.verify(self.paths, self.private / name, self.cache, **kwargs)

    def assert_run_rejected(self, name, runner):
        with self.assertRaises(self.FAILURES):
            self.run_verification(name, runner=runner)
        report = json.loads((self.private / name / "report.json").read_text())
        self.assertEqual(report["conclusion"], "failure")

    def test_binding_uses_real_commits_full_task_and_raw_snapshot_bytes(self):
        snapshot = self.snapshot()
        binding = self.bind([self.OWNED, self.OWNED])
        self.assertEqual(binding, {
            "repository": snapshot["task"]["repository"], "issue": 559,
            "feature_id": "FACTORY-006", "revision": "b" * 64,
            "task_sha256": readiness.digest(snapshot["task"]),
            "intake_sha256": hashlib.sha256(self.intake.read_bytes()).hexdigest(),
            "base": self.base, "head": self.head, "changed_paths": [self.OWNED]})

    def test_opt_in_preserves_baseline_checks_and_legacy_report_shape(self):
        legacy = self.run_verification("legacy", intake=False)
        self.assertNotIn("task_binding", legacy)
        self.assertNotIn("base", legacy["identity"])
        self.calls.clear()
        report = self.run_verification()
        self.assertEqual(report["schema"], legacy["schema"])
        self.assertEqual(report["conclusion"], "success")
        self.assertEqual(report["plan"], legacy["plan"])
        self.assertEqual(list(report["checks"]), list(verify.gate.CORE))
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(report["identity"]["base"], self.base)
        self.assertEqual(report["task_binding"], self.bind())

    def test_complete_changed_set_cannot_be_omitted_or_invented(self):
        self.write("docs/second.md", "second accepted file\n")
        self.commit("second candidate change")
        for selected in ([self.OWNED], ["docs/second.md"],
                         [self.OWNED, "docs/second.md", "docs/not-changed.md"]):
            with self.subTest(selected=selected), self.assertRaises(self.FAILURES):
                self.bind(selected)
        self.assertEqual(self.bind(["docs/second.md", self.OWNED])["changed_paths"],
                         [self.OWNED, "docs/second.md"])

    def test_scope_uses_component_boundaries_and_supports_literal_files(self):
        snapshot = self.snapshot()
        snapshot["task"]["scope"]["paths"] = [self.OWNED]
        self.save_snapshot(snapshot)
        self.assertEqual(self.bind()["changed_paths"], [self.OWNED])
        self.write("docs_extra/escape.md", "not inside docs\n")
        self.commit("prefix escape")
        self.save_snapshot()
        with self.assertRaises(self.FAILURES):
            self.bind([self.OWNED, "docs_extra/escape.md"])

    def test_actual_changed_file_count_respects_max_files(self):
        self.write("docs/second.md", "second\n")
        self.commit("two changed files")
        snapshot = self.snapshot()
        snapshot["task"]["scope"]["max_files"] = 1
        self.save_snapshot(snapshot)
        with self.assertRaises(self.FAILURES):
            self.bind([self.OWNED, "docs/second.md"])

    def test_rename_reserves_both_source_and_destination(self):
        self.git("mv", "docs/rename-source.md", "docs/renamed.md")
        self.commit("rename within scope")
        selected = [self.OWNED, "docs/rename-source.md", "docs/renamed.md"]
        self.assertEqual(self.bind(selected)["changed_paths"], sorted(selected))
        with self.assertRaises(self.FAILURES):
            self.bind([self.OWNED, "docs/renamed.md"])
        snapshot = self.snapshot()
        snapshot["task"]["scope"]["max_files"] = 2
        self.save_snapshot(snapshot)
        with self.assertRaises(self.FAILURES):
            self.bind(selected)

    def test_rename_cannot_move_content_outside_scope(self):
        self.git("mv", "docs/rename-source.md", "escaped.md")
        self.commit("rename outside scope")
        with self.assertRaises(self.FAILURES):
            self.bind([self.OWNED, "docs/rename-source.md", "escaped.md"])

    def test_leading_whitespace_filename_is_retained_in_the_actual_diff(self):
        relative = " leading.md"
        self.write(relative, "literal leading whitespace\n")
        self.commit("whitespace filename")
        snapshot = self.snapshot()
        snapshot["task"]["scope"]["paths"].append(relative)
        self.save_snapshot(snapshot)
        self.assertEqual(self.bind([self.OWNED, relative])["changed_paths"],
                         sorted([self.OWNED, relative]))

    def test_stale_future_malformed_and_not_ready_intakes_fail(self):
        variants = []
        for captured_at in (99, 1001):
            value = self.snapshot(); value["captured_at"] = captured_at; variants.append(value)
        missing = self.snapshot(); del missing["task"]["acceptance"]; variants.append(missing)
        unavailable = self.snapshot(); unavailable["available_capabilities"] = []; variants.append(unavailable)
        dependency = self.snapshot(); dependency["task"]["prerequisites"] = ["SIM-001"]; variants.append(dependency)
        closed = self.snapshot(); closed["task"]["state"] = "closed"; variants.append(closed)
        for value in variants:
            self.save_snapshot(value)
            with self.subTest(value=value), self.assertRaises(self.FAILURES):
                self.bind()
        for text in ("{", "[]", "null"):
            self.intake.write_text(text)
            with self.subTest(text=text), self.assertRaises(self.FAILURES):
                self.bind()

    def test_duplicate_keys_and_oversized_valid_json_are_rejected(self):
        original = self.intake.read_text()
        self.intake.write_text(original[:-1] + ', "captured_at": 1000}')
        with self.assertRaisesRegex(ValueError, "[Dd]uplicate"):
            self.bind()
        oversized = self.snapshot()
        oversized["task"]["acceptance"] = ["x" * (256 * 1024)]
        self.save_snapshot(oversized)
        with self.assertRaisesRegex(ValueError, "bound|KiB|size|exceed"):
            self.bind()

    def test_missing_and_symlinked_intake_files_are_rejected(self):
        original = self.intake
        file_alias = self.private / "intake-alias.json"
        file_alias.symlink_to(original)
        directory_alias = self.private / "directory-alias"
        directory_alias.symlink_to(self.private, target_is_directory=True)
        for path in (file_alias, directory_alias / "intake.json", self.private / "missing.json"):
            self.intake = path
            with self.subTest(path=path), self.assertRaises(self.FAILURES):
                self.bind()
        self.intake = original

    def test_other_repository_fails_but_expected_repository_is_case_insensitive(self):
        snapshot = self.snapshot()
        snapshot["task"]["repository"] = "ElganSayer/NEPTUNE-BOMBERMAN"
        self.save_snapshot(snapshot)
        self.bind()
        snapshot["task"]["repository"] = "example/another-game"
        self.save_snapshot(snapshot)
        with self.assertRaises(self.FAILURES):
            self.bind()

    def test_missing_and_nonancestor_base_commits_fail(self):
        unrelated = self.git("commit-tree", self.git("rev-parse", "HEAD^{tree}"),
                             "-m", "unrelated root commit")
        for base in ("0" * 40, unrelated):
            snapshot = self.snapshot(); snapshot["base_sha"] = base
            self.save_snapshot(snapshot)
            with self.subTest(base=base), self.assertRaises(self.FAILURES):
                self.bind()

    def test_dirty_tracked_worktree_cannot_pass(self):
        self.write(self.OWNED, "uncommitted source\n")
        with self.assertRaises(self.FAILURES):
            self.bind()

    def test_staged_source_cannot_pass(self):
        self.write("protected.md", "uncommitted staged change\n")
        self.git("add", "protected.md")
        with self.assertRaises(self.FAILURES):
            self.bind()

    def test_assume_unchanged_cannot_hide_unselected_dirty_source(self):
        self.git("update-index", "--assume-unchanged", "protected.md")
        self.write("protected.md", "hidden from ordinary git status\n")
        self.assertEqual(self.git("status", "--porcelain"), "")
        with self.assertRaises(self.FAILURES):
            self.bind()

    def test_skip_worktree_cannot_hide_unselected_dirty_source(self):
        self.git("update-index", "--skip-worktree", "protected.md")
        self.write("protected.md", "hidden from ordinary git status\n")
        self.assertEqual(self.git("status", "--porcelain"), "")
        with self.assertRaises(self.FAILURES):
            self.bind()

    def test_untracked_source_cannot_pass_but_ignored_outputs_are_allowed(self):
        self.write(".godot/runtime-output.txt", "ignored output\n")
        self.bind()
        self.write("docs/untracked.md", "undisclosed source\n")
        with self.assertRaises(self.FAILURES):
            self.bind()

    def test_selected_and_unselected_source_changes_during_checks_fail(self):
        def change_selected(command, **kwargs):
            self.write(self.OWNED, "changed after acceptance\n")
            return self.runner(command, **kwargs)
        self.assert_run_rejected("selected-change", change_selected)
        self.git("restore", self.OWNED)
        def change_unselected(command, **kwargs):
            self.write("protected.md", "outside the selected digest\n")
            return self.runner(command, **kwargs)
        self.assert_run_rejected("unselected-change", change_unselected)

    def test_new_untracked_source_during_checks_fails(self):
        def introduce_source(command, **kwargs):
            self.write("docs/undeclared.md", "new source\n")
            return self.runner(command, **kwargs)
        self.assert_run_rejected("untracked-change", introduce_source)

    def test_same_semantic_intake_with_different_retained_bytes_fails(self):
        changed = False
        def replace_intake(command, **kwargs):
            nonlocal changed
            if not changed:
                self.intake.write_text(self.intake.read_text() + "\n")
                changed = True
            return self.runner(command, **kwargs)
        self.assert_run_rejected("intake-change", replace_intake)

    def test_head_only_change_during_checks_fails(self):
        changed = False
        def advance_head(command, **kwargs):
            nonlocal changed
            if not changed:
                self.git("commit", "--quiet", "--no-gpg-sign", "--allow-empty", "-m", "different candidate head")
                changed = True
            return self.runner(command, **kwargs)
        self.assert_run_rejected("head-change", advance_head)

    def test_intake_expiring_during_checks_fails(self):
        def exhaust_freshness(command, **kwargs):
            self.now = 1901
            return self.runner(command, **kwargs)
        self.assert_run_rejected("expired-during-checks", exhaust_freshness)

    def test_plan_rejects_intake_without_reading_or_running_it(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(verify, "task_binding", side_effect=AssertionError("plan read intake")), \
             patch.object(verify, "verify", side_effect=AssertionError("plan ran checks")), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), \
             self.assertRaises(SystemExit) as raised:
            verify.main(["--plan", "--changed-path", self.OWNED, "--intake", str(self.intake)])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(output.getvalue(), "")

    def test_cli_receipt_adds_binding_only_for_opt_in_verification(self):
        original = verify.verify
        def in_temporary_repository(paths, evidence, toolchain, **kwargs):
            return original(paths, evidence, toolchain, root=self.root,
                            runner=self.runner, now=lambda: self.now, **kwargs)
        for use_intake in (False, True):
            args = ["--changed-path", self.OWNED, "--toolchain", str(self.cache),
                    "--evidence", str(self.private / ("cli-bound" if use_intake else "cli-legacy"))]
            if use_intake:
                args.extend(["--intake", str(self.intake)])
            output = io.StringIO()
            with patch.object(verify, "verify", side_effect=in_temporary_repository), \
                 contextlib.redirect_stdout(output):
                self.assertEqual(verify.main(args), 0)
            receipts = [line for line in output.getvalue().splitlines()
                        if line.startswith("NEPTUNE_FACTORY_VERIFICATION=")]
            self.assertEqual(len(receipts), 1)
            receipt = json.loads(receipts[0].split("=", 1)[1])
            self.assertEqual(set(receipt), {"schema", "identity", "plan", "checks", "conclusion"}
                             | ({"task_binding"} if use_intake else set()))
            self.assertEqual(receipt["conclusion"], "success")
            self.assertEqual("base" in receipt["identity"], use_intake)
            if use_intake:
                self.assertEqual(receipt["task_binding"], self.bind())


if __name__ == "__main__":
    unittest.main()
