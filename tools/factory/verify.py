#!/usr/bin/env python3
"""Local offline factory preflight using Neptune's required-CI test plan.

This does not publish a GitHub check, approve a review, merge or run a scheduler.
The factory must invoke it inside its credential-free verification sandbox.
--plan only prints what the selected checks require: it runs, installs, downloads
and inspects nothing, and its result is not a verification or readiness receipt.
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

from readiness import digest as task_digest, evaluate as evaluate_intake
import feature_contracts

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("neptune_ci_plan", ROOT / "tools/merge_gate/run.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
SCHEMA = "neptune.factory-verification.v1"
REQUIREMENTS_SCHEMA = "neptune.factory-requirements.v1"
TOOLCHAIN_LOCK = "tools/godot/toolchain.json"
# Declared, never probed from the host: the core checks run under the invoking
# Python (3.11 for hashlib.file_digest) and invoke git and a C compiler. Only the
# graphical native-runtime check needs a virtual display.
BASELINE_PYTHON = ">=3.11"
BASELINE_EXECUTABLES = ("cc", "git")
DISPLAY_EXECUTABLES = ("Xvfb",)
REPOSITORY = "elgansayer/Neptune-Bomberman"
MAX_INTAKE_BYTES = 256 * 1024


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


def read_intake(path):
    """Read a bounded coordinator-supplied snapshot; hashes do not authenticate it."""
    path = Path(path).absolute()
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents) or not path.is_file():
        raise ValueError("Intake must be a regular file without symlink components")
    with path.open("rb") as stream:
        raw = stream.read(MAX_INTAKE_BYTES + 1)
    if len(raw) > MAX_INTAKE_BYTES:
        raise ValueError("Intake snapshot exceeds its 256 KiB bound")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate intake JSON key: " + key)
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique), hashlib.sha256(raw).hexdigest()


def task_binding(intake_path, paths, root, now=time.time):
    """Bind existing intake to the actual clean candidate, never issue commands."""
    selectors = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                 "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE")
    if any(os.environ.get(name) for name in selectors):
        raise ValueError("Intake verification rejects Git repository/index override variables")
    snapshot, intake_sha256 = read_intake(intake_path)
    evaluated = evaluate_intake(snapshot, now())
    if not evaluated["ready"]:
        raise ValueError("Intake is not ready: " + "; ".join(evaluated["reasons"]))
    task = snapshot["task"]
    if task["repository"].casefold() != REPOSITORY.casefold():
        raise ValueError("Intake repository does not match Neptune")
    head = gate.git("rev-parse", "HEAD", root=root)
    base = snapshot["base_sha"]
    gate.git("merge-base", "--is-ancestor", base, head, root=root)
    tracked = subprocess.check_output(["git", "ls-files", "-v", "-z"], cwd=root, text=True).split("\0")
    if any(entry and (entry[0] == "S" or entry[0].islower()) for entry in tracked):
        raise ValueError("Candidate index contains assume-unchanged or skip-worktree source")
    if gate.git("status", "--porcelain=v1", "--untracked-files=all", root=root):
        raise ValueError("Intake verification requires clean tracked and untracked candidate source")
    # gate.git strips whitespace for scalar results; NUL-delimited filenames
    # must retain leading spaces so an actual changed file cannot disappear.
    actual = subprocess.check_output(["git", "diff", "--no-renames", "--name-only", "-z", base, head],
                                     cwd=root, text=True).split("\0")
    actual = sorted(path for path in actual if path)
    # Reuse path validation/classification even for deletions and rename sources.
    selection(actual)
    if selection(paths)["paths"] != actual:
        raise ValueError("Selected paths differ from the complete intake base/head diff")
    if len(actual) > task["scope"]["max_files"]:
        raise ValueError("Candidate exceeds the accepted scope max_files")
    for path in actual:
        if not any(path == allowed or path.startswith(allowed + "/") for allowed in task["scope"]["paths"]):
            raise ValueError("Candidate changed a path outside accepted scope: " + path)
    return {"repository": task["repository"], "issue": task["issue"], "feature_id": task["feature_id"],
            "revision": task["revision"], "task_sha256": task_digest(task), "intake_sha256": intake_sha256,
            "base": base, "head": head, "changed_paths": actual}


def offline_toolchain(root, directory):
    lock_path = root / TOOLCHAIN_LOCK
    lock = json.loads(lock_path.read_text())
    binary = directory / gate.godot_binary_name(lock)
    if not binary.is_file() or not os.access(binary, os.X_OK) or sha(binary) != lock["binary_sha256"]:
        raise ValueError("Missing/mismatched offline Godot cache; provision it before verification")
    if not isinstance(lock.get("addons"), dict) or not lock["addons"]:
        raise ValueError("Missing native addon identities")
    for relative, expected in lock["addons"].items():
        selection([relative])
        if sha(root / relative) != expected:
            raise ValueError("Native addon identity mismatch: " + relative)
    return {"binary_sha256": sha(binary), "lock_sha256": sha(lock_path), "addon_count": len(lock["addons"])}


def is_sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def pinned_toolchain(root):
    """Engine identity pinned by the lock; no cache, engine or addon file is inspected."""
    raw = (root / TOOLCHAIN_LOCK).read_bytes()
    lock = json.loads(raw)
    if not isinstance(lock, dict):
        raise ValueError("Pinned Godot toolchain lock must be a JSON object")
    binary_name = gate.godot_binary_name(lock)
    version, binary_sha256, addons = lock.get("godot_version"), lock.get("binary_sha256"), lock.get("addons")
    if not isinstance(version, str) or not version or not is_sha256(binary_sha256):
        raise ValueError("Missing pinned Godot version/binary identity")
    if not isinstance(addons, dict) or not addons:
        raise ValueError("Missing native addon identities")
    for relative, expected in addons.items():
        selection([relative])
        if not is_sha256(expected):
            raise ValueError("Invalid native addon identity: " + relative)
    # Identities only: the lock's download location is deliberately not forwarded.
    return {"tool": "godot", "lock": TOOLCHAIN_LOCK, "lock_sha256": hashlib.sha256(raw).hexdigest(),
            "godot_version": version, "binary_name": binary_name, "binary_sha256": binary_sha256,
            "addons": dict(sorted(addons.items()))}


def requirements(paths, *, root=ROOT):
    """What the shared CI plan needs for a selection. A plan, never a receipt: nothing runs."""
    plan = selection(paths)
    engine_checks = gate.NATIVE + gate.RUNTIME
    baseline = [name for name in plan["required"] if name in gate.CORE]
    native = [name for name in plan["required"] if name in engine_checks]
    needed = plan["mode"] != "metadata"  # The test verify() applies before demanding the offline cache.
    if len(baseline) + len(native) != len(plan["required"]) or needed != bool(native):
        raise ValueError("Shared plan has an unclassified or inconsistent native requirement")
    return {"schema": REQUIREMENTS_SCHEMA,
            "scope": "requirements only; no check was run and no host, tool cache or engine was inspected; "
                     "not a verification or readiness receipt",
            "plan": plan,
            "baseline": {"checks": baseline, "python": BASELINE_PYTHON, "executables": list(BASELINE_EXECUTABLES)},
            "native": {"required": needed, "checks": native,
                       "executables": list(DISPLAY_EXECUTABLES) if "native-runtime" in native else [],
                       "toolchain": pinned_toolchain(root) if needed else None}}


def verify(paths, evidence, toolchain, *, root=ROOT, runner=subprocess.run, intake=None, now=time.time,
           feature_artifacts=None):
    if evidence.exists():
        raise ValueError("Use a fresh verification evidence directory")
    evidence.mkdir(parents=True, mode=0o700)
    report = {"schema": SCHEMA, "scope": "local preflight only; required GitHub CI remains authoritative", "checks": {}}
    report_path = evidence / "report.json"
    try:
        plan = selection(paths)
        identity = {"head": gate.git("rev-parse", "HEAD", root=root),
                    "selected_contents_sha256": selected_contents(root, paths)}
        if intake is not None:
            binding = task_binding(intake, paths, root, now)
            if binding["head"] != identity["head"]:
                raise ValueError("Candidate head changed during intake binding")
            identity["base"] = binding["base"]
            report["task_binding"] = binding
            snapshot, raw_sha = read_intake(intake)
            if raw_sha != binding["intake_sha256"]:
                raise ValueError("Accepted intake changed before feature selection")
            required_features = feature_contracts.requirements(snapshot["task"])
        else:
            if feature_artifacts is not None:
                raise ValueError("Feature artifacts require a trusted --intake")
            required_features = {}
        if required_features:
            report.update(feature_requirements=required_features, feature_checks={})
        prepared_feature = feature_contracts.prepare(required_features, feature_artifacts,
                                                      root=root, evidence=evidence)
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
        if prepared_feature is not None:
            result = feature_contracts.execute(prepared_feature)
            report["feature_checks"][feature_contracts.NAME] = result
            if result["status"] != "success":
                raise ValueError("Required named feature comparison diverged")
        if selected_contents(root, paths) != identity["selected_contents_sha256"]:
            raise ValueError("Selected source changed during verification")
        if intake is not None and task_binding(intake, paths, root, now) != binding:
            raise ValueError("Accepted intake or candidate changed during verification")
        if prepared_feature is not None:
            feature_contracts.unchanged(prepared_feature)
        gate.assert_pass(report, identity)
        report["conclusion"] = "success"
        return report
    except (ValueError, KeyError, TypeError, OSError, RecursionError, subprocess.SubprocessError) as error:
        report.update(conclusion="failure", error=str(error))
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true",
                        help="print the requirements of the selection only; run, install and inspect nothing")
    parser.add_argument("--changed-path", action="append", required=True)
    parser.add_argument("--toolchain", type=Path, help="offline Godot cache directory (required unless --plan)")
    parser.add_argument("--evidence", type=Path, help="fresh evidence directory (required unless --plan)")
    parser.add_argument("--intake", type=Path,
                        help="fresh trusted coordinator snapshot; bind actual committed scope and task identity")
    parser.add_argument("--feature-artifacts", type=Path,
                        help="separate trusted read-only supplied artifacts selected by accepted task requirements")
    args = parser.parse_args(argv)
    given = {"--toolchain": args.toolchain, "--evidence": args.evidence}
    if args.plan:
        plan_forbidden = {**given, "--intake": args.intake, "--feature-artifacts": args.feature_artifacts}
        if any(value is not None for value in plan_forbidden.values()):
            parser.error("--plan accepts only --changed-path (remove " +
                         ", ".join(flag for flag, value in plan_forbidden.items() if value is not None) + ")")
    elif missing := [flag for flag, value in given.items() if value is None]:
        parser.error("the following arguments are required: " + ", ".join(missing))
    try:
        if args.plan:
            print("NEPTUNE_FACTORY_REQUIREMENTS=" + json.dumps(requirements(args.changed_path), sort_keys=True))
            return 0
        report = verify(args.changed_path, args.evidence, args.toolchain, intake=args.intake,
                        feature_artifacts=args.feature_artifacts)
    except (ValueError, KeyError, TypeError, OSError, RecursionError, subprocess.SubprocessError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1
    receipt = {key: report[key] for key in ("schema", "identity", "plan", "checks", "conclusion")}
    if "task_binding" in report:
        receipt["task_binding"] = report["task_binding"]
    if "feature_requirements" in report:
        receipt["feature_requirements"] = report["feature_requirements"]
        receipt["feature_checks"] = report["feature_checks"]
    print("NEPTUNE_FACTORY_VERIFICATION=" + json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
