#!/usr/bin/env python3
"""Always-present preparation gate: exact applicability and required child results."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("neptune_provision_checkout", ROOT / "tools/merge_gate/run.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
CHILDREN = ("xvfb", "ocr", "call-trace", "context-trace", "init-trace", "ghidra", "scsp-dsp")
EXACT = {"tools/godot/install.py", "tools/godot/toolchain.json", ".github/workflows/tool-provisioning.yml",
         "tools/saturn_lab/m68k_scsp_dsp.py", "tools/saturn_lab/m68k_scsp_state.py",
         "tools/saturn_lab/m68k_consumer_native.py", "tools/saturn_lab/tests/test_m68k_scsp_state.py", "tools/saturn_lab/scsp-dsp-source-lock.json",
         "tools/saturn_lab/tests/test_m68k_scsp_dsp.py", "tools/saturn_lab/m68k_scsp_fifo.py",
         "tools/saturn_lab/m68k_probe.py", "tools/saturn_lab/m68k_probe_backend.c",
         "tools/saturn_lab/m68k-probe-source-lock.json", "tools/saturn_lab/probe_kernel.py"}


def required(paths):
    if not isinstance(paths, list) or not paths:
        raise ValueError("Require a complete nonempty changed-path selection")
    for path in paths:
        if (not isinstance(path, str) or not path or "\\" in path or
                any(ord(c) < 32 for c in path) or PurePosixPath(path).is_absolute() or
                ".." in PurePosixPath(path).parts or PurePosixPath(path).as_posix() != path):
            raise ValueError("Invalid changed path")
    return any(path in EXACT or path.startswith("tools/factory/provision") or
               (path.startswith("tools/factory/tests/test_provision") and path.endswith(".py"))
               for path in paths)


def selection(event, kind, root=ROOT):
    if kind == "workflow_dispatch":
        identity = {"event": kind, "head": GATE.git("rev-parse", "HEAD", root=root)}
        paths = [".github/workflows/tool-provisioning.yml"]
    elif kind == "pull_request":
        identity, _ = GATE.checkout_identity(event, kind, root)
        # Include deletion/rename sources; a renamed installer must not disappear
        # from applicability merely because its new path is outside the prefix.
        raw = subprocess.check_output(["git", "diff", "--no-renames", "--name-only", "-z",
                                       identity["base"], identity["head"]], cwd=root)
        names = raw.decode("utf-8", errors="strict").split("\0")
        paths = sorted(set(name for name in names if name))
    else:
        raise ValueError("Preparation requires a real pull_request or explicit full manual run")
    return {"schema": "neptune.provision-applicability.v1", "identity": identity,
            "paths": paths, "required": required(paths)}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def assert_needs(needs, selected):
    if not isinstance(needs, dict) or set(needs) != {"applicability", *CHILDREN}:
        raise ValueError("Missing or unknown preparation dependencies")
    parent = needs["applicability"]
    outputs = {"required": str(selected["required"]).lower(), "selection_sha256": digest(selected)}
    if not isinstance(parent, dict) or parent.get("result") != "success" or parent.get("outputs") != outputs:
        raise ValueError("Applicability failed or differs from this exact checkout")
    expected = "success" if selected["required"] else "skipped"
    if any(not isinstance(needs[name], dict) or needs[name].get("result") != expected for name in CHILDREN):
        raise ValueError("Applicable preparation must succeed; only proven unrelated jobs may skip")
    return {"status": "success", "required": selected["required"], "selection_sha256": digest(selected),
            "child_results": {name: needs[name]["result"] for name in CHILDREN}}


def bounded_json(raw):
    if len(raw) > 1024**2:
        raise ValueError("Oversized gate metadata")
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate gate metadata key")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "assert-needs"))
    parser.add_argument("--event", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--kind", default=os.environ.get("GITHUB_EVENT_NAME"))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        if args.event is None:
            raise ValueError("Missing GitHub event identity")
        with args.event.open("rb") as source:
            event = bounded_json(source.read(1024**2 + 1))
        selected = selection(event, args.kind)
        result = selected if args.action == "plan" else assert_needs(
            bounded_json(os.environ.get("NEPTUNE_PROVISION_NEEDS", "")), selected)
        with args.report.open("x") as output:
            output.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        if args.github_output:
            if args.action != "plan":
                raise ValueError("Only the successful applicability job publishes outputs")
            with args.github_output.open("a") as output:
                output.write("required=" + str(selected["required"]).lower() + "\n")
                output.write("selection_sha256=" + digest(selected) + "\n")
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, "FAIL: " + str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
