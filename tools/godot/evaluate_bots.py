#!/usr/bin/env python3
"""Run bounded real-physics bot liveness matches and retain failed evidence too.

This is a two-scenario diagnostic, not a tournament or policy-promotion gate.
The existing supervisor remains authoritative about engine and script errors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
MARKER = "BOT_MATCH_EVIDENCE="
EXPECTED = {(4, "46271"), (12, "81439")}


def read_matches(log: str) -> list[dict]:
    matches = []
    identities = set()
    for line in log.splitlines():
        if not line.startswith(MARKER):
            continue
        value = json.loads(line[len(MARKER):])
        if not isinstance(value, dict) or value.get("schema") != 1:
            raise ValueError("Unsupported bot evidence schema")
        if type(value.get("participants")) is not int or not isinstance(value.get("policy_seed"), str):
            raise ValueError("Malformed participant or seed identity")
        identity = (value["participants"], value["policy_seed"])
        if identity not in EXPECTED or identity in identities:
            raise ValueError("Unexpected or duplicate bot match")
        identities.add(identity)
        if value.get("purpose") != "short-native-liveness-not-policy-promotion":
            raise ValueError("Evidence is not the requested liveness scenario")
        if value.get("physics_frames_observed", 0) < 120 or value.get("manager_cost_usec", {}).get("samples", 0) < 120:
            raise ValueError("No sufficiently sampled real simulation")
        if value.get("eliminations", {}).get("discarded", -1) != 0:
            raise ValueError("Missing or truncated causal elimination evidence")
        if len(value.get("roster", [])) != identity[0]:
            raise ValueError("Incomplete actual participant roster")
        matches.append(value)
    if identities != EXPECTED:
        raise ValueError("Expected both complete four- and twelve-bot matches")
    return matches


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default=os.environ.get("GODOT_BIN", "godot"))
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    if not 0 < args.timeout <= 600:
        parser.error("--timeout must be greater than zero and at most 600 seconds")
    directory = args.evidence.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    report_file = directory / "bot-matches.json"
    log_file = directory / "bot-matches.log"
    if report_file.exists() or log_file.exists():
        parser.error("Use a new evidence directory; previous evidence is immutable")
    executable = shutil.which(args.godot)
    if executable is None:
        parser.error("Godot executable is unavailable")
    executable_path = Path(executable).resolve()
    command = [sys.executable, str(ROOT / "tools/godot/run_bot_tests.py"),
               "--godot", str(executable_path), "--run-specific", "test_bot_match_liveness",
               "--timeout", str(args.timeout), "--max-log-mib", "16", "--log", str(log_file)]
    with executable_path.open("rb") as binary:
        binary_sha256 = hashlib.file_digest(binary, "sha256").hexdigest()
    report = {"schema": 1, "purpose": "short-native-liveness-not-policy-promotion",
              "git_head": git("rev-parse", "HEAD"), "working_tree_dirty": bool(git("status", "--porcelain")),
              "godot_path": str(executable_path), "godot_sha256": binary_sha256,
              "command": command, "matches": [], "passing": False}
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=ROOT, timeout=args.timeout + 15, check=False)
        report["supervisor_exit"] = result.returncode
        # Retain diagnostic results even if the supervisor rejected the engine.
        report["matches"] = read_matches(log_file.read_text(encoding="utf-8"))
        report["passing"] = result.returncode == 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report["error"] = str(exc)
    finally:
        report["wall_seconds"] = round(time.monotonic() - started, 3)
        report_file.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"{'PASS' if report['passing'] else 'FAIL'}: bot liveness evidence: {report_file}")
    return 0 if report["passing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
