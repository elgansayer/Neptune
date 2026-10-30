#!/usr/bin/env python3
"""Local offline factory preflight using Neptune's required-CI test plan.

This does not publish a GitHub check, approve a review, merge or run a scheduler.
The factory must invoke it inside its credential-free verification sandbox.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("neptune_ci_plan", ROOT / "tools/merge_gate/run.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
SCHEMA = "neptune.factory-verification.v1"


def selection(paths):
    if not paths or len(paths) > 1000:
        raise ValueError("A bounded non-empty changed-file selection is required")
    for path in paths:
        if not isinstance(path, str) or not path or "\\" in path or ":" in path or any(ord(c) < 32 for c in path):
            raise ValueError("Changed paths must be portable relative files")
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or ".." in parsed.parts or parsed.as_posix() != path or path == ".":
            raise ValueError("Changed paths must be normalised relative files")
    return gate.plan(paths)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def selected_contents(root, paths):
    records = []
    for relative in sorted(set(paths)):
        path = root / relative
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            raise ValueError("Selected source contains a symlink: " + relative)
        if not path.exists():
            records.append([relative, "deleted"])
        elif path.is_file():
            records.append([relative, sha(path)])
        else:
            raise ValueError("Selected source is not a regular file: " + relative)
    return hashlib.sha256(json.dumps(records, separators=(",", ":")).encode()).hexdigest()


def offline_toolchain(root, directory):
    lock_path = root / "tools/godot/toolchain.json"
    lock = json.loads(lock_path.read_text())
    if lock.get("binary_name") != "Godot_v4.5-stable_linux.x86_64":
        raise ValueError("Unsupported pinned Godot binary name")
    binary = directory / lock["binary_name"]
    if not binary.is_file() or not os.access(binary, os.X_OK) or sha(binary) != lock["binary_sha256"]:
        raise ValueError("Missing/mismatched offline Godot cache; provision it before verification")
    if not isinstance(lock.get("addons"), dict) or not lock["addons"]:
        raise ValueError("Missing native addon identities")
    for relative, expected in lock["addons"].items():
        selection([relative])
        if sha(root / relative) != expected:
            raise ValueError("Native addon identity mismatch: " + relative)
    return {"binary_sha256": sha(binary), "lock_sha256": sha(lock_path), "addon_count": len(lock["addons"])}


def verify(paths, evidence, toolchain, *, root=ROOT, runner=subprocess.run):
    if evidence.exists():
        raise ValueError("Use a fresh verification evidence directory")
    evidence.mkdir(parents=True, mode=0o700)
    report = {"schema": SCHEMA, "scope": "local preflight only; required GitHub CI remains authoritative", "checks": {}}
    report_path = evidence / "report.json"
    try:
        plan = selection(paths)
        identity = {"head": gate.git("rev-parse", "HEAD", root=root),
                    "selected_contents_sha256": selected_contents(root, paths)}
        report.update(identity=identity, plan=plan)
        if plan["mode"] != "metadata":
            report["offline_toolchain"] = offline_toolchain(root, toolchain)
        for name, command, timeout in gate.commands(plan["mode"], evidence, toolchain):
            record = {"command": command, "status": "running"}
            report["checks"][name] = record
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            started = time.monotonic()
            with (evidence / (name + ".log")).open("w") as output:
                try:
                    process = runner(command, cwd=root, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
                    code = process.returncode
                    record.update(exit=code, status="success" if type(code) is int and code == 0 else "failure")
                except subprocess.TimeoutExpired:
                    record.update(exit=None, status="timed_out")
            record["seconds"] = round(time.monotonic() - started, 3)
            print(name + ": " + record["status"], flush=True)
            if record["status"] != "success":
                raise ValueError("Required check failed: " + name)
        if selected_contents(root, paths) != identity["selected_contents_sha256"]:
            raise ValueError("Selected source changed during verification")
        gate.assert_pass(report, identity)
        report["conclusion"] = "success"
        return report
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        report.update(conclusion="failure", error=str(error))
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-path", action="append", required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = verify(args.changed_path, args.evidence, args.toolchain)
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1
    print("NEPTUNE_FACTORY_VERIFICATION=" + json.dumps({key: report[key] for key in ("schema", "identity", "plan", "checks", "conclusion")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
