#!/usr/bin/env python3
"""Sample declared SH-2 WorkRAM-H values across a verified checkpoint restore lineage.

Passive natural observation: values are read from existing captured Beetle
states; nothing is executed or modified. Consecutive checkpoints count as one
lineage only when the later run's recorded command restored the earlier
checkpoint's exact state and its frame number equals the earlier frame plus its
``--frames``. Deltas are reported only for verified pairs. Optional witnesses
require original kernel byte ranges to be resident unchanged in every sample.
The report holds identities and derived values, never RAM or module bytes.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

import state_graphics

SCHEMA = "neptune.workram-lineage-samples.v1"
WORKRAM_H_BASE = 0x06000000
WORKRAM_H_SIZE = 0x100000
MAX_JSON = 2 * 1024 * 1024
MAX_MODULE = 8 * 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Input exceeds its size bound: " + path.name)
    return data


def canonical(address: int) -> int:
    """Fold the SH-2 cache-through window onto the cached address."""
    return address & 0x1FFFFFFF if address >> 29 == 1 else address


def load_checkpoint(directory: Path) -> dict:
    """Verified checkpoint metadata, WorkRAM-H in SH-2 byte order and the run command."""
    metadata = json.loads(_read(directory / "checkpoint.json", MAX_JSON))
    relative = Path(metadata["state_path"])
    if relative.is_absolute() or len(relative.parts) != 1 or ".." in relative.parts:
        raise ValueError("Checkpoint state path must be a sibling filename")
    state = _read(directory / relative, state_graphics.MAX_STATE)
    if len(state) != metadata.get("state_bytes") or sha(state) != metadata.get("state_sha256"):
        raise ValueError("Checkpoint state size/hash mismatch: " + str(directory))
    parsed = state_graphics.parse(state)
    ram = state_graphics.cpu_words(state_graphics.field(parsed, "MAIN", "WorkRAMH", WORKRAM_H_SIZE), "little")
    command = None
    process = directory / "process.json"
    if process.is_file():
        command = json.loads(_read(process, MAX_JSON)).get("command")
    if type(metadata.get("frame")) is not int or metadata["frame"] < 0:
        raise ValueError("Checkpoint frame must be a nonnegative integer")
    return {"directory": directory, "frame": metadata["frame"], "state_sha256": metadata["state_sha256"],
            "ram": ram, "command": command}


def _argument(command, name):
    if not isinstance(command, list):
        return None
    values = [command[i + 1] for i, item in enumerate(command[:-1]) if item == name]
    return values[0] if len(values) == 1 else None


def lineage(earlier: dict, later: dict) -> dict:
    """Prove ``later`` restored ``earlier``'s exact state, or say why not."""
    restore = _argument(later["command"], "--restore")
    frames = _argument(later["command"], "--frames")
    if restore is None or frames is None:
        return {"verified": False, "reason": "later run records no single --restore/--frames"}
    restored = Path(restore)
    try:
        metadata = json.loads(_read(restored, MAX_JSON))
    except (OSError, ValueError) as error:
        return {"verified": False, "reason": "restore metadata unreadable: " + type(error).__name__}
    if metadata.get("state_sha256") != earlier["state_sha256"]:
        return {"verified": False, "reason": "restored state differs from the earlier checkpoint"}
    if not frames.isdigit() or later["frame"] != earlier["frame"] + int(frames):
        return {"verified": False, "reason": "frame numbers do not add up"}
    return {"verified": True, "frames": int(frames), "restored_state_sha256": metadata["state_sha256"]}


def read_value(ram: bytes, address: int, size: int) -> int:
    address = canonical(address)
    if size not in (1, 2, 4) or address % size or not WORKRAM_H_BASE <= address <= WORKRAM_H_BASE + WORKRAM_H_SIZE - size:
        raise ValueError("Value must be an aligned 1/2/4-byte WorkRAM-H location")
    offset = address - WORKRAM_H_BASE
    return int.from_bytes(ram[offset:offset + size], "big")


def witness(ram: bytes, kernel: bytes, kernel_base: int, address: int, length: int) -> bool:
    if length <= 0 or not kernel_base <= address or address + length > kernel_base + len(kernel):
        raise ValueError("Witness range must lie inside the declared kernel mapping")
    if not WORKRAM_H_BASE <= address or address + length > WORKRAM_H_BASE + WORKRAM_H_SIZE:
        raise ValueError("Witness range must lie inside WorkRAM-H")
    start = address - kernel_base
    return ram[address - WORKRAM_H_BASE:address - WORKRAM_H_BASE + length] == kernel[start:start + length]


def sample(checkpoints: list[dict], values: dict, kernel: bytes | None = None, kernel_base: int = 0,
           witnesses=(), expectations=None) -> dict:
    rows, pairs, failures = [], [], []
    for checkpoint in checkpoints:
        row = {"frame": checkpoint["frame"], "state_sha256": checkpoint["state_sha256"],
               "workram_h_sha256": sha(checkpoint["ram"]),
               "values": {name: read_value(checkpoint["ram"], address, size) for name, (address, size) in values.items()}}
        if witnesses:
            row["witnesses"] = {"%08X+%d" % (address, length): witness(checkpoint["ram"], kernel, kernel_base, address, length)
                                for address, length in witnesses}
            if not all(row["witnesses"].values()):
                failures.append("witness not resident at frame %d" % checkpoint["frame"])
        rows.append(row)
    for earlier, later, a, b in zip(checkpoints, checkpoints[1:], rows, rows[1:]):
        link = lineage(earlier, later)
        pair = {"from_frame": a["frame"], "to_frame": b["frame"], "lineage": link}
        if link["verified"]:
            pair["deltas"] = {name: (b["values"][name] - a["values"][name]) % (1 << (8 * values[name][1]))
                              for name in values}
        pairs.append(pair)
    for name, rate in (expectations or {}).items():
        verified = [p for p in pairs if p["lineage"]["verified"]]
        if not verified:
            failures.append("expectation %s has no verified pair" % name)
        for pair in verified:
            expected = Fraction(pair["lineage"]["frames"]) * rate
            if expected.denominator != 1 or pair["deltas"][name] != expected.numerator:
                failures.append("%s changed by %d over %d frames, expected %s per frame" % (
                    name, pair["deltas"][name], pair["lineage"]["frames"], rate))
    return {"schema": SCHEMA, "samples": rows, "pairs": pairs, "failures": failures,
            "passed": not failures,
            "limitations": ["Passive samples of captured states; nothing was executed",
                            "Values between samples are unobserved; a delta is net change, not a count of writes",
                            "Address roles come from separate static evidence, not from these samples"]}


def _named(text: str):
    name, _, spec = text.partition("=")
    address, _, size = spec.partition(":")
    if not name or not address or not size:
        raise argparse.ArgumentTypeError("use NAME=HEXADDRESS:SIZE")
    return name, (int(address, 16), int(size))


def _range(text: str):
    address, _, length = text.partition(":")
    return int(address, 16), int(length)


def _rate(text: str):
    name, _, value = text.partition("=")
    if not name or not value:
        raise argparse.ArgumentTypeError("use NAME=NUMERATOR/DENOMINATOR")
    return name, Fraction(value)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checkpoint", type=Path, action="append", required=True, help="checkpoint directory, in order")
    parser.add_argument("--value", type=_named, action="append", required=True)
    parser.add_argument("--kernel", type=Path)
    parser.add_argument("--expected-kernel-sha256")
    parser.add_argument("--kernel-base", type=lambda text: int(text, 16), default=0x06006000)
    parser.add_argument("--witness", type=_range, action="append", default=[], help="HEXADDRESS:LENGTH")
    parser.add_argument("--expect-rate", type=_rate, action="append", default=[])
    parser.add_argument("--report", type=Path, required=True, help="new private JSON report")
    args = parser.parse_args(argv)
    values = dict(args.value)
    if len(values) != len(args.value):
        print("FAIL: duplicate value names", file=sys.stderr)
        return 1
    expectations = dict(args.expect_rate)
    if any(name not in values for name in expectations):
        print("FAIL: expectation for an undeclared value", file=sys.stderr)
        return 1
    kernel = None
    if args.witness:
        if not args.kernel or not args.expected_kernel_sha256:
            print("FAIL: witnesses need --kernel and --expected-kernel-sha256", file=sys.stderr)
            return 1
        kernel = _read(args.kernel, MAX_MODULE)
        if sha(kernel) != args.expected_kernel_sha256:
            print("FAIL: kernel differs from the declared identity", file=sys.stderr)
            return 1
    report = sample([load_checkpoint(path) for path in args.checkpoint], values, kernel, args.kernel_base,
                    args.witness, expectations)
    report["values"] = {name: {"address": "%08X" % address, "bytes": size} for name, (address, size) in values.items()}
    report["expectations"] = {name: str(rate) for name, rate in expectations.items()}
    report["kernel_sha256"] = None if kernel is None else sha(kernel)
    report["tool_sha256"] = sha(Path(__file__).read_bytes())
    with args.report.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"passed": report["passed"], "failures": report["failures"],
                      "pairs": [{k: p[k] for k in p if k != "lineage"} | {"verified": p["lineage"]["verified"]}
                                for p in report["pairs"]]}, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
