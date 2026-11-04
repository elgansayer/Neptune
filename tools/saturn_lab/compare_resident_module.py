#!/usr/bin/env python3
"""Compare a private module image with one mapped into captured SH-2 WorkRAM.

The report contains identities and matching address ranges only; it never
copies original module or save-state bytes to the report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

import probe_kernel
import state_graphics

WORKRAM_H_BASE = 0x06000000
WORKRAM_H_SIZE = 0x100000
MAX_MODULE_BYTES = 8 * 1024 * 1024
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def matching_ranges(source: bytes, ram: bytes, offset: int, minimum: int = 16) -> list[tuple[int, int]]:
    """Return source-relative half-open ranges that exactly match mapped RAM."""
    if not source or len(source) > MAX_MODULE_BYTES:
        raise ValueError("Module size is outside the bounded 1..8 MiB range")
    if len(ram) != WORKRAM_H_SIZE or type(offset) is not int or offset < 0 or offset + len(source) > len(ram):
        raise ValueError("Mapped module must fit wholly inside the captured 1 MiB WorkRAM-H region")
    if type(minimum) is not int or not 1 <= minimum <= len(source):
        raise ValueError("Minimum exact-run size is outside the module bounds")
    ranges = []
    start = None
    for index, (left, right) in enumerate(zip(source, ram[offset:offset + len(source)])):
        if left == right:
            if start is None:
                start = index
        elif start is not None:
            if index - start >= minimum:
                ranges.append((start, index))
            start = None
    if start is not None and len(source) - start >= minimum:
        ranges.append((start, len(source)))
    return ranges


def analyze(source_path: Path, expected_source_sha256: str, checkpoint_path: Path,
            mapping: int, minimum: int = 16) -> dict:
    if not SHA256_RE.fullmatch(expected_source_sha256):
        raise ValueError("Require a lowercase SHA-256 for the expected original module")
    source = probe_kernel.read_bounded(source_path, MAX_MODULE_BYTES)
    if not source or sha(source) != expected_source_sha256:
        raise ValueError("Original module size/hash differs from the pinned identity")
    metadata = json.loads(probe_kernel.read_bounded(checkpoint_path, 2 * 1024**2))
    relative = Path(metadata["state_path"])
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
        raise ValueError("Checkpoint state path must be a sibling filename")
    state_path = checkpoint_path.parent / relative
    state = probe_kernel.read_bounded(state_path, state_graphics.MAX_STATE)
    if len(state) != metadata.get("state_bytes") or sha(state) != metadata.get("state_sha256"):
        raise ValueError("Checkpoint state size/hash mismatch")
    if type(mapping) is not int or not WORKRAM_H_BASE <= mapping < WORKRAM_H_BASE + WORKRAM_H_SIZE:
        raise ValueError("Mapping must start inside captured SH-2 WorkRAM-H")
    offset = mapping - WORKRAM_H_BASE
    parsed = state_graphics.parse(state)
    ram = state_graphics.cpu_words(state_graphics.field(parsed, "MAIN", "WorkRAMH", WORKRAM_H_SIZE), "little")
    ranges = matching_ranges(source, ram, offset, minimum)
    return {
        "schema": "neptune.resident-module-comparison.v1",
        "status": "success",
        "source_bytes": len(source),
        "source_sha256": sha(source),
        "checkpoint_frame": metadata.get("frame"),
        "checkpoint_state_sha256": metadata["state_sha256"],
        "workram_h_base": f"0x{WORKRAM_H_BASE:08x}",
        "workram_h_bytes": len(ram),
        "workram_h_sha256": sha(ram),
        "candidate_mapping": f"0x{mapping:08x}",
        "minimum_exact_range_bytes": minimum,
        "matching_ranges": [{"source_start": f"0x{start:x}",
                              "source_end_exclusive": f"0x{end:x}",
                              "mapped_start": f"0x{mapping + start:08x}",
                              "mapped_end_exclusive": f"0x{mapping + end:08x}",
                              "bytes": end - start} for start, end in ranges],
        "matching_range_count": len(ranges),
        "matching_bytes": sum(end - start for start, end in ranges),
        "limitations": ["Exact byte identity in one save-state WorkRAM-H image does not prove those instructions executed",
                        "Ranges below the declared minimum are omitted",
                        "Only the requested candidate mapping and captured state are compared"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--mapping", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--minimum-range", type=int, default=16)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    result = analyze(args.source, args.expected_source_sha256, args.checkpoint,
                     args.mapping, args.minimum_range)
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(args.report, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(payload)
    print(json.dumps({"status": result["status"],
                      "matching_range_count": result["matching_range_count"],
                      "matching_bytes": result["matching_bytes"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
