"""Fixed supplied-artifact checks selected by existing trusted task fields.

No capture authenticity, production parity, arbitrary commands or new intake schema.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[2]
NAME = "behaviour-trace-exact-v1"
SELECTOR = "check:" + NAME
PREFIX = "trace-v1:"
FIELDS = {"contract", "reference-source", "candidate-source", "reference-file", "candidate-file"}
COMPARER = ROOT / "tools/saturn_lab/compare_trace.py"
spec = importlib.util.spec_from_file_location("neptune_feature_trace", COMPARER)
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def identity(value):
    return sha(trace.canonical(value).encode())


def requirements(task):
    selected = [value for value in task["acceptance"] if value.startswith("check:")]
    if any(value != SELECTOR for value in selected) or len(selected) > 1:
        raise ValueError("Unknown or duplicate named executable requirement")
    expected = {}
    for value in task["evidence"]:
        if not value.startswith(PREFIX):
            continue
        match = re.fullmatch(r"trace-v1:([a-z-]+):([0-9a-f]{64})", value)
        if not match or match[1] not in FIELDS or match[1] in expected:
            raise ValueError("Malformed, unknown or duplicate supplied-trace identity")
        expected[match[1]] = match[2]
    if bool(selected) != bool(expected) or (selected and set(expected) != FIELDS):
        raise ValueError("Named trace requirement needs all five independent artifact/contract/source identities")
    return {NAME: expected} if selected else {}


def safe(path):
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("Feature artifacts must not contain symlink components")
    return path


def read(path):
    path = safe(path)
    if not path.is_file():
        raise ValueError("Missing regular supplied trace: " + path.name)
    with path.open("rb") as source:
        raw = source.read(trace.MAX_BYTES + 1)
    if len(raw) > trace.MAX_BYTES:
        raise ValueError("Supplied trace exceeds its 16MiB bound")
    value = json.loads(raw, object_pairs_hook=trace.unique_object)
    trace.validate(value)
    return value, sha(raw)


def prepare(required, directory, *, root, evidence):
    if not required:
        if directory is not None:
            raise ValueError("Artifact directory supplied without a named task requirement")
        return None
    if directory is None:
        raise ValueError("Named task requirement needs --feature-artifacts")
    directory = safe(directory)
    if not directory.is_dir() or directory.is_relative_to(root) or directory.is_relative_to(evidence):
        raise ValueError("Supply a separate coordinator artifact mount outside candidate source and evidence")
    expected = required[NAME]
    observations, files = {}, {}
    for role, kind in (("reference", "reference"), ("candidate", "implementation")):
        path = directory / NAME / (role + ".json")
        value, raw_sha = read(path)
        if raw_sha != expected[role + "-file"]:
            raise ValueError("Supplied " + role + " artifact differs from accepted task identity")
        if value["source"]["kind"] != kind or identity(value["source"]) != expected[role + "-source"]:
            raise ValueError("Supplied " + role + " source differs from accepted task identity/role")
        if identity(value["contract"]) != expected["contract"]:
            raise ValueError("Supplied trace scenario/clock/input differs from accepted task contract")
        observations[role], files[role] = value, path
    return {"observations": observations, "files": files, "expected": expected}


def unchanged(prepared):
    for role, path in prepared["files"].items():
        _, raw_sha = read(path)
        if raw_sha != prepared["expected"][role + "-file"]:
            raise ValueError("Supplied artifacts changed during verification")


def execute(prepared):
    """Call the existing exact comparator, never consume a supplied success receipt."""
    unchanged(prepared)
    started = time.monotonic()
    result = trace.compare(prepared["observations"]["reference"], prepared["observations"]["candidate"])
    unchanged(prepared)
    return {"status": "success" if result["match"] is True else "failure",
            "operation": "tools/saturn_lab/compare_trace.py:compare",
            "comparer_sha256": sha(COMPARER.read_bytes()),
            "seconds": round(time.monotonic() - started, 6),
            "artifacts": dict(prepared["expected"]), "comparison": result,
            "scope": "Exact equality of supplied observations only; source authenticity, "
                     "production Godot execution and Saturn fidelity remain unverified."}
