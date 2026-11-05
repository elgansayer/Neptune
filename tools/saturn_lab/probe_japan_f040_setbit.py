#!/usr/bin/env python3
"""Recover the Japan KRNL F040 helper set-bit contract across its call train.

The accepted caller-derived probe (`probe_japan_095c24_caller_derived.py`)
measured one longword read and written through R2 with bit 31 set, but it
sampled a single F040 caller state, in which R4 held 0x1F. The F040 call train
visits the same helper repeatedly while R4 decreases by two and R5 advances
through powers of four, so "bit 31" may be an artefact of that one sample.

This probe runs the original F040 path from the captured frame-1200 WorkRAM,
observes the helper's effect at every call, repeats the run with a constructed
pre-word at the observed result address, and mechanically discriminates
candidate bit-index rules over both the helper entry and its inner visit.

Bounded CPU-only diagnostic: no gameplay, timing, device, audio or
whole-program claim is made or implied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg

BASE = 0x06000000
KERNEL_BASE = 0x0600A000
RAM_SIZE = 0x100000
ENTRY = 0x0600F040
HELPER_ENTRY = 0x06095C24
HELPER_INNER = 0x06095C60
HELPER_END = 0x06095C8C
TASK_CURSOR = 0x060BCC80
STACK = 0x06002000
STACK_LO, STACK_HI = 0x06001EE4, 0x06001F30
DATA_SLICE_LO, DATA_SLICE_HI = 0x060FC500, 0x060FC700
DATA_SLICE_SHA256 = "4d43fa36164881d49f7a766f9d71cb116edc4a02086e984171cffa9b4b6258e2"
HELPER_ENTRY_SP = 0x06001F24
CONSTRUCTED_WORD = 0x00000000
SEEDS = (0, 1)
DEFAULT_INSTRUCTION_LIMIT = 1024
ALLOWED_INSTRUCTION_LIMITS = (1024, 2048, 4096, 8192)
KERNEL_SHA256 = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA256 = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
WORKRAM_SHA256 = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
CORE_SHA256 = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


class InstructionBudget(Exception):
    """Raised when the declared instruction bound is reached."""


def changed_bits(before: int, after: int) -> list[int]:
    """Bit indexes set in `after` and clear in `before`."""
    difference = after & ~before & 0xFFFFFFFF
    return [index for index in range(32) if difference & (1 << index)]


RULES = {
    "constant_bit31": lambda observation: 31,
    "r4_entry_low5": lambda observation: observation["r4_entry"] & 0x1F,
    "r4_inner_low5": lambda observation: observation["r4_inner"] & 0x1F,
    "r5_entry_low5": lambda observation: observation["r5_entry"] & 0x1F,
    "r5_inner_low5": lambda observation: observation["r5_inner"] & 0x1F,
    "r4_entry_low4": lambda observation: observation["r4_entry"] & 0x0F,
    "r4_inner_low4": lambda observation: observation["r4_inner"] & 0x0F,
    "r4_entry_plus_1_low5": lambda observation: (observation["r4_entry"] + 1) & 0x1F,
    "r4_inner_plus_1_low5": lambda observation: (observation["r4_inner"] + 1) & 0x1F,
    "r4_inner_minus_r5_inner_low5": lambda observation: (
        observation["r4_inner"] - observation["r5_inner"]) & 0x1F,
}


def evaluate_rules(observations: list[dict], rules: dict = RULES) -> dict:
    """Report which bit-index rules fit every observed helper effect.

    An observation with no changed bit cannot discriminate a rule and is
    counted separately instead of being counted as agreement.
    """
    results = {}
    for name, rule in rules.items():
        mismatches = []
        checked = 0
        for observation in observations:
            bits = observation["set_bits"]
            if not bits:
                continue
            checked += 1
            expected = rule(observation)
            if bits != [expected]:
                mismatches.append({"call_index": observation["call_index"],
                                   "expected_bit": expected,
                                   "observed_bits": bits})
        results[name] = {"checked": checked, "consistent": bool(checked) and not mismatches,
                         "mismatches": mismatches}
    return results


def word_changes(pre_image: bytes, work: bytearray, addresses: set[int]) -> list[dict]:
    """Changed 4-byte words among the addresses written since `pre_image`."""
    changes = []
    for address in sorted(addresses):
        offset = address - BASE
        before = int.from_bytes(pre_image[offset:offset + 4], "big")
        after = int.from_bytes(work[offset:offset + 4], "big")
        if before != after:
            changes.append({"address": hex32(address), "before": hex32(before),
                            "after": hex32(after), "set_bits": changed_bits(before, after)})
    return changes


def classify_changes(changes: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split changed words into stack spill/restore traffic and data changes."""
    stack = []
    data = []
    for change in changes:
        address = int(change["address"], 16)
        (stack if STACK_LO <= address < STACK_HI else data).append(change)
    return stack, data


def series_checks(observations: list[dict]) -> dict:
    """Register progressions across the observed helper calls."""
    r4_entry = [observation["r4_entry"] for observation in observations]
    r4_inner = [observation["r4_inner"] for observation in observations]
    r5_entry = [observation["r5_entry"] for observation in observations]
    r5_inner = [observation["r5_inner"] for observation in observations]
    return {
        "helper_call_count": len(observations),
        "r4_entry_series": [hex32(value) for value in r4_entry[:8]],
        "r4_inner_series": [hex32(value) for value in r4_inner[:8]],
        "r5_entry_series": [hex32(value) for value in r5_entry[:8]],
        "r5_inner_series": [hex32(value) for value in r5_inner[:8]],
        "r4_inner_decreases_by_two": all(b == a - 2 for a, b in zip(r4_inner, r4_inner[1:])),
        "r5_entry_advances_by_four": all(b == a * 4 for a, b in zip(r5_entry, r5_entry[1:])),
        "r5_inner_advances_by_four": all(b == a * 4 for a, b in zip(r5_inner, r5_inner[1:])),
        "first_r4_inner_is_0x1f": bool(r4_inner) and r4_inner[0] == 0x1F,
    }


def execute(kernel: bytes, ram: bytes, emu, seed: int, instruction_limit: int,
            construct: dict | None = None) -> dict:
    """Run the original F040 path and observe every helper call.

    `construct` maps a helper call index to the address whose word is replaced
    with `CONSTRUCTED_WORD` immediately before that call, so that a repeated
    idempotent store becomes observable.
    """
    work = bytearray(ram)
    reads: list[list[int]] = []
    writes: list[list[int]] = []
    pcs: list[int] = []
    helper_calls: list[dict] = []
    constructed_writes: list[dict] = []
    state = {"in_helper": False, "pre_image": None, "entry": None,
             "call_index": 0, "write_start": 0}

    class Memory(emu.Memory):
        fetching = False

        def read(self, address, width):
            if self.fetching:
                offset = address - KERNEL_BASE
                if width != 2 or not 0 <= offset <= len(kernel) - width:
                    raise ValueError(f"original code fetch fence {address:08x}/{width}")
                if work[address - BASE:address - BASE + width] != kernel[offset:offset + width]:
                    raise ValueError(f"captured code differs from original at {address:08x}")
            value = super().read(address, width)
            reads.append([address, width, value])
            return value

        def write(self, address, width, value):
            if width not in (1, 2, 4) or address < BASE or address + width > BASE + RAM_SIZE:
                raise ValueError(f"WorkRAM write fence {address:08x}/{width}")
            value &= (1 << (width * 8)) - 1
            writes.append([address, width, value])
            return super().write(address, width, value)

    memory = Memory()
    mapped = memory.add(BASE, len(work), work)

    def open_helper(cpu) -> None:
        call_index = state["call_index"]
        state["call_index"] += 1
        registers = list(cpu.r)
        state["in_helper"] = True
        state["write_start"] = len(writes)
        state["entry"] = {
            "call_index": call_index,
            "steps": cpu.steps,
            "registers": [hex32(value) for value in registers],
            "r2_entry": registers[2],
            "r4_entry": registers[4],
            "r5_entry": registers[5],
            "sp_entry": registers[15],
            "r4_inner": registers[4],
            "r5_inner": registers[5],
            "inner_seen": False,
        }
        if construct is not None:
            address = construct.get(call_index)
            if address is not None:
                offset = address - BASE
                if offset < 0 or offset + 4 > len(mapped) or address % 4:
                    raise ValueError(f"constructed address outside captured WorkRAM: {address:08x}")
                mapped[offset:offset + 4] = CONSTRUCTED_WORD.to_bytes(4, "big")
                constructed_writes.append({"call_index": call_index,
                                           "address": hex32(address),
                                           "word": hex32(CONSTRUCTED_WORD)})
        state["pre_image"] = bytes(mapped)

    def close_helper() -> None:
        entry = state["entry"]
        pre_image = state["pre_image"]
        state["in_helper"] = False
        window = writes[state["write_start"]:]
        addresses = {address & ~3 for address, _width, _value in window}
        changes = word_changes(pre_image, mapped, addresses)
        stack_changes, data_changes = classify_changes(changes)
        data_writes = sorted({address & ~3 for address, _width, _value in window
                              if not STACK_LO <= address < STACK_HI})
        result_address = data_writes[0] if len(data_writes) == 1 else None
        set_bits = []
        if result_address is not None:
            offset = result_address - BASE
            before = int.from_bytes(pre_image[offset:offset + 4], "big")
            after = int.from_bytes(mapped[offset:offset + 4], "big")
            set_bits = changed_bits(before, after)
        observation = dict(entry)
        observation.update({
            "writes": [[hex32(address), width, hex32(value)]
                       for address, width, value in window],
            "stack_changes": stack_changes,
            "data_changes": data_changes,
            "data_write_addresses": [hex32(address) for address in data_writes],
            "result_address": None if result_address is None else hex32(result_address),
            "set_bits": set_bits,
        })
        helper_calls.append(observation)

    class CPU(emu.CPU):
        def fetch(self, pc):
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= instruction_limit:
                raise InstructionBudget()
            pcs.append(pc)
            if pc == HELPER_ENTRY:
                open_helper(self)
            elif state["in_helper"]:
                if pc == HELPER_INNER and not state["entry"]["inner_seen"]:
                    state["entry"]["inner_seen"] = True
                    state["entry"]["r4_inner"] = self.r[4]
                    state["entry"]["r5_inner"] = self.r[5]
                    state["entry"]["sp_inner"] = self.r[15]
                elif not HELPER_ENTRY <= pc < HELPER_END:
                    close_helper()
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0x61000000 + i * 0x0103070B + seed * 0x11111111) & 0xFFFFFFFF
             for i in range(16)]
    cpu.r[11] = TASK_CURSOR
    cpu.r[15] = STACK
    cpu.r[4] = int.from_bytes(work[TASK_CURSOR - BASE:TASK_CURSOR - BASE + 4], "big")
    cpu.vbr, cpu.sr = 0x06000000, 0xF0
    cpu.pr, cpu.pc = emu.RETURN_SENTINEL, ENTRY

    try:
        while cpu.pc != emu.RETURN_SENTINEL:
            cpu.step()
        stop = {"kind": "return_sentinel", "pc": hex32(cpu.pc)}
    except InstructionBudget:
        stop = {"kind": "instruction_budget", "pc": hex32(cpu.pc), "steps": cpu.steps}

    return {"seed": seed, "stop": stop, "steps": cpu.steps,
            "instruction_limit": instruction_limit,
            "constructed": construct is not None,
            "constructed_writes": constructed_writes,
            "helper_calls": helper_calls,
            "series": series_checks(helper_calls),
            "pcs": [hex32(pc) for pc in pcs],
            "reads": reads,
            "writes": writes,
            "final_registers": [hex32(value) for value in cpu.r],
            "pr": hex32(cpu.pr), "sr": hex32(cpu.sr), "vbr": hex32(cpu.vbr)}


def result_addresses(run: dict) -> dict:
    """Map each helper call index to its observed result address."""
    addresses = {}
    for observation in run["helper_calls"]:
        address = observation["result_address"]
        if address is not None:
            addresses[observation["call_index"]] = int(address, 16)
    return addresses


OWNED_POINTER = 0x060FC5A0
OWNED_LITERAL_BASE = 0x0600F068
OWNED_CALLER = (
    0xD309,        # mov.l @T,r3  -> helper entry
    0xD20A,        # mov.l @T,r2  -> owned work pointer
    0xD70B,        # mov.l @T,r7  -> owned helper return address
    0xE604,        # mov #4,r6    (call counter)
    0xE41F,        # mov #0x1f,r4 (bit index)
    0xE501,        # mov #1,r5
    0x432B,        # jmp @r3      (owned dispatch to the helper)
    0x0009,        # nop (delay slot)
    0x355C,        # add r5,r5
    0x355C,        # add r5,r5    (r5 *= 4)
    0x74FE,        # add #-2,r4
    0x76FF,        # add #-1,r6
    0xE000,        # mov #0,r0
    0x3060,        # cmp/eq r6,r0
    0x8FF6,        # bf/s back to the owned dispatch
    0x0009,        # nop (delay slot)
    0x000B,        # rts
    0x0009,        # nop (delay slot)
)
OWNED_HELPER = (0xA01C, 0x0009)      # bra to the inner visit, nop delay slot
OWNED_HELPER_INNER = (
    0x6843,        # mov r4,r8
    0xE91F,        # mov #31,r9
    0x2899,        # and r9,r8
    0xE001,        # mov #1,r0
    0x300C,        # add r0,r0   (loop)
    0x78FF,        # add #-1,r8
    0xE900,        # mov #0,r9
    0x3980,        # cmp/eq r8,r9
    0x8FFA,        # bf/s loop
    0x0009,        # nop (delay slot)
    0x2202,        # mov.l r0,@r2
    0x472B,        # jmp @r7     (owned return)
    0x0009,        # nop (delay slot)
)
OWNED_EXPECTED_BITS = ([31], [29], [27], [25])


def owned_program() -> tuple[bytes, bytes]:
    """An owned synthetic caller and helper; never original game code.

    The owned caller dispatches to the owned helper four times while R4
    decreases by two and R5 advances by four, and the owned helper stores
    `1 << (R4 & 31)` at the owned pointer. The harness must observe exactly
    that, which exercises the helper window, the result store identification,
    the changed-bit arithmetic and the rule discrimination.
    """
    kernel = bytearray(786432)

    def put(address: int, words) -> None:
        for index, word in enumerate(words):
            offset = address - KERNEL_BASE + index * 2
            kernel[offset:offset + 2] = word.to_bytes(2, "big")

    def literal(address: int, value: int) -> None:
        offset = address - KERNEL_BASE
        kernel[offset:offset + 4] = value.to_bytes(4, "big")

    put(ENTRY, OWNED_CALLER)
    put(HELPER_ENTRY, OWNED_HELPER)
    put(HELPER_INNER, OWNED_HELPER_INNER)
    literal(OWNED_LITERAL_BASE, HELPER_ENTRY)
    literal(OWNED_LITERAL_BASE + 4, OWNED_POINTER)
    literal(OWNED_LITERAL_BASE + 12, ENTRY + 0x10)
    ram = bytearray(RAM_SIZE)
    ram[KERNEL_BASE - BASE:KERNEL_BASE - BASE + len(kernel)] = kernel
    return bytes(kernel), bytes(ram)


def owned_smoke(emu) -> dict:
    """Exercise the harness with the actual pinned CPU on owned instructions."""
    kernel, ram = owned_program()
    run = execute(kernel, ram, emu, 0, 4096)
    calls = run["helper_calls"]
    if run["stop"]["kind"] != "return_sentinel":
        raise ValueError("Owned harness run did not return")
    if len(calls) != len(OWNED_EXPECTED_BITS):
        raise ValueError("Owned harness observed the wrong number of helper calls")
    if [call["set_bits"] for call in calls] != list(OWNED_EXPECTED_BITS):
        raise ValueError("Owned harness observed the wrong changed bits")
    if [call["result_address"] for call in calls] != [hex32(OWNED_POINTER)] * len(calls):
        raise ValueError("Owned harness identified the wrong result store")
    if [call["r4_entry"] for call in calls] != [0x1F, 0x1D, 0x1B, 0x19]:
        raise ValueError("Owned harness observed the wrong R4 progression")
    if [call["r5_entry"] for call in calls] != [1, 4, 0x10, 0x40]:
        raise ValueError("Owned harness observed the wrong R5 progression")
    results = evaluate_rules(calls)
    if not results["r4_entry_low5"]["consistent"] or results["constant_bit31"]["consistent"]:
        raise ValueError("Owned harness did not discriminate the bit-index rules")
    constructed = execute(kernel, ram, emu, 0, 4096,
                          construct={index: OWNED_POINTER
                                     for index in range(len(OWNED_EXPECTED_BITS))})
    if [call["set_bits"] for call in constructed["helper_calls"]] != list(OWNED_EXPECTED_BITS):
        raise ValueError("Owned constructed run did not repeat the observed bits")
    controls = {}
    altered = bytearray(kernel)
    altered[HELPER_ENTRY - KERNEL_BASE] ^= 0x01
    try:
        execute(bytes(altered), ram, emu, 0, 4096)
    except ValueError as error:
        controls["source_mismatch"] = {"rejected": True, "reason": str(error)}
    else:
        raise ValueError("Owned harness accepted altered source bytes")
    try:
        execute(kernel, ram, emu, 0, 4096, construct={0: BASE + RAM_SIZE})
    except ValueError as error:
        controls["constructed_address_outside_workram"] = {"rejected": True,
                                                           "reason": str(error)}
    else:
        raise ValueError("Owned harness accepted a constructed address outside WorkRAM")
    bounded = execute(kernel, ram, emu, 0, 64)
    if bounded["stop"]["kind"] != "instruction_budget":
        raise ValueError("Owned harness did not stop at the instruction budget")
    controls["instruction_budget"] = {"kind": bounded["stop"]["kind"],
                                      "steps": bounded["steps"]}
    return {"original_game_bytes_executed": False,
            "helper_calls_observed": len(calls),
            "observed_bits": [call["set_bits"] for call in calls],
            "result_address": hex32(OWNED_POINTER),
            "r4_entry_series": [hex32(call["r4_entry"]) for call in calls],
            "r5_entry_series": [hex32(call["r5_entry"]) for call in calls],
            "r4_rule_consistent": results["r4_entry_low5"]["consistent"],
            "constant_bit31_rejected": not results["constant_bit31"]["consistent"],
            "constructed_run_matches": True,
            "failure_controls": controls}


def anchors(ram: bytes, observed: list[dict]) -> dict:
    """Check the regenerated caller state against the accepted evidence.

    Only the facts pinned by an accepted artifact are hard requirements: the
    caller data slice hash and the helper entry stack pointer. The register
    progressions recorded in the accepted note are reported for comparison
    without deciding the run, because the note does not say whether it saw
    them at the helper entry or at the inner visit.
    """
    slice_bytes = bytes(ram[DATA_SLICE_LO - BASE:DATA_SLICE_HI - BASE])
    first = observed[0]
    checks = series_checks(first["helper_calls"])
    entry_sp = first["helper_calls"][0]["sp_entry"] if first["helper_calls"] else None
    anchor = {
        "data_slice_sha256": sha(slice_bytes),
        "data_slice_matches_accepted": sha(slice_bytes) == DATA_SLICE_SHA256,
        "helper_entry_sp": None if entry_sp is None else hex32(entry_sp),
        "helper_entry_sp_matches_accepted": entry_sp == HELPER_ENTRY_SP,
        "helper_call_count": checks["helper_call_count"],
        "r4_inner_decreases_by_two": checks["r4_inner_decreases_by_two"],
        "r5_advances_by_four": checks["r5_entry_advances_by_four"] or
                               checks["r5_inner_advances_by_four"],
        "first_r4_inner_is_0x1f": checks["first_r4_inner_is_0x1f"],
        "r4_entry_series": checks["r4_entry_series"],
        "r4_inner_series": checks["r4_inner_series"],
        "r5_entry_series": checks["r5_entry_series"],
        "r5_inner_series": checks["r5_inner_series"],
    }
    anchor["failures"] = [name for name, value in anchor.items()
                          if name.endswith("_matches_accepted") and not value]
    return anchor


def pair_comparison(runs: list[dict]) -> dict:
    """Compare the two constructed seeds the way the accepted diagnostics do."""
    if len(runs) != 2:
        return {"compared": False}
    first, second = runs
    return {
        "compared": True,
        "pc_traces_identical": first["pcs"] == second["pcs"],
        "read_traces_identical": first["reads"] == second["reads"],
        "write_address_width_shapes_identical":
            [(row[0], row[1]) for row in first["writes"]] ==
            [(row[0], row[1]) for row in second["writes"]],
        "helper_call_counts": [len(first["helper_calls"]), len(second["helper_calls"])],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--saturn-recomp", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--instruction-limit", type=int, choices=ALLOWED_INSTRUCTION_LIMITS,
                        default=DEFAULT_INSTRUCTION_LIMIT)
    args = parser.parse_args(argv)

    report = {"schema": "neptune.original-japan-f040-setbit.v1", "status": "failure"}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        print(f"FAIL: fresh private report path required: {error}")
        return 1

    with os.fdopen(fd, "w", encoding="utf-8") as output:
        try:
            kernel = pinned.read_bounded(args.kernel, 786432)
            state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
            metadata = json.loads(args.checkpoint.read_text())
            if sha(kernel) != KERNEL_SHA256:
                raise ValueError("Japan original kernel identity differs")
            if (sha(state) != STATE_SHA256 or metadata.get("frame") != 1200 or
                    metadata.get("state_sha256") != STATE_SHA256 or
                    metadata.get("identity", {}).get("core_sha256") != CORE_SHA256):
                raise ValueError("frame-1200 state/checkpoint/core identity differs")
            ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", RAM_SIZE), "little")
            if sha(ram) != WORKRAM_SHA256:
                raise ValueError("normalized captured WorkRAM-H identity differs")

            emu = pinned.interpreter(args.saturn_recomp)
            report.update(
                release="Japan T-14302G V1.000", module="KRNL",
                cpu="SH-2", entry=hex32(ENTRY), helper_entry=hex32(HELPER_ENTRY),
                helper_inner=hex32(HELPER_INNER), helper_end=hex32(HELPER_END),
                kernel_sha256=KERNEL_SHA256, state_sha256=STATE_SHA256,
                normalized_workram_sha256=WORKRAM_SHA256,
                interpreter_revision=pinned.INTERPRETER_REVISION,
                interpreter_sources=pinned.SOURCE_HASHES,
                probe_sha256=sha(Path(__file__).read_bytes()),
                instruction_limit=args.instruction_limit,
                constructed_word=hex32(CONSTRUCTED_WORD))
            observed = [execute(kernel, ram, emu, seed, args.instruction_limit)
                        for seed in SEEDS]
            report["observed_runs"] = observed
            anchor = anchors(ram, observed)
            report["anchors"] = anchor
            if anchor["failures"]:
                raise ValueError("caller state differs from the accepted evidence: " +
                                 ", ".join(anchor["failures"]))
            constructed = []
            for run in observed:
                addresses = result_addresses(run)
                if not addresses:
                    raise ValueError("no unique helper result address was observed")
                constructed.append(execute(kernel, ram, emu, run["seed"],
                                           args.instruction_limit, construct=addresses))
                report["constructed_runs"] = constructed

            observed_calls = [call for run in observed for call in run["helper_calls"]]
            constructed_calls = [call for run in constructed for call in run["helper_calls"]]
            report.update(
                status="success",
                cpu="SH-2", entry=hex32(ENTRY), helper_entry=hex32(HELPER_ENTRY),
                helper_inner=hex32(HELPER_INNER), helper_end=hex32(HELPER_END),
                kernel_sha256=KERNEL_SHA256, state_sha256=STATE_SHA256,
                normalized_workram_sha256=WORKRAM_SHA256,
                interpreter_revision=pinned.INTERPRETER_REVISION,
                interpreter_sources=pinned.SOURCE_HASHES,
                probe_sha256=sha(Path(__file__).read_bytes()),
                instruction_limit=args.instruction_limit,
                constructed_word=hex32(CONSTRUCTED_WORD),
                contract=("Executes the original F040 path from the captured frame-1200 WorkRAM "
                    "and observes every call to the original 0x06095C24 helper. Each call records "
                    "the helper's changed words, separating stack spill/restore traffic from the "
                    "single data word the helper stores. A second run replaces that word with a "
                    "constructed value before each call so a repeated store stays observable. "
                    "Candidate bit-index rules are then discriminated mechanically."),
                limitations=["Direct F040 entry with constructed GPR seeds; the natural 0x0600A20E "
                             "caller state is unresolved",
                             "Constructed pre-word changes captured data; it is an experiment, not "
                             "the natural captured execution",
                             "Bounded instruction budget; the F040/F134 path is not completed",
                             "No independent emulator, hardware timing, device, gameplay, audio or "
                             "whole-program claim",
                             "The accepted caller-derived report was produced by a private probe "
                             "variant that is not in this repository, so only its data slice hash "
                             "and register facts are anchored here"],
                pair_comparison={
                    "observed": pair_comparison(observed),
                    "constructed": pair_comparison(constructed),
                },
                hypothesis_results={
                    "observed": evaluate_rules(observed_calls),
                    "constructed": evaluate_rules(constructed_calls),
                })
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        output.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.report),
                      "helper_calls": report.get("anchors", {}).get("helper_call_count")}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
