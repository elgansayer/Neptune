#!/usr/bin/env python3
"""Fail-closed, read-only CI aggregate; never merges or reads provider credentials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CORE = ("input-tooling", "film-contracts", "catalogue-tests", "catalogue-validation", "factory-contracts", "gate-contracts")
NATIVE = ("native-install", "native-runner", "native-project")
RUNTIME = ("native-runtime", "native-bots")
# An allowlist: new/unrecognised paths require the full native gameplay gate.
METADATA = ("docs/", "tools/saturn_lab/", "tools/research_catalog/", "tools/merge_gate/", "tools/factory/")
METADATA_FILES = {"AGENTS.md", "LICENSE", "NOTICE", ".gitignore",
                  ".github/workflows/neptune-merge-gate.yml", ".github/workflows/saturn-lab.yml"}
RUNNER_FILES = {"run_bot_tests.sh", "tests/bot_test_runner.gd", "tests/bot_test_runner.tscn",
                "tests/bot_test_suite.gd", ".github/workflows/godot-runner.yml",
                "tools/godot/README.md", "tools/godot/check_runner.py",
                "tools/godot/check_project_contracts.py", "tools/godot/install.py",
                "tools/godot/run_bot_tests.py", "tools/godot/toolchain.json"}


def git(*args: str, root: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def godot_binary_name(lock: dict) -> str:
    name = lock.get("binary_name")
    if not isinstance(name, str) or not re.fullmatch(r"Godot_v[0-9]+\.[0-9]+(?:\.[0-9]+)?-stable_linux\.x86_64", name):
        raise ValueError("Unsupported pinned Godot binary name")
    return name


def plan(paths: list[str]) -> dict:
    if not paths or any(not path or path.startswith("/") or ".." in path.split("/") for path in paths):
        raise ValueError("Changed-file selection must be non-empty and relative")
    mode = "metadata"
    for path in paths:
        if path in METADATA_FILES or path.startswith(METADATA) or ("/" not in path and path.endswith(".md")):
            continue
        if path in RUNNER_FILES:
            if mode == "metadata":
                mode = "runner"
        else:
            mode = "gameplay"
    required = list(CORE)
    if mode != "metadata":
        required.extend(NATIVE)
    if mode == "gameplay":
        required.extend(RUNTIME)
    return {"mode": mode, "paths": sorted(set(paths)), "required": required}


def checkout_identity(event: dict, kind: str, root: Path = ROOT) -> tuple[dict, list[str]]:
    sha = git("rev-parse", "HEAD", root=root)
    if kind == "pull_request":
        pr = event["pull_request"]
        base, head = pr["base"]["sha"], pr["head"]["sha"]
        if not all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) for value in (base, head)):
            raise ValueError("Missing/invalid exact base or head")
        if git("rev-parse", "HEAD^1", root=root) != base or git("rev-parse", "HEAD^2", root=root) != head:
            raise ValueError("Stale/different merge checkout: parents must match event base/head")
        if subprocess.run(["git", "merge-base", "--is-ancestor", base, head], cwd=root).returncode:
            raise ValueError("Head is behind current base; update it before testing/merging")
        names = git("diff", "--name-only", "-z", base, head, root=root).split("\0")
        identity = {"event": kind, "base": base, "head": head, "merge": sha, "pr": event["number"]}
    elif kind == "push":
        base, head = event["before"], event["after"]
        if head != sha:
            raise ValueError("Push checkout differs from event head")
        names = (git("ls-files", "-z", root=root) if base == "0" * 40
                 else git("diff", "--name-only", "-z", base, head, root=root)).split("\0")
        identity = {"event": kind, "base": base, "head": head, "merge": sha}
    else:
        raise ValueError("Gate requires a real pull_request or push event")
    return identity, [name for name in names if name]


def assert_pass(report: dict, expected: dict) -> None:
    if report.get("identity") != expected or not expected:
        raise ValueError("Report head/base identity differs")
    selection = plan(report["plan"]["paths"])
    if report["plan"] != selection:
        raise ValueError("Changed-file plan differs")
    checks = report["checks"]
    if set(checks) != set(selection["required"]) or not checks:
        raise ValueError("Missing/extra/empty required checks")
    for name, check in checks.items():
        if check.get("status") != "success" or check.get("exit") != 0 or not check.get("command"):
            raise ValueError("Required check did not succeed: " + name)


def commands(mode: str, evidence: Path, toolchain: Path) -> list[tuple[str, list[str], int]]:
    python = sys.executable
    checks = [
        ("input-tooling", [python, "tools/saturn_lab/check.py"], 60),
        ("film-contracts", [python, "tools/saturn_film/check.py"], 60),
        ("catalogue-tests", [python, "tools/research_catalog/check.py"], 60),
        ("catalogue-validation", [python, "tools/research_catalog/cli.py", "validate"], 30),
        ("factory-contracts", [python, "tools/factory/check.py"], 60),
        ("gate-contracts", [python, "tools/merge_gate/check.py"], 60),
    ]
    if mode == "metadata":
        return checks
    lock = json.loads((ROOT / "tools/godot/toolchain.json").read_text())
    binary = str(toolchain / godot_binary_name(lock))
    checks.extend([
        ("native-install", [python, "tools/godot/install.py", "--directory", str(toolchain)], 180),
        ("native-runner", [python, "tools/godot/check_runner.py", "--godot", binary], 120),
        ("native-project", [python, "tools/godot/check_project_contracts.py", "--godot", binary,
                            "--evidence", str(evidence / "native-project")], 180),
    ])
    if mode == "gameplay":
        checks.extend([
            ("native-runtime", [python, "tools/godot/check_runtime.py", "--godot", binary,
                                "--graphical", "--evidence", str(evidence / "native-runtime")], 180),
            ("native-bots", [python, "tools/godot/run_bot_tests.py", "--godot", binary,
                             "--timeout", "300", "--max-log-mib", "16",
                             "--log", str(evidence / "native-bots-engine.log")], 330),
        ])
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--kind", default=os.environ.get("GITHUB_EVENT_NAME"))
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    report: dict = {"checks": {}}
    report_path = args.evidence / "report.json"
    try:
        identity, paths = checkout_identity(json.loads(args.event.read_text()), args.kind)
        selection = plan(paths)
        report.update(identity=identity, plan=selection)
        print(json.dumps({"identity": identity, "plan": selection}), flush=True)
        for name, command, timeout in commands(selection["mode"], args.evidence, args.toolchain):
            started = time.monotonic()
            result = {"command": command, "status": "running"}
            report["checks"][name] = result
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            log = args.evidence / (name + ".log")
            with log.open("w") as output:
                try:
                    process = subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
                    result.update(exit=process.returncode, status="success" if process.returncode == 0 else "failure")
                except subprocess.TimeoutExpired:
                    result.update(exit=None, status="timed_out")
            result["seconds"] = round(time.monotonic() - started, 3)
            print(f"{name}: {result['status']}", flush=True)
            if result["status"] != "success":
                print(log.read_text()[-6000:], flush=True)
                raise ValueError("Required test failed: " + name)
        assert_pass(report, identity)
        report["conclusion"] = "success"
        print("PASS: non-empty applicable tests at the recorded head/current base")
        return 0
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        report.update(conclusion="failure", error=str(error))
        print("FAIL:", error, file=sys.stderr)
        return 1
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
