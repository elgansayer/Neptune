#!/usr/bin/env python3
"""Inspect trusted intake or coordinator state; never start a model/provider."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time

from readiness import ContractError, evaluate
from store import JobStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ready = sub.add_parser("readiness")
    ready.add_argument("snapshot", type=Path)
    for name in ("enqueue", "show", "recover", "status"):
        command = sub.add_parser(name)
        command.add_argument("--database", type=Path, required=True)
        if name == "enqueue":
            command.add_argument("snapshot", type=Path)
        if name == "show":
            command.add_argument("job")
    args = parser.parse_args()
    try:
        if args.command == "readiness":
            result = evaluate(json.loads(args.snapshot.read_text()), time.time())
            print(json.dumps(result, indent=2))
            return 0 if result["ready"] else 1
        store = JobStore(args.database)
        try:
            if args.command == "enqueue":
                result = {"job": store.enqueue(json.loads(args.snapshot.read_text()))}
            elif args.command == "status":
                result = store.status()
            elif args.command == "show":
                result = store.get(args.job)
                result.pop("token", None)
            else:
                store.recover()
                result = {"recovered": True, "scope": "local leases only"}
            print(json.dumps(result, indent=2))
        finally:
            store.close()
        return 0
    except (ValueError, TypeError, OSError, sqlite3.Error) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
