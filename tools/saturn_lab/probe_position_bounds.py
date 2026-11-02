#!/usr/bin/env python3
"""Bounded original-USA position writes and a direct caller; no game bytes bundled."""
from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path

import probe_kernel as pinned

LEAF = 0x0600A3E0
CALLER = 0x0600A3FA
OBJECTS = 0x060C381C
BUFFER = 0x00204000
DESCRIPTOR = 0x00205000
STACK = 0x060FFFD0
SP = STACK + 32
LIMIT = 128
MASK = 0xFFFFFFFF
EXPERIMENT = "EXP-SAT-CODE-003"


def signed(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def expected_record(record, descriptor, horizontal, vertical=None):
    """Independent byte-oriented contract; all final writes truncate to 16 bits."""
    result = bytearray(record)
    for position, low, high, first, second, delta in (
        (16, 20, 24, 0, 2, horizontal),
        (18, 22, 26, 1, 3, vertical),
    ):
        if delta is None:
            continue
        coordinate = signed(int.from_bytes(record[position:position + 2], "big"), 16)
        lo = coordinate - delta
        hi = coordinate + signed(descriptor[first], 8) - signed(descriptor[second], 8) + delta
        result[low:low + 2] = (lo & 0xFFFF).to_bytes(2, "big")
        result[high:high + 2] = (hi & 0xFFFF).to_bytes(2, "big")
    return bytes(result)


def cases():
    # A complete small Cartesian product plus constructed signs/wraps. Never
    # present constructed records, descriptors or indices as observed gameplay.
    coordinates = (0, 1, 0x7FFF, 0x8000, 0xFFFF)
    descriptors = ((0, 1, 2, 3), (0x7F, 0x80, 0xFF, 0),
                   (0x80, 0xFF, 0x7F, 0x80), (0xFF, 0x7F, 0x80, 0xFF))
    deltas = (0, 1, 0x7FFF, 0x8000, 0xFFFF, 0x10000, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)
    return list(itertools.product(coordinates, descriptors, deltas))


def run_case(data, emu, entry, coordinate, descriptor, delta, index=0):
    if len(data) != pinned.SIZE or entry not in (LEAF, CALLER):
        raise ValueError("Invalid original module extent or function entry")
    caller = entry == CALLER
    record_address = OBJECTS + ((index * 84) & 0xFFFF) if caller else BUFFER
    record = bytearray((i * 37 + 19) & 255 for i in range(84))
    record[16:18] = coordinate.to_bytes(2, "big")
    record[18:20] = ((coordinate ^ 0xA55A) & 0xFFFF).to_bytes(2, "big")
    descriptor = bytes(descriptor)
    horizontal = signed(delta, 16) if caller else delta
    vertical = signed(delta ^ 0x5555, 16) if caller else None
    expected = expected_record(record, descriptor, horizontal, vertical)
    write_offsets = (20, 22, 24, 26) if caller else (20, 24)
    permitted = {(record_address + offset, 2) for offset in write_offsets}
    stack_writes = {(SP - offset, size) for offset, size in
                    ((4, 4), (8, 4), (12, 4), (16, 4), (24, 2), (20, 2))} if caller else set()

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.writes = []
            self.record_reads = []
            self.descriptor_reads = []

        def read(self, address, size):
            # No cache-through alias or implicit invented device state allowed.
            if record_address <= address < record_address + 84:
                if (address - record_address, size) not in ((16, 2), (18, 2)):
                    raise ValueError("Unexpected record read")
                self.record_reads.append((address - record_address, size))
            if DESCRIPTOR <= address < DESCRIPTOR + 4:
                if size != 1:
                    raise ValueError("Unexpected descriptor access width")
                self.descriptor_reads.append(address - DESCRIPTOR)
            return super().read(address, size)

        def write(self, address, size, value):
            if (address, size) not in permitted | stack_writes:
                raise ValueError("Write outside declared output fields and stack slots")
            self.writes.append((address, size))
            return super().write(address, size, value)

    memory = Memory()
    # A controlled record may lie within the file's mapped extent. Carve it out
    # explicitly rather than using ambiguous overlapping Memory regions. The
    # executed code/literals remain original; initialized data is test input.
    end = pinned.BASE + len(data)
    if record_address < end and record_address + 84 > pinned.BASE:
        left = record_address - pinned.BASE
        memory.add(pinned.BASE, left, data[:left])
        if record_address + 84 < end:
            memory.add(record_address + 84, end - record_address - 84, data[left + 84:])
    else:
        memory.add(pinned.BASE, len(data), data)
    actual_record = memory.add(record_address, 84, record)
    memory.add(DESCRIPTOR, 4, descriptor)
    if caller:
        memory.add(STACK, 32, bytes([0xCD]) * 32)
    baseline = [(lo, bytes(buf)) for lo, _, buf in memory.regions]

    class CPU(emu.CPU):
        def __init__(self, mem):
            super().__init__(mem)
            self.visited = []

        def exec(self, instruction, pc, in_slot=False):
            if len(self.visited) >= LIMIT:
                raise ValueError("Instruction budget exceeded")
            if not (LEAF <= pc < (0x0600A44A if caller else 0x0600A3FA)):
                raise ValueError("Execution outside inspected original function ranges")
            self.visited.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [0xA5A5A5A5] * 16
    cpu.r[15] = SP
    cpu.r[4:8] = [index if caller else record_address, DESCRIPTOR,
                  delta ^ 0x5555 if caller else delta, delta]
    cpu.macl, cpu.mach = 0x13579BDF, 0x2468ACE0
    cpu.sr = 0x3F3
    cpu.pr = emu.RETURN_SENTINEL
    before = {**{f"r{i}": v for i, v in enumerate(cpu.r)},
              **{name: getattr(cpu, name) for name in ("sr", "pr", "macl", "mach", "gbr", "vbr")}}
    cpu.call(entry, max_steps=LIMIT)
    if cpu.pc != emu.RETURN_SENTINEL or cpu.steps != len(cpu.visited):
        raise ValueError("Missing return or delay-slot accounting")
    if bytes(actual_record) != expected:
        raise ValueError("Position output differs from independent byte contract")
    if set(memory.writes) != permitted | stack_writes or len(memory.writes) != len(permitted | stack_writes):
        raise ValueError("Missing, repeated or unexpected write")
    allowed_bytes = {address + offset for address, size in permitted | stack_writes for offset in range(size)}
    for (lo, original), (_, _, buf) in zip(baseline, memory.regions):
        if bytes(buf) == original:
            continue
        if any(a != b and lo + offset not in allowed_bytes
               for offset, (a, b) in enumerate(zip(original, buf))):
            raise ValueError("Unaffected mapped byte changed")
    after = {name: cpu.r[int(name[1:])] if name.startswith("r") and name[1:].isdigit()
             else getattr(cpu, name) for name in before}
    changed = sorted(name for name in before if before[name] != after[name])
    if set(changed) - ({"r0", "r3"} if not caller else {"r0", "r3", "r4", "r5", "r6"}):
        raise ValueError("Unexpected register clobber or failed stack restoration")
    return {"entry": hex(entry), "coordinate_bits": coordinate,
            "descriptor": list(descriptor), "delta_bits": delta, "index_bits": index,
            "record_address": hex(record_address), "output_hex": bytes(actual_record[20:28]).hex(),
            "instructions": cpu.steps, "pcs": [hex(pc) for pc in cpu.visited],
            "writes": [[hex(a), n] for a, n in memory.writes],
            "record_reads": memory.record_reads, "descriptor_reads": memory.descriptor_reads,
            "changed_registers": changed, "unaffected_bytes_equal": True,
            "return_sentinel_reached": True}


def execute(data, emu):
    selected = cases()
    if len(selected) != 180:
        raise ValueError("Case selection changed")
    rows = [run_case(data, emu, LEAF, *case) for case in selected]
    # The caller converts both scalar extents through signed halfword stack
    # slots, and truncates index*84 before adding the record base.
    indices = (0, 1, 127, 255, 780, 781, 0x7FFF, 0xFFFF, 0x10000, 0xFFFFFFFF)
    rows.extend(run_case(data, emu, CALLER, *case, index=index)
                for index in indices for case in selected)
    controls = {}
    for name, pc, replacement, original_op, entry in (
        ("subtract_to_add", LEAF + 2, "add", "sub", LEAF),
        ("missing_return_delay_store", LEAF + 24, "nop", "mov.w", LEAF),
        ("nonreturning_leaf", LEAF + 22, "loop", "rts", LEAF),
        ("caller_index_not_truncated", 0x0600A416, "nop", "extu.w", CALLER),
        ("caller_missing_vertical_store", 0x0600A43C, "nop", "mov.w", CALLER),
        ("caller_missing_register_restore", 0x0600A448, "nop", "mov.l", CALLER),
    ):
        offset = pc - pinned.BASE
        ins = emu.sh2.decode(int.from_bytes(data[offset:offset + 2], "big"), pc)
        if ins.op != original_op:
            raise ValueError("Original control instruction changed")
        if replacement == "add":
            word = 0x300C | (ins.n << 8) | (ins.m << 4)
        else:
            word = 0x0009 if replacement == "nop" else 0xAFFE
        altered = bytearray(data)
        altered[offset:offset + 2] = word.to_bytes(2, "big")
        rejected = 0
        reasons = set()
        control_cases = [(case, 0) for case in selected] if entry == LEAF else [
            (case, index) for index in (0, 781, 0xFFFF, 0x10000, 0xFFFFFFFF)
            for case in selected[::20]]
        for case, index in control_cases:
            try:
                run_case(bytes(altered), emu, entry, *case, index=index)
            except (ValueError, emu.MemoryError_) as error:
                rejected += 1
                reasons.add(str(error))
        if not rejected:
            raise ValueError("Original-instruction mutation survived")
        controls[name] = {"pc": hex(pc), "rejected": rejected,
                          "tested": len(control_cases), "reasons": sorted(reasons),
                          "mutated_kernel_sha256": pinned.digest(altered)}
    return {"cases": len(rows), "leaf_cases": len(selected), "caller_cases": len(indices) * len(selected),
            "results": rows, "results_sha256": pinned.digest(json.dumps(rows, sort_keys=True).encode()),
            "instruction_controls": controls,
            "instruction_ranges": {"leaf": [hex(LEAF), "0x600a3fa"],
                                   "caller": [hex(CALLER), "0x600a44a"]},
            "range_sha256": {"leaf": pinned.digest(data[LEAF-pinned.BASE:0x0600A3FA-pinned.BASE]),
                             "caller": pinned.digest(data[CALLER-pinned.BASE:0x0600A44A-pinned.BASE]),
                             "caller_literal": pinned.digest(data[0x44D4:0x44D8])}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.position-bounds-probe.v1", "experiment": EXPERIMENT,
              "status": "failure", "game": "USA MK-81070 V1.003",
              "kernel_sha256": pinned.KERNEL_SHA256, "interpreter_revision": pinned.INTERPRETER_REVISION,
              "interpreter_sources": pinned.SOURCE_HASHES,
              "probe_sha256": pinned.digest(Path(__file__).read_bytes()),
              "adapter_sha256": pinned.digest(Path(pinned.__file__).read_bytes()),
              "scope": "Original instructions; initialized controlled records/descriptor/stack; CPU-only",
              "limitations": ["No natural data, gameplay role, timing, independent CPU oracle or whole-program completion",
                              "Sampled register preservation only; function return value unspecified",
                              "Caller entry is a static boundary lead; executed with constructed ABI inputs"]}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print("FAIL: report requires a fresh writable path")
        return 1
    with os.fdopen(fd, "w") as output:
        phase = "source_identity"
        try:
            data = pinned.kernel_bytes(args.kernel)
            emu = pinned.interpreter(args.saturn_recomp)
            phase = "original_execution"
            report.update(execute(data, emu), status="success")
        except Exception as error:
            report["error"] = {"phase": phase, "type": type(error).__name__,
                               "reason": "Identity, bounded execution or memory contract failed"}
        output.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
