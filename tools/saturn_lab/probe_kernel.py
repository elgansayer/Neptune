#!/usr/bin/env python3
"""Test one upstream kernel hypothesis against the pinned private USA original.

No game bytes or third-party implementation are included. This is a bounded
CPU-only experiment, not whole-game or hardware validation. See
docs/restart/research/2026-10-30-deep-dive.md for attribution and limitations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import types

BASE = 0x06006000
ENTRY = 0x0600A4B0
SIZE = 786432
KERNEL_SHA256 = "20109f506afd076af8a8583121dbb5a4880e0a764ee8e004c17b0cb055c798a7"
UPSTREAM_SHA1 = "6fc53e5715d89cae7b4684bb3b65165ac1865736"
INTERPRETER_REVISION = "f20de940e8013fc84103a5b39c4069ed8071b1f9"
SOURCE_HASHES = {
    "hw": "a0a1e036358474b41fd594a1dd2fae9024e3e63059682367aca57eac257d231d",
    "sh2": "0add78272f1ee398881fbca2850d8d89b4cbd5a7767448299b39498f60d703dd",
    "sh2emu": "c43458498cde2f4b727aab6298cfba84487b03fcecd544161ab0c7007e13c253",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bounded(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"Input exceeds {limit} bytes: {path.name}")
    return data


def kernel_bytes(path: Path) -> bytes:
    data = read_bounded(path, SIZE)
    if len(data) != SIZE or digest(data) != KERNEL_SHA256:
        raise ValueError("Kernel differs from accepted USA MK-81070 V1.003 inventory")
    if hashlib.sha1(data).hexdigest() != UPSTREAM_SHA1:
        raise ValueError("Kernel differs from upstream disc.json")
    return data


def interpreter(source_root: Path):
    """Verify all three files before loading their exact bytes; skip package __init__.

    This executes trusted, hash-pinned Python in the ordinary unprivileged
    research environment. Hash checking is not an OS sandbox.
    """
    sources = {}
    for name, expected in SOURCE_HASHES.items():
        content = read_bounded(source_root / "src" / "saturnrecomp" / (name + ".py"), 65536)
        if digest(content) != expected:
            raise ValueError(f"Interpreter source mismatch: {name}.py")
        sources[name] = content
    package_name = "_neptune_pinned_sh2"
    package = types.ModuleType(package_name)
    package.__path__ = []
    names = [package_name] + [package_name + "." + name for name in sources]
    previous = {name: sys.modules.get(name) for name in names}
    try:
        sys.modules[package_name] = package
        for name, content in sources.items():
            module = types.ModuleType(package_name + "." + name)
            module.__package__ = package_name
            sys.modules[module.__name__] = module
            setattr(package, name, module)
            exec(compile(content, f"pinned-saturn-recomp/{name}.py", "exec"), module.__dict__)
        return package.sh2emu
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def candidate(value: int) -> int:
    """Upstream f0600A4B0 hypothesis; names/directions remain unverified."""
    for bit, result in ((0x4000, 3), (0x2000, 2), (0x8000, 1), (0x1000, 4)):
        if value & bit:
            return result
    return 0


def inputs() -> list[int]:
    # All sixteen direction-bit combinations, four low-bit patterns and four
    # upper-word patterns. This is 256 cases, NOT all 2**32 possible arguments.
    return [upper | (mask << 12) | low
            for upper in (0, 0xFFFF0000, 0x80000000, 0x55550000)
            for mask in range(16) for low in (0, 0xFFF, 0x555, 0xAAA)]


def exercise(call) -> dict:
    cases = inputs()
    if len(cases) != 256 or len(set(cases)) != 256:
        raise ValueError("Probe case coverage changed")
    results = []
    for argument in cases:
        actual, steps = call(argument)
        expected = candidate(argument)
        if type(actual) is not int or actual != expected:
            raise ValueError(f"Mismatch for 0x{argument:08x}: expected {expected}, got {actual!r}")
        if type(steps) is not int or not 0 < steps <= 256:
            raise ValueError("Invalid instruction-count evidence")
        results.append([argument, actual, steps])
    # Mutation controls: a changed result and reversed precedence must disagree.
    wrong_result = sum((0 if candidate(v) == 3 else candidate(v)) != candidate(v) for v in cases)
    wrong_priority = sum((1 if v & 0x8000 else candidate(v)) != candidate(v) for v in cases)
    if wrong_result == 0 or wrong_priority == 0:
        raise ValueError("Mutation controls did not detect changed semantics")
    return {"cases": len(results), "results_sha256": digest(json.dumps(results).encode()),
            "max_instructions": max(row[2] for row in results),
            "mutation_rejections": {"changed_return": wrong_result, "changed_priority": wrong_priority},
            "results": results}


def execute(data: bytes, sh2emu) -> dict:
    # The candidate is a pure leaf. Refuse all writes and non-module accesses;
    # do not silently turn hardware registers into RAM as some upstream tests do.
    class ReadOnlyMemory(sh2emu.Memory):
        def write(self, addr, size, value):
            raise ValueError(f"Unexpected write at 0x{addr:08x}; revise the hypothesis with evidence")

    memory = ReadOnlyMemory()
    memory.add(BASE, len(data), data)

    def call(argument):
        cpu = sh2emu.CPU(memory)
        cpu.r = [0xA5A5A5A5] * 16
        cpu.r[15] = 0x060FFFF0
        result = cpu.call(ENTRY, max_steps=256, r4=argument)
        return result, cpu.steps

    return exercise(call)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True,
                        help="Checkout of the pinned dependency (no network access by this tool)")
    parser.add_argument("--report", type=Path, required=True, help="New private JSON report; never overwritten")
    args = parser.parse_args(argv)
    report = {"schema": "neptune.kernel-probe.v1", "status": "failure",
              "experiment": "EXP-SAT-CODE-001", "entry": hex(ENTRY),
              "game": "USA MK-81070 V1.003", "kernel_sha256": KERNEL_SHA256,
              "interpreter_revision": INTERPRETER_REVISION, "interpreter_sources": SOURCE_HASHES,
              "probe_sha256": digest(Path(__file__).read_bytes()),
              "scope": "isolated original SH-2 routine; 256 input samples; CPU interpreter only",
              "limitations": ["No original gameplay/caller validation", "No timing or hardware equivalence",
                              "Shared upstream interpreter is not an independent oracle",
                              "No spritesheet extracted", "Not exhaustive over 32-bit input"]}
    # Exclusive create prevents a failed rerun from overwriting accepted evidence.
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                data = kernel_bytes(args.kernel)
                result = execute(data, interpreter(args.saturn_recomp))
                report.update(status="success", **result)
            except Exception as error:
                report["error"] = f"{type(error).__name__}: {error}"
            output.write(json.dumps(report, indent=2) + "\n")
    except OSError as error:
        print(f"FAIL: cannot create fresh report: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "experiment": report["experiment"],
                      "report": str(args.report), "cases": report.get("cases", 0)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
