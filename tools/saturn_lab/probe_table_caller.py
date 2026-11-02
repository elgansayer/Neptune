#!/usr/bin/env python3
"""Execute an original caller prefix and both original table helpers, offline.

The stop at BAFA is before the rest of the caller, not a function return. Data
bytes and stack are constructed inputs. No private game bytes are bundled.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned

ENTRY, STOP = 0x0600BAC4, 0x0600BAFA
FIRST, SECOND = 0x0600B934, 0x0600B950
CATEGORY, SLOT = 0x060C029C, 0x060C029D
DATA_BASE, DATA_SIZE = CATEGORY - 12, 32
SP, STACK_SIZE = 0x060FFFF0, 64
STACK_BASE = SP - 48
REGISTERS = tuple(f"r{i}" for i in range(16)) + ("sr", "gbr", "vbr", "mach", "macl", "pr")
LIMIT = 64
EXPERIMENT = "EXP-SAT-CODE-PAIRED-CALLER-630"


def initial_registers(category, slot):
    result = {f"r{i}": 0xA5A50000 + i * 0x101 for i in range(16)}
    result.update(r15=SP, sr=0x3F3, gbr=0x13572468, vbr=0x24681350,
                  mach=0x2468ACE0, macl=0x13579BDF ^ (category << 8) ^ slot, pr=0xFACEB00C)
    return result


def expected_pcs(category):
    return (list(range(ENTRY, 0x0600BAE0, 2))
            + (list(range(0x0600BAE0, 0x0600BAE4, 2)) if category >= 9 else [])
            + list(range(0x0600BAE4, 0x0600BAEE, 2))
            + list(range(FIRST, SECOND, 2))
            + list(range(0x0600BAEE, STOP, 2))
            + list(range(SECOND, 0x0600B966, 2)))


def contract(category, slot):
    """Independent byte/stack contract, including the declared prefix stop."""
    if any(type(v) is not int or not 0 <= v <= 255 for v in (category, slot)):
        raise ValueError("Caller inputs must be unsigned bytes")
    row, column = (0, 0) if category >= 9 else (category, slot)
    index = row * 10 + column
    before = initial_registers(category, slot)
    after = dict(before)
    after.update(r0=0x060B30C4 + index * 16, r2=152, r3=row, r4=row, r5=column,
                 r6=0x060B30C4, r11=SLOT, r12=0, r13=CATEGORY,
                 r14=0x00207F74 + index * 152, r15=SP - 24, sr=before["sr"] & ~1,
                 pr=STOP)
    writes = [[SP - offset, 4, before[register]] for offset, register in
              ((4, "r14"), (8, "r13"), (12, "r12"), (16, "r11"), (20, "r10"), (24, "pr"))]
    if category >= 9:
        writes.extend([[CATEGORY, 1, 0], [SLOT, 1, 0]])
    writes.append([SP - 28, 4, before["macl"]])
    reads = [[CATEGORY, 1, category], [SLOT, 1, column], [CATEGORY, 1, row],
             [SLOT, 1, column], [CATEGORY, 1, row]]
    calls = [[FIRST, row, column, 0x0600BAEE, SP - 24, before["macl"]],
             [SECOND, row, column, STOP, SP - 24, before["macl"]]]
    return {"registers": after, "writes": writes, "data_reads": reads,
            "stack_reads": [[SP - 28, 4, before["macl"]]], "calls": calls,
            "pcs": expected_pcs(category), "stop": STOP, "effective_bytes": [row, column]}


def validate_observation(category, slot, observed):
    expected = contract(category, slot)
    for name in ("registers", "writes", "data_reads", "stack_reads", "calls", "pcs", "stop"):
        if observed.get(name) != expected[name]:
            raise ValueError(f"Caller prefix {name} mismatch at input ({category},{slot})")
    if observed.get("unaffected_bytes_equal") is not True:
        raise ValueError("Caller prefix changed an unaffected data/stack byte")
    return expected


class Experiment:
    def __init__(self, data, emu):
        if len(data) != pinned.SIZE:
            raise ValueError("Complete original kernel extent required")
        experiment = self

        class Memory(emu.Memory):
            def read(self, address, size):
                value = super().read(address, size)
                if DATA_BASE <= address < DATA_BASE + DATA_SIZE:
                    if (address, size) not in ((CATEGORY, 1), (SLOT, 1)):
                        raise ValueError("Unexpected controlled-data read")
                    experiment.data_reads.append([address, size, value])
                if STACK_BASE <= address < STACK_BASE + STACK_SIZE:
                    if (address, size) != (SP - 28, 4):
                        raise ValueError("Unexpected stack read before declared prefix stop")
                    experiment.stack_reads.append([address, size, value])
                return value

            def write(self, address, size, value):
                permitted = {(SP - n, 4) for n in range(4, 29, 4)} | {(CATEGORY, 1), (SLOT, 1)}
                if (address, size) not in permitted:
                    raise ValueError("Write outside declared controlled-data and stack slots")
                experiment.writes.append([address, size, value & ((1 << (size * 8)) - 1)])
                return super().write(address, size, value)

        class CPU(emu.CPU):
            def exec(self, instruction, pc, in_slot=False):
                if len(experiment.pcs) >= LIMIT:
                    raise ValueError("Original prefix exceeded instruction budget")
                if not (ENTRY <= pc < STOP or FIRST <= pc < 0x0600B966):
                    raise ValueError("Execution escaped declared original prefix/helpers")
                if pc in (FIRST, SECOND):
                    experiment.calls.append([pc, self.r[4], self.r[5], self.pr, self.r[15], self.macl])
                experiment.pcs.append(pc)
                return super().exec(instruction, pc, in_slot=in_slot)

        self.memory, self.cpu_type = Memory(), CPU
        # Carve the writable controlled data out, with no overlapping regions.
        left = DATA_BASE - pinned.BASE
        self.left = self.memory.add(pinned.BASE, left, data[:left])
        right = left + DATA_SIZE
        self.right = self.memory.add(DATA_BASE + DATA_SIZE, len(data) - right, data[right:])
        self.original_left, self.original_right = bytes(self.left), bytes(self.right)
        self.data = self.memory.add(DATA_BASE, DATA_SIZE)
        self.stack = self.memory.add(STACK_BASE, STACK_SIZE)

    def run(self, category, slot):
        expected = contract(category, slot)
        self.data_reads, self.stack_reads, self.writes, self.pcs, self.calls = [], [], [], [], []
        data_before = bytearray((n * 17 + 31) & 255 for n in range(DATA_SIZE))
        data_before[CATEGORY - DATA_BASE] = category
        data_before[SLOT - DATA_BASE] = slot
        stack_before = bytes((n * 37 + category + slot) & 255 for n in range(STACK_SIZE))
        self.data[:] = data_before
        self.stack[:] = stack_before
        cpu = self.cpu_type(self.memory)
        before = initial_registers(category, slot)
        cpu.r = [before[f"r{i}"] for i in range(16)]
        for name in REGISTERS[16:]:
            setattr(cpu, name, before[name])
        cpu.pc = ENTRY
        while cpu.pc != STOP:
            cpu.step()
            if cpu.steps > LIMIT:
                raise ValueError("Original prefix failed to reach its declared stop")
        after = {**{f"r{i}": value for i, value in enumerate(cpu.r)},
                 **{name: getattr(cpu, name) for name in REGISTERS[16:]}}
        expected_data, expected_stack = bytearray(data_before), bytearray(stack_before)
        for address, size, value in expected["writes"]:
            target, base = (expected_data, DATA_BASE) if address < STACK_BASE else (expected_stack, STACK_BASE)
            target[address - base:address - base + size] = value.to_bytes(size, "big")
        observed = {"registers": after, "writes": self.writes, "data_reads": self.data_reads,
                    "stack_reads": self.stack_reads, "calls": self.calls, "pcs": self.pcs,
                    "stop": cpu.pc, "unaffected_bytes_equal":
                    self.data == expected_data and self.stack == expected_stack}
        validate_observation(category, slot, observed)
        if cpu.steps != len(self.pcs):
            raise ValueError("Delay-slot instruction coverage disagreement")
        return observed

    def immutable_code(self):
        if bytes(self.left) != self.original_left or bytes(self.right) != self.original_right:
            raise ValueError("Original code/literals or unrelated mapped kernel data changed")


def execute(data, emu):
    experiment = Experiment(data, emu)
    results, inputs, paths, samples = hashlib.sha256(), hashlib.sha256(), Counter(), []
    instructions, cases, resets = 0, 0, 0
    for category in range(256):
        for slot in range(256):
            observed = experiment.run(category, slot)
            results.update(json.dumps([category, slot, observed], sort_keys=True, separators=(",", ":")).encode())
            inputs.update(bytes((category, slot)))
            count = len(observed["pcs"])
            paths[count] += 1
            instructions += count
            cases += 1
            resets += category >= 9
            if category in (0, 8, 9, 128, 255) and slot in (0, 9, 255):
                samples.append({"category": category, "slot": slot,
                                "first_pointer": observed["registers"]["r14"],
                                "second_pointer": observed["registers"]["r0"],
                                "instructions": count})
    experiment.immutable_code()
    if cases != 65536 or resets != 63232 or dict(paths) != {50: 2304, 52: 63232}:
        raise ValueError("Incomplete unsigned-byte caller coverage")
    return {"cases": cases, "reset_cases": resets, "instruction_total": instructions,
            "path_counts": dict(paths), "input_pairs_sha256": inputs.hexdigest(),
            "observations_sha256": results.hexdigest(), "samples": samples,
            "original_code_and_unaffected_data_equal": True,
            "natural_observation_consistency": {"prior_issue": 597, "prior_frame": 34213,
                "prior_arguments": [0, 0], "prior_return_context": "0x0600baee",
                "prior_first_pointer": "0x00207f74", "new_natural_capture": False}}


def instruction_controls(data, emu):
    changes = (("threshold_10", 0x0600BAC6, 0xE20A, 9, 255),
               ("reversed_reset_branch", 0x0600BADC, 0x8D02, 8, 255),
               ("missing_slot_reset", 0x0600BAE2, 0x0009, 9, 255),
               ("changed_first_argument_delay", 0x0600BAEC, 0xE401, 0, 0),
               ("changed_second_base", 0x0600B98A, 0x30C8, 8, 255))
    result = []
    for name, address, word, category, slot in changes:
        changed = bytearray(data)
        offset = address - pinned.BASE
        changed[offset:offset + 2] = word.to_bytes(2, "big")
        if bytes(changed) == data:
            raise ValueError("Ineffective original-copy control")
        try:
            Experiment(bytes(changed), emu).run(category, slot)
        except ValueError as error:
            if not str(error).startswith("Caller prefix "):
                raise ValueError("Control did not reach a terminal semantic comparison: " + name) from error
            result.append({"name": name, "address": hex(address), "rejected": True,
                           "altered_sha256": pinned.digest(changed), "reason": str(error)})
        else:
            raise ValueError("Original-copy semantic control survived: " + name)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.table-caller-prefix.v1", "status": "failure",
              "experiment": EXPERIMENT, "entry": hex(ENTRY), "prefix_stop": hex(STOP),
              "kernel_sha256": pinned.KERNEL_SHA256, "interpreter_revision": pinned.INTERPRETER_REVISION,
              "interpreter_sources": pinned.SOURCE_HASHES, "probe_sha256": pinned.digest(Path(__file__).read_bytes()),
              "scope": "all constructed byte inputs; original prefix and two complete helpers; no caller return",
              "limitations": ["No new natural-game capture or table dereference", "No established table/gameplay meaning",
                              "No campaign/battle, timing, hardware or Godot parity proof",
                              "Constructed writable data/stack; shared interpreter lineage", "Not whole-program recovery"]}
    with args.report.open("x", encoding="utf-8") as output:
        try:
            data = pinned.kernel_bytes(args.kernel)
            emu = pinned.interpreter(args.saturn_recomp)
            result = execute(data, emu)
            controls = instruction_controls(data, emu)
            report.update(status="success", **result, instruction_controls=controls)
        except Exception as error:
            report["error"] = f"{type(error).__name__}: {error}"
        output.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
