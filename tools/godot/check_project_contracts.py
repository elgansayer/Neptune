#!/usr/bin/env python3
"""Check real addon loading and BotTestSuite's null contract, not bot quality."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from run_bot_tests import ANSI, ERROR, MARKER, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True)
    parser.add_argument("--evidence", type=Path, default=ROOT / ".godot/restart-evidence")
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "USER", "LOGNAME")}
    for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        folder = ROOT / ".godot/restart-runtime" / key.lower()
        folder.mkdir(parents=True, exist_ok=True)
        env[key] = str(folder)
    with (args.evidence / "project-import.log").open("w") as log:
        imported = subprocess.run([args.godot, "--headless", "--editor", "--path", str(ROOT), "--import", "--quit"],
                                  env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90)
    text = ANSI.sub("", (args.evidence / "project-import.log").read_text())
    if imported.returncode != 0 or ERROR.search(text):
        raise SystemExit("FAIL: actual project import; inspect project-import.log")
    suite = '''extends "res://tests/bot_test_suite.gd"
func setup_suite():
\tpass
func teardown_suite():
\tpass
func setup_test():
\tpass
func teardown_test():
\tpass
func test_result() -> Variant:
\treturn RETURN_VALUE
'''
    probes = {
        "null": (suite.replace("RETURN_VALUE", "null"), 1, 0, 1),
        "true": (suite.replace("RETURN_VALUE", "true"), 0, 1, 0),
        "addons": ('extends Node\nfunc execute() -> bool:\n\treturn ClassDB.class_exists("BTPlayer") and ClassDB.class_exists("SQLite")\n', 0, 1, 0),
    }
    with tempfile.TemporaryDirectory(prefix="runner-contract-", dir=ROOT / "tests") as temp:
        directory = Path(temp)
        for name, (source, expected_exit, passed, failed) in probes.items():
            script = directory / (name + "_test.gd")
            script.write_text(source)
            log = args.evidence / (name + "-contract.log")
            command = [sys.executable, str(ROOT / "tools/godot/run_bot_tests.py"), "--godot", args.godot,
                       "--run-specific", "res://" + script.relative_to(ROOT).as_posix(),
                       "--timeout", "15", "--log", str(log)]
            result = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=25)
            (args.evidence / (name + "-supervisor.log")).write_text(result.stdout)
            text = ANSI.sub("", log.read_text())
            records = [json.loads(line[len(MARKER):]) for line in text.splitlines() if line.startswith(MARKER)]
            if (result.returncode != expected_exit or ERROR.search(text) or len(records) != 1
                    or records[0]["passed"] != passed or records[0]["failed"] != failed):
                raise SystemExit("FAIL: " + name + " actual project contract; inspect " + str(log))
            print("PASS: actual project", name, "contract; exit", result.returncode)
    print("These are actual suite/addon contract checks, not bot survival or parity checks.")


if __name__ == "__main__":
    main()
