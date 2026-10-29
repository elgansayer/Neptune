from copy import deepcopy
import json
import multiprocessing
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from readiness import ContractError, evaluate
from store import JobStore


def snapshot(issue=71, feature="FACTORY-001", path="tools/factory"):
    return {"schema": "neptune.factory-intake.v1", "captured_at": 1000, "base_sha": "a" * 40,
            "task": {"repository": "example/game", "issue": issue, "feature_id": feature,
                     "revision": "b" * 64, "kind": "implementation", "state": "open",
                     "acceptance": ["Reject stale intake"], "evidence": ["Run failure cases"],
                     "prerequisites": [], "capabilities": ["python"],
                     "scope": {"goal": "Validate readiness", "paths": [path], "max_files": 10}},
            "available_capabilities": ["python"], "prerequisite_evidence": {}, "active_work": []}


def compete(path, job, owner, start, output):
    store = JobStore(path, lambda: 1000)
    try:
        if not start.wait(10):
            raise RuntimeError("start barrier timed out")
        try:
            output.put(("won", store.claim(job, owner)))
        except ContractError as error:
            output.put(("lost", str(error)))
    finally:
        store.close()


def interrupted_write(path, job, ready):
    store = JobStore(path, lambda: 1000)
    store.db.execute("BEGIN IMMEDIATE")
    store.db.execute("UPDATE jobs SET checkpoint='uncommitted' WHERE id=?", (job,))
    ready.set()
    # Parent terminates the process while SQLite owns an unfinished transaction.
    multiprocessing.Event().wait(20)


class Intake(unittest.TestCase):
    def test_complete_snapshot_is_ready(self):
        result = evaluate(snapshot(), 1000)
        self.assertTrue(result["ready"])
        self.assertEqual(len(result["task_digest"]), 64)

    def test_missing_contract_fields_are_not_ready(self):
        for field in snapshot()["task"]:
            value = snapshot()
            del value["task"][field]
            with self.subTest(field=field):
                self.assertFalse(evaluate(value, 1000)["ready"])

    def test_epic_empty_acceptance_and_unbounded_scope_rejected(self):
        changes = [("kind", "epic"), ("kind", "roadmap"), ("state", "closed"),
                   ("acceptance", []), ("evidence", [""]), ("revision", "current"),
                   ("feature_id", "TODO"), ("issue", True)]
        for key, value in changes:
            data = snapshot()
            data["task"][key] = value
            with self.subTest(key=key, value=value):
                self.assertFalse(evaluate(data, 1000)["ready"])
        for value in (0, 21, True, "5"):
            data = snapshot()
            data["task"]["scope"]["max_files"] = value
            self.assertFalse(evaluate(data, 1000)["ready"])

    def test_literal_safe_paths_required(self):
        for path in (".", "/etc", "../game", "ai/../game", "ai//tasks", "ai/*", "ai/", "C:\\game"):
            with self.subTest(path=path):
                self.assertFalse(evaluate(snapshot(path=path), 1000)["ready"])

    def test_stale_future_missing_capability_fail(self):
        self.assertFalse(evaluate(snapshot(), 1901)["ready"])
        self.assertFalse(evaluate(snapshot(), 999)["ready"])
        value = snapshot()
        value["available_capabilities"] = []
        self.assertIn("missing capabilities: python", evaluate(value, 1000)["reasons"])

    def test_closed_prerequisite_is_not_verified_evidence(self):
        data = snapshot()
        data["task"]["prerequisites"] = ["SIM-001"]
        for proof in ({}, {"state": "closed"}, {"status": "verified"}):
            data["prerequisite_evidence"]["SIM-001"] = proof
            self.assertFalse(evaluate(data, 1000)["ready"])
        data["prerequisite_evidence"]["SIM-001"] = {"status": "verified", "head_sha": "c" * 40, "base_sha": "d" * 40, "report_sha256": "e" * 64, "evidence_ref": "private:evidence/accepted"}
        self.assertTrue(evaluate(data, 1000)["ready"])

    def test_pr_overlap_by_feature_issue_or_path(self):
        for issue, feature, path in ((71, "OTHER-001", "elsewhere"), (99, "FACTORY-001", "elsewhere"), (99, "OTHER-001", "tools/factory/store.py"), (99, "OTHER-001", "tools")):
            data = snapshot()
            data["active_work"] = [{"repository": "example/game", "kind": "pr", "state": "open", "issue": issue, "feature_id": feature, "paths": [path]}]
            self.assertFalse(evaluate(data, 1000)["ready"])

    def test_path_prefix_and_other_repository_do_not_collide(self):
        data = snapshot()
        work = {"repository": "example/game", "kind": "pr", "state": "open", "issue": 99, "feature_id": "OTHER-001", "paths": ["tools/factory_extra"]}
        data["active_work"] = [work]
        self.assertTrue(evaluate(data, 1000)["ready"])
        work.update(repository="another/game", paths=["tools/factory"])
        self.assertTrue(evaluate(data, 1000)["ready"])

    def test_expired_external_claim_needs_reconciliation(self):
        data = snapshot()
        data["active_work"] = [{"repository": "example/game", "kind": "lease", "issue": 71, "feature_id": "FACTORY-001", "paths": ["tools/factory"], "expires_at": 999}]
        self.assertFalse(evaluate(data, 1000)["ready"])

    def test_unknown_or_missing_active_work_fails_closed(self):
        for record in (None, [{}], [{"kind": "magic"}]):
            data = snapshot()
            data["active_work"] = record
            self.assertFalse(evaluate(data, 1000)["ready"])

    def test_cli_bad_input_and_stale_snapshot_exit_nonzero(self):
        cli = Path(__file__).resolve().parents[1] / "cli.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            for content in ("{", json.dumps(snapshot())):
                path.write_text(content)
                result = subprocess.run([sys.executable, str(cli), "readiness", str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)


class Leases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jobs.sqlite"
        self.now = 1000
        self.store = JobStore(self.path, lambda: self.now)
        self.addCleanup(lambda: self.store.close())
        self.job = self.store.enqueue(snapshot())

    def receipt(self, ttl=10):
        return self.store.claim(self.job, "worker-a", ttl)

    def test_duplicate_delivery_and_changed_intake(self):
        self.assertEqual(self.job, self.store.enqueue(snapshot()))
        changed = snapshot()
        changed["task"]["revision"] = "c" * 64
        with self.assertRaisesRegex(ContractError, "changed task"):
            self.store.enqueue(changed)
        with self.assertRaises(ContractError):
            self.store.enqueue(snapshot(feature="FACTORY-002"))
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)

    def test_owned_refresh_is_rejected(self):
        self.receipt()
        with self.assertRaisesRegex(ContractError, "owned"):
            self.store.enqueue(snapshot())

    def test_only_one_real_process_claims_same_job(self):
        ctx = multiprocessing.get_context("spawn")
        start, output = ctx.Event(), ctx.Queue()
        workers = [ctx.Process(target=compete, args=(str(self.path), self.job, str(i), start, output)) for i in range(2)]
        for worker in workers:
            worker.start()
        start.set()
        answers = [output.get(timeout=15) for _ in workers]
        for worker in workers:
            worker.join(10)
            if worker.is_alive():
                worker.terminate()
                worker.join()
                self.fail("claim process hung")
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(sorted(answer[0] for answer in answers), ["lost", "won"])

    def test_scope_overlap_across_distinct_jobs(self):
        other = self.store.enqueue(snapshot(72, "FACTORY-002", "tools/factory/store.py"))
        self.receipt()
        with self.assertRaisesRegex(ContractError, "reserved"):
            self.store.claim(other, "worker-b")

    def test_independent_scope_can_be_claimed(self):
        other = self.store.enqueue(snapshot(27, "REF-001", "tools/saturn_lab"))
        self.receipt()
        self.assertEqual(self.store.claim(other, "worker-b")["owner"], "worker-b")

    def test_repository_case_cannot_bypass_reservation(self):
        data = snapshot(72, "FACTORY-002", "tools/factory/other.py")
        data["task"]["repository"] = "EXAMPLE/Game"
        other = self.store.enqueue(data)
        self.receipt()
        with self.assertRaisesRegex(ContractError, "reserved"):
            self.store.claim(other, "worker-b")

    def test_heartbeat_extends_current_lease(self):
        receipt = self.receipt()
        self.now = 1009
        self.store.heartbeat(receipt, 20)
        self.now = 1011
        with self.assertRaises(ContractError):
            self.store.claim(self.job, "worker-b")
        self.assertEqual(self.store.get(self.job)["expires"], 1029)

    def test_expiry_fences_old_worker_and_preserves_checkpoint_on_restart(self):
        old = self.receipt()
        checkpoint = {"base_sha": "a" * 40, "head_sha": "b" * 40, "next_step": "resume tests", "evidence_ref": "private:logs/1"}
        self.store.checkpoint(old, checkpoint)
        self.store.close()
        self.now = 1010
        self.store = JobStore(self.path, lambda: self.now)
        new = self.store.claim(self.job, "worker-b")
        self.assertGreater(new["epoch"], old["epoch"])
        self.assertEqual(new["checkpoint"], checkpoint)
        for operation in (lambda: self.store.heartbeat(old), lambda: self.store.checkpoint(old, checkpoint), lambda: self.store.release(old, "ready", "stale"), lambda: self.store.begin_publication(old, {"head_sha": "b" * 40, "base_sha": "a" * 40, "branch": "old"})):
            with self.assertRaises(ContractError):
                operation()

    def test_foreign_owner_or_token_cannot_mutate(self):
        receipt = self.receipt()
        for key, value in (("owner", "intruder"), ("token", "bad"), ("epoch", 999), ("task_digest", "bad")):
            foreign = {**receipt, key: value}
            with self.assertRaises(ContractError):
                self.store.heartbeat(foreign)

    def test_cancel_fences_worker_and_requires_reconciliation(self):
        receipt = self.receipt()
        self.store.cancel(self.job, "operator stop")
        with self.assertRaises(ContractError):
            self.store.heartbeat(receipt)
        with self.assertRaises(ContractError):
            self.store.claim(self.job, "worker-b")

    def test_crash_during_publication_blocks_duplicate_publication(self):
        receipt = self.receipt()
        intent = {"head_sha": "b" * 40, "base_sha": "a" * 40, "branch": "worker/change"}
        self.store.begin_publication(receipt, intent)
        self.store.begin_publication(receipt, intent)
        self.now = 1011
        self.store.recover()
        row = self.store.get(self.job)
        self.assertEqual(row["state"], "blocked")
        self.assertIn("unknown", row["reason"])
        with self.assertRaises(ContractError):
            self.store.claim(self.job, "replacement")
        other = self.store.enqueue(snapshot(72, "FACTORY-002", "tools/factory/other.py"))
        with self.assertRaises(ContractError):
            self.store.claim(other, "replacement")
        self.store.reconcile(self.job, row["epoch"], "clear", "checked:no old process, branch or PR")
        self.assertEqual(self.store.claim(self.job, "replacement")["owner"], "replacement")

    def test_cannot_requeue_or_change_publication_intent(self):
        receipt = self.receipt()
        intent = {"head_sha": "b" * 40, "base_sha": "a" * 40, "branch": "worker/change"}
        self.store.begin_publication(receipt, intent)
        with self.assertRaises(ContractError):
            self.store.release(receipt, "ready", "retry")
        with self.assertRaises(ContractError):
            self.store.begin_publication(receipt, {**intent, "head_sha": "c" * 40})

    def test_killed_process_rolls_back_partial_checkpoint(self):
        ctx = multiprocessing.get_context("spawn")
        ready = ctx.Event()
        worker = ctx.Process(target=interrupted_write, args=(str(self.path), self.job, ready))
        worker.start()
        try:
            self.assertTrue(ready.wait(10))
        finally:
            worker.terminate()
            worker.join(10)
        self.assertIsNone(self.store.get(self.job)["checkpoint"])
        self.assertEqual(self.receipt()["owner"], "worker-a")

    def test_stale_snapshot_requires_refresh_before_reclaim(self):
        self.receipt()
        self.now = 2000
        self.store.recover()
        with self.assertRaisesRegex(ContractError, "stale"):
            self.receipt()
        refreshed = snapshot()
        refreshed["captured_at"] = self.now
        self.store.enqueue(refreshed)
        self.receipt()

    def test_clock_rollback_fails_closed(self):
        receipt = self.receipt()
        self.now = 999
        with self.assertRaisesRegex(ContractError, "backwards"):
            self.store.heartbeat(receipt)

    def test_audit_survives_restart_and_submission_is_not_merge(self):
        receipt = self.receipt()
        self.store.begin_publication(receipt, {"head_sha": "b" * 40, "base_sha": "a" * 40, "branch": "worker/change"})
        self.store.release(receipt, "submitted", "PR created")
        self.store.close()
        self.store = JobStore(self.path, lambda: self.now)
        self.assertEqual(self.store.get(self.job)["state"], "submitted")
        self.assertEqual([row[0] for row in self.store.db.execute("SELECT event FROM events ORDER BY sequence")], ["enqueued", "claimed", "publication_started", "released"])
        with self.assertRaises(ContractError):
            self.store.reconcile(self.job, 0, "accepted", "stale reconciliation")


if __name__ == "__main__":
    unittest.main()
