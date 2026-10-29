"""Fail-closed intake contract for trusted coordinator snapshots, never issue prose."""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
import re


class ContractError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ContractError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value, label, allow_empty=False):
    require(isinstance(value, list) and (allow_empty or bool(value)), label + " must be a list")
    require(all(nonempty(x) for x in value), label + " contains empty/non-string values")
    require(len(set(value)) == len(value), label + " contains duplicates")
    return value


def sha(value, length=40):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def paths(value):
    for path in strings(value, "scope paths"):
        require(not any(c in path for c in "\\:*?[]\x00"), "scope paths must be literal relative files/directories")
        p = PurePosixPath(path)
        require(path not in {".", ""} and not p.is_absolute() and ".." not in p.parts
                and p.as_posix() == path, "invalid scope path")
    return value


def overlaps(left, right):
    return any(a == b or a.startswith(b + "/") or b.startswith(a + "/") for a in left for b in right)


def validate_task(task):
    require(isinstance(task, dict), "task must be an object")
    require(set(task) == {"repository", "issue", "feature_id", "revision", "kind", "state",
                          "acceptance", "evidence", "prerequisites", "capabilities", "scope"},
            "task fields are missing or unknown")
    require(isinstance(task["repository"], str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", task["repository"]), "invalid repository")
    require(type(task["issue"]) is int and task["issue"] > 0, "invalid issue")
    require(isinstance(task["feature_id"], str) and re.fullmatch(r"[A-Z]+-\d{3}", task["feature_id"]), "invalid feature ID")
    require(sha(task["revision"], 64), "issue revision must be a SHA-256 of trusted intake source")
    require(task["kind"] in {"implementation", "research", "verification", "operations"}, "an epic/roadmap is not an executable task")
    require(task["state"] == "open", "task issue is not open")
    strings(task["acceptance"], "acceptance")
    strings(task["evidence"], "evidence expectations")
    strings(task["prerequisites"], "prerequisites", True)
    require(all(re.fullmatch(r"[A-Z]+-\d{3}", x) and x != task["feature_id"] for x in task["prerequisites"]), "invalid/self prerequisite")
    strings(task["capabilities"], "capabilities", True)
    scope = task["scope"]
    require(isinstance(scope, dict) and set(scope) == {"goal", "paths", "max_files"}, "invalid bounded scope")
    require(nonempty(scope["goal"]), "scope needs one observable goal")
    paths(scope["paths"])
    require(type(scope["max_files"]) is int and 1 <= scope["max_files"] <= 20, "split tasks exceeding the 20-file intake limit")
    return task


def evaluate(snapshot, now, max_age=900):
    """Returns reasons; malformed/stale/unknown data never means ready.

    Evidence is attested by the trusted coordinator, not authenticated here.
    The future GitHub adapter must verify remote identities/checks before intake.
    """
    reasons = []
    try:
        require(isinstance(snapshot, dict) and set(snapshot) == {"schema", "captured_at", "base_sha", "task", "available_capabilities", "prerequisite_evidence", "active_work"}, "invalid snapshot fields")
        require(snapshot["schema"] == "neptune.factory-intake.v1", "unsupported intake schema")
        require(type(now) in (int, float) and type(snapshot["captured_at"]) in (int, float), "invalid clock")
        require(0 <= now - snapshot["captured_at"] <= max_age, "snapshot stale or from the future")
        require(sha(snapshot["base_sha"]), "missing exact base SHA")
        task = validate_task(snapshot["task"])
        available = strings(snapshot["available_capabilities"], "available capabilities", True)
        missing = sorted(set(task["capabilities"]) - set(available))
        if missing:
            reasons.append("missing capabilities: " + ", ".join(missing))
        evidence = snapshot["prerequisite_evidence"]
        require(isinstance(evidence, dict), "invalid prerequisite evidence")
        for dependency in task["prerequisites"]:
            proof = evidence.get(dependency)
            if not (isinstance(proof, dict) and proof.get("status") == "verified"
                    and sha(proof.get("head_sha")) and sha(proof.get("base_sha"))
                    and sha(proof.get("report_sha256"), 64) and nonempty(proof.get("evidence_ref"))):
                reasons.append("unverified prerequisite: " + dependency)
        require(isinstance(snapshot["active_work"], list), "active work must be an explicit list")
        for work in snapshot["active_work"]:
            require(isinstance(work, dict) and work.get("kind") in {"pr", "lease"}, "unknown active-work record")
            require(nonempty(work.get("repository")), "active work lacks repository")
            require(type(work.get("issue")) is int and work["issue"] > 0 and nonempty(work.get("feature_id")), "active work lacks identity")
            work_paths = paths(work.get("paths"))
            if work["kind"] == "pr":
                require(work.get("state") == "open", "active PR state must be open")
            else:
                require(type(work.get("expires_at")) in (int, float) and work["expires_at"] > 0, "invalid lease expiry")
                # An expired heartbeat is not proof a worker stopped publishing.
            if work["repository"].casefold() == task["repository"].casefold() and (work["issue"] == task["issue"] or work["feature_id"] == task["feature_id"] or overlaps(work_paths, task["scope"]["paths"])):
                reasons.append("overlapping " + work["kind"] + ": " + str(work["issue"]))
        return {"ready": not reasons, "reasons": reasons, "task_digest": digest(task), "base_sha": snapshot["base_sha"]}
    except (ContractError, TypeError, ValueError, KeyError) as error:
        return {"ready": False, "reasons": [str(error)]}
