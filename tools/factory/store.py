"""Single-host coordinator-owned SQLite leases with fencing and publication holds.

Workers receive lease receipts; they must not have database or merge credentials.
This module launches no provider, shell command, GitHub operation or host service.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid

from readiness import ContractError, canonical, digest, evaluate, nonempty, overlaps, require, sha, validate_task


class JobStore:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        self.db = sqlite3.connect(Path(path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value REAL NOT NULL);
          INSERT OR IGNORE INTO meta VALUES ('version', 1);
          INSERT OR IGNORE INTO meta VALUES ('last_time', 0);
          CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, repository TEXT NOT NULL, issue INTEGER NOT NULL,
            feature TEXT NOT NULL, task_digest TEXT NOT NULL, snapshot TEXT NOT NULL,
            state TEXT NOT NULL, owner TEXT, token TEXT, epoch INTEGER NOT NULL DEFAULT 0,
            expires REAL, checkpoint TEXT, publication TEXT, reason TEXT,
            UNIQUE(repository, issue), UNIQUE(repository, feature));
          CREATE TABLE IF NOT EXISTS events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT NOT NULL,
            at REAL NOT NULL, event TEXT NOT NULL, epoch INTEGER NOT NULL, detail TEXT NOT NULL);
        """)
        require(self.db.execute("SELECT value FROM meta WHERE key='version'").fetchone()[0] == 1, "unsupported store version")

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            now = self.clock()
            last = self.db.execute("SELECT value FROM meta WHERE key='last_time'").fetchone()[0]
            require(type(now) in (int, float) and now >= last and now < float("inf"), "clock moved backwards or is invalid")
            self.db.execute("UPDATE meta SET value=? WHERE key='last_time'", (now,))
            yield now
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def record(self, job, now, event, epoch, detail=None):
        self.db.execute("INSERT INTO events(job,at,event,epoch,detail) VALUES (?,?,?,?,?)", (job, now, event, epoch, canonical(detail or {})))

    def get(self, job):
        row = self.db.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
        require(row is not None, "unknown job")
        return dict(row)

    def enqueue(self, snapshot):
        task = validate_task(snapshot.get("task"))
        repository = task["repository"].casefold()
        key = repository + ":" + task["feature_id"]
        with self.transaction() as now:
            result = evaluate(snapshot, now)
            require(result["ready"], "; ".join(result["reasons"]))
            existing = self.db.execute("SELECT * FROM jobs WHERE id=? OR (repository=? AND issue=?)", (key, repository, task["issue"])).fetchone()
            if existing:
                require(existing["id"] == key and existing["task_digest"] == digest(task), "duplicate issue or changed task needs explicit reconciliation")
                require(existing["state"] not in {"running", "publishing"}, "cannot refresh an owned job")
                self.db.execute("UPDATE jobs SET snapshot=? WHERE id=?", (canonical(snapshot), key))
                self.record(key, now, "refreshed", existing["epoch"])
            else:
                self.db.execute("INSERT INTO jobs(id,repository,issue,feature,task_digest,snapshot,state) VALUES (?,?,?,?,?,?,'ready')", (key, repository, task["issue"], task["feature_id"], digest(task), canonical(snapshot)))
                self.record(key, now, "enqueued", 0)
        return key

    def _recover(self, now):
        for row in self.db.execute("SELECT * FROM jobs WHERE state IN ('running','publishing') AND expires<=?", (now,)).fetchall():
            publishing = row["state"] == "publishing"
            state = "blocked" if publishing else "ready"
            reason = "publication outcome unknown; reconcile remote state" if publishing else "lease expired"
            self.db.execute("UPDATE jobs SET state=?,owner=NULL,token=NULL,expires=NULL,epoch=epoch+1,reason=? WHERE id=?", (state, reason, row["id"]))
            self.record(row["id"], now, "expired", row["epoch"] + 1, {"state": state, "reason": reason})

    def recover(self):
        with self.transaction() as now:
            self._recover(now)

    def claim(self, job, owner, ttl=300):
        require(nonempty(owner), "owner required")
        require(type(ttl) is int and 1 <= ttl <= 3600, "lease TTL must be 1..3600 seconds")
        with self.transaction() as now:
            self._recover(now)
            row = self.get(job)
            require(row["state"] == "ready", "job is not ready")
            snapshot = json.loads(row["snapshot"])
            result = evaluate(snapshot, now)
            require(result["ready"], "; ".join(result["reasons"]))
            for other in self.db.execute("SELECT * FROM jobs WHERE repository=? AND id!=?", (row["repository"], job)):
                # Unknown publication outcomes remain reserved even after expiry/cancellation.
                if other["state"] in {"running", "publishing", "submitted"} or other["publication"]:
                    if overlaps(snapshot["task"]["scope"]["paths"], json.loads(other["snapshot"])["task"]["scope"]["paths"]):
                        raise ContractError("scope already reserved by " + other["id"])
            token, epoch = uuid.uuid4().hex, row["epoch"] + 1
            self.db.execute("UPDATE jobs SET state='running',owner=?,token=?,epoch=?,expires=?,reason=NULL WHERE id=?", (owner, token, epoch, now + ttl, job))
            self.record(job, now, "claimed", epoch, {"owner": owner})
            return {"job": job, "owner": owner, "token": token, "epoch": epoch, "expires": now + ttl, "task_digest": row["task_digest"], "base_sha": snapshot["base_sha"], "checkpoint": json.loads(row["checkpoint"]) if row["checkpoint"] else None}

    def _owned(self, receipt, now):
        row = self.get(receipt["job"])
        require(row["state"] in {"running", "publishing"} and row["expires"] > now, "lease inactive or expired")
        require(all(row[key] == receipt.get(key) for key in ("owner", "token", "epoch", "task_digest")), "stale or foreign lease receipt")
        return row

    def heartbeat(self, receipt, ttl=300):
        require(type(ttl) is int and 1 <= ttl <= 3600, "invalid TTL")
        with self.transaction() as now:
            self._owned(receipt, now)
            self.db.execute("UPDATE jobs SET expires=? WHERE id=?", (now + ttl, receipt["job"]))
            self.record(receipt["job"], now, "heartbeat", receipt["epoch"])

    def checkpoint(self, receipt, checkpoint):
        require(isinstance(checkpoint, dict) and sha(checkpoint.get("base_sha")) and sha(checkpoint.get("head_sha")) and nonempty(checkpoint.get("next_step")), "checkpoint requires exact base/head and next step")
        require(len(canonical(checkpoint).encode()) <= 65536, "checkpoint exceeds 64KiB; store logs separately")
        with self.transaction() as now:
            self._owned(receipt, now)
            self.db.execute("UPDATE jobs SET checkpoint=? WHERE id=?", (canonical(checkpoint), receipt["job"]))
            self.record(receipt["job"], now, "checkpoint", receipt["epoch"], {"digest": digest(checkpoint)})

    def begin_publication(self, receipt, intent):
        require(isinstance(intent, dict) and set(intent) == {"head_sha", "base_sha", "branch"} and sha(intent["head_sha"]) and sha(intent["base_sha"]) and nonempty(intent["branch"]), "invalid publication intent")
        with self.transaction() as now:
            row = self._owned(receipt, now)
            if row["publication"]:
                require(json.loads(row["publication"]) == intent, "publication intent is immutable")
                return
            self.db.execute("UPDATE jobs SET state='publishing',publication=? WHERE id=?", (canonical(intent), receipt["job"]))
            self.record(receipt["job"], now, "publication_started", receipt["epoch"], intent)

    def release(self, receipt, state, reason):
        require(state in {"ready", "blocked", "submitted"} and nonempty(reason), "invalid release")
        with self.transaction() as now:
            row = self._owned(receipt, now)
            require(not row["publication"] or state in {"blocked", "submitted"}, "publication must be reconciled before requeue")
            require(state != "submitted" or row["publication"], "submission requires publication intent")
            self.db.execute("UPDATE jobs SET state=?,owner=NULL,token=NULL,expires=NULL,epoch=epoch+1,reason=? WHERE id=?", (state, reason, receipt["job"]))
            self.record(receipt["job"], now, "released", receipt["epoch"] + 1, {"state": state, "reason": reason})

    def cancel(self, job, reason):
        require(nonempty(reason), "cancellation reason required")
        with self.transaction() as now:
            row = self.get(job)
            self.db.execute("UPDATE jobs SET state='cancelled',owner=NULL,token=NULL,expires=NULL,epoch=epoch+1,reason=? WHERE id=?", (reason, job))
            self.record(job, now, "cancelled", row["epoch"] + 1, {"reason": reason})

    def reconcile(self, job, expected_epoch, outcome, evidence_ref):
        """Trusted coordinator only, after checking remote processes/branches/PRs.

        'clear' permits retry only when no old publisher or active PR remains.
        'accepted' records completion only after independent exact-head merge checks.
        This local store cannot authenticate those external assertions.
        """
        require(outcome in {"clear", "accepted"} and nonempty(evidence_ref), "reconciliation evidence required")
        with self.transaction() as now:
            row = self.get(job)
            require(row["epoch"] == expected_epoch and row["state"] in {"blocked", "submitted", "cancelled"}, "reconciliation state changed")
            require(outcome != "accepted" or row["publication"], "cannot accept without a publication")
            state = "ready" if outcome == "clear" else "accepted"
            self.db.execute("UPDATE jobs SET state=?,publication=NULL,epoch=epoch+1,reason=? WHERE id=?", (state, evidence_ref, job))
            self.record(job, now, "reconciled", row["epoch"] + 1, {"outcome": outcome, "evidence_ref": evidence_ref})
