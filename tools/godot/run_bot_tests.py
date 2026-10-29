#!/usr/bin/env python3
"""Supervise real Godot tests. A zero engine exit code alone is not success."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
MARKER = "NEPTUNE_TEST_RESULT="
ERROR = re.compile(r"(?:^|\n)\s*(?:SCRIPT ERROR:|ERROR:|USER ERROR:|Parse Error:|SHADER ERROR:)")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def terminate_supervisor(signum, _frame):
    raise SystemExit(128 + signum)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default=os.environ.get("GODOT_BIN", "godot"))
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--max-log-mib", type=int, default=8)
    parser.add_argument("--max-fps", type=int, help="Bound idle/render cadence for native runtime experiments")
    select = parser.add_mutually_exclusive_group()
    select.add_argument("--run-specific")
    select.add_argument("--run-category")
    select.add_argument("--run-all", action="store_true")
    args = parser.parse_args()
    if not 0 < args.timeout <= 600:
        parser.error("--timeout must be greater than zero and at most 600 seconds")
    if not 1 <= args.max_log_mib <= 32:
        parser.error("--max-log-mib must be between 1 and 32")
    if args.max_fps is not None and not 1 <= args.max_fps <= 240:
        parser.error("--max-fps must be between 1 and 240")
    max_log_bytes = args.max_log_mib * 1024 * 1024
    if args.run_specific == "" or args.run_category == "":
        parser.error("Selections cannot be empty")
    project = args.project.resolve()
    candidate = args.log or project / "test_results.log"
    if candidate.suffix != ".log" or candidate.is_symlink():
        parser.error("--log must name a non-symlink .log file")
    log = candidate.resolve()
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [args.godot, "--headless", "--path", str(project),
               "res://tests/bot_test_runner.tscn", "--", "--runtime-role=test"]
    if args.max_fps is not None:
        command[1:1] = ["--max-fps", str(args.max_fps)]
    if args.run_specific is not None:
        command.append("--run-specific=" + args.run_specific)
    elif args.run_category is not None:
        command.append("--run-category=" + args.run_category)
    else:
        command.append("--run-all")
    # Do not forward provider tokens or operator credentials to game scripts.
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "USER", "LOGNAME")}
    for key, directory in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache")):
        location = project / ".godot" / "restart-runtime" / directory
        location.mkdir(parents=True, exist_ok=True)
        env[key] = str(location)
    started = time.monotonic()
    stopped = ""
    with log.open("w", encoding="utf-8") as output:
        try:
            process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                       env=env, start_new_session=True)
        except OSError as exc:
            print(f"FAIL: Cannot start Godot: {exc}")
            return 1
        signal.signal(signal.SIGTERM, terminate_supervisor)
        try:
            while process.poll() is None:
                if time.monotonic() - started > args.timeout:
                    stopped = "timeout"
                elif log.stat().st_size > max_log_bytes:
                    stopped = "log byte limit exceeded"
                if stopped:
                    break
                time.sleep(0.02)
        finally:
            # Reap Godot even if this supervisor is interrupted or terminated.
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
    with log.open("rb") as source:
        raw = source.read(max_log_bytes + 1)
    text = ANSI.sub("", raw.decode("utf-8", errors="replace"))
    print(text[-12000:])
    print(f"Godot exit={process.returncode}; log={log}")
    if stopped or len(raw) > max_log_bytes:
        print("FAIL: " + (stopped or "log byte limit exceeded"))
        return 1
    if process.returncode != 0 or ERROR.search(text):
        print("FAIL: Engine exit or logged engine/script error")
        return 1
    summaries = [line[len(MARKER):] for line in text.splitlines() if line.startswith(MARKER)]
    if len(summaries) != 1:
        print("FAIL: Expected exactly one complete test summary")
        return 1
    try:
        result = json.loads(summaries[0])
        if not isinstance(result, dict) or result.get("schema") != 1:
            raise ValueError("unsupported summary schema")
        for key in ("files", "passed", "failed"):
            if type(result.get(key)) is not int or result[key] < 0:
                raise ValueError("invalid counters")
        if result["files"] == 0 or result["passed"] == 0 or result["failed"] != 0:
            raise ValueError("empty or failing run")
        results = result.get("results")
        if not isinstance(results, dict) or len(results) != result["passed"] or any(v != "PASS" for v in results.values()):
            raise ValueError("results do not match passing counters")
    except (ValueError, TypeError, KeyError) as exc:
        print(f"FAIL: Invalid test summary: {exc}")
        return 1
    print(f"PASS: {result['passed']} tests in {result['files']} files (runner evidence only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
