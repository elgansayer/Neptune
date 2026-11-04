#!/usr/bin/env python3
"""Execute original Japan AB30's 18-row count normalization loop."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg

BASE, SIZE = 0x0600A000, 786432
WRAM, WRAM_SIZE = 0x06000000, 0x100000
ENTRY, END = 0x0600AB30, 0x0600AB78
TABLE, ROW_SIZE, ROWS = 0x060BCEEC, 88, 18
TABLE_SIZE = ROW_SIZE * ROWS
CURRENT_ALIAS, CURRENT_PHYS = 0x2600A038, 0x0600A038
PREVIOUS = 0x060BDDAC
SP, LIMIT = 0x06002000, 512
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
RAM_SHA = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
CORE_SHA = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
LITERALS = {0x0600AD7C: (4, CURRENT_ALIAS), 0x0600AD80: (4, PREVIOUS),
            0x0600AD84: (4, TABLE)}
SEEDS = (0, 1)
CASES = {
    "equal_counter_no_table_access": {"current": 10, "previous": 10,
        "rows": {0: (1, 8), 1: (1, 1), 17: (0, 0xDEADBEEF)}},
    "subtract_and_floor": {"current": 13, "previous": 10,
        "rows": {0: (1, 8), 1: (1, 3), 2: (1, 2), 3: (0, 9), 17: (1, 0)}},
    "unsigned_wrap_delta": {"current": 2, "previous": 0xFFFFFFFF,
        "rows": {0: (1, 10), 1: (1, 3), 2: (1, 0xFFFFFFFD), 3: (0, 99)}},
    "high_bit_delta": {"current": 0x80000005, "previous": 5,
        "rows": {0: (1, 0xFFFFFFFF), 1: (1, 0x7FFFFFFF), 2: (0, 0x80000001)}},
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def initial_table(case):
    table = bytearray(TABLE_SIZE)
    for row, (active, value) in case["rows"].items():
        start = row * ROW_SIZE
        table[start:start+4] = (value & 0xFFFFFFFF).to_bytes(4, "big")
        table[start+80] = active
    return bytes(table)


def expected_table(before: bytes, current: int, previous: int) -> bytes:
    after = bytearray(before)
    delta = (current - previous) & 0xFFFFFFFF
    if delta == 0:
        return bytes(after)
    for row in range(ROWS):
        start = row * ROW_SIZE
        if after[start+80] == 0:
            continue
        value = int.from_bytes(after[start:start+4], "big")
        if value <= 1:
            continue
        new = value - delta if value > delta else 1
        after[start:start+4] = (new & 0xFFFFFFFF).to_bytes(4, "big")
    return bytes(after)


def execute(kernel, ram, emu, case_name, seed, mutate=False):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA or len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("original Japan kernel or frame-1200 WorkRAM-H identity differs")
    if case_name not in CASES or seed not in SEEDS:
        raise ValueError("case or seed outside declared corpus")
    if ram[ENTRY-WRAM:END-WRAM] != kernel[ENTRY-BASE:END-BASE]:
        raise ValueError("captured AB30 code differs from original source bytes")

    case = CASES[case_name]
    before = initial_table(case)
    expected = expected_table(before, case["current"], case["previous"])
    work = bytearray(ram)
    work[TABLE-WRAM:TABLE-WRAM+TABLE_SIZE] = before
    work[CURRENT_PHYS-WRAM:CURRENT_PHYS-WRAM+4] = (case["current"] & 0xFFFFFFFF).to_bytes(4, "big")
    work[PREVIOUS-WRAM:PREVIOUS-WRAM+4] = (case["previous"] & 0xFFFFFFFF).to_bytes(4, "big")
    if mutate:
        work[0x0600AB5C-WRAM:0x0600AB5E-WRAM] = (0x8903).to_bytes(2, "big")

    reads, writes, pcs = [], [], []

    class Memory(emu.Memory):
        def read(self, address, width):
            if self.fetching:
                if width != 2 or not ENTRY <= address < END or address & 1:
                    raise ValueError(f"AB30 PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address == CURRENT_ALIAS and width == 4:
                value = super().read(CURRENT_PHYS, width)
                reads.append(["current_alias", address, width, value])
                return value
            if address in LITERALS and LITERALS[address][0] == width:
                value = super().read(address, width)
                reads.append(["literal", address, width, value])
                return value
            if address == PREVIOUS and width == 4:
                value = super().read(address, width)
                reads.append(["previous", address, width, value])
                return value
            if TABLE <= address and address + width <= TABLE + TABLE_SIZE and width in (1, 4):
                value = super().read(address, width)
                reads.append(["table", address, width, value])
                return value
            if SP - 8 <= address and address + width <= SP and width == 4:
                value = super().read(address, width)
                reads.append(["stack", address, width, value])
                return value
            raise ValueError(f"unexpected AB30 read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            if address == CURRENT_ALIAS and width == 4:
                writes.append(["current_alias", address, width, value])
                return super().write(CURRENT_PHYS, width, value)
            if address == PREVIOUS and width == 4:
                writes.append(["previous", address, width, value])
            elif TABLE <= address and address + width <= TABLE + TABLE_SIZE and width == 4:
                writes.append(["table", address, width, value])
            elif SP - 8 <= address and address + width <= SP and width == 4:
                writes.append(["stack", address, width, value])
            else:
                raise ValueError(f"unexpected AB30 write {address:08x}/{width}/{value:08x}")
            return super().write(address, width, value)

    memory = Memory()
    mapped = memory.add(WRAM, WRAM_SIZE, work)
    class CPU(emu.CPU):
        def fetch(self, pc):
            if not ENTRY <= pc < END or pc & 1:
                raise ValueError(f"AB30 fetch escaped bounded function {pc:08x}")
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False
        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= LIMIT or not ENTRY <= pc < END:
                raise ValueError(f"AB30 instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0x51000000 + n * 0x01020307 + seed * 0x11111111) & 0xFFFFFFFF for n in range(16)]
    cpu.r[15] = SP
    before_r14, before_sp, before_pr = cpu.r[14], cpu.r[15], 0xFFFFFFF0
    before_special = (cpu.mach, cpu.macl)
    cpu.pr, cpu.pc = before_pr, ENTRY
    while cpu.pc != emu.RETURN_SENTINEL:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("AB30 instruction budget exceeded")
    actual = bytes(mapped[TABLE-WRAM:TABLE-WRAM+TABLE_SIZE])
    current_after = int.from_bytes(mapped[CURRENT_PHYS-WRAM:CURRENT_PHYS-WRAM+4], "big")
    previous_after = int.from_bytes(mapped[PREVIOUS-WRAM:PREVIOUS-WRAM+4], "big")
    if not mutate and actual != expected:
        offsets = [i for i, (a, b) in enumerate(zip(actual, expected)) if a != b][:16]
        raise ValueError(f"AB30 table differs in {case_name}; first differing offsets={offsets}; "
                         f"actual={actual[:24].hex()}; expected={expected[:24].hex()}")
    if not mutate and current_after != case["current"] & 0xFFFFFFFF:
        raise ValueError("AB30 modified its current counter")
    if not mutate and previous_after != case["current"] & 0xFFFFFFFF:
        raise ValueError("AB30 did not update previous counter")
    if cpu.r[14] != before_r14 or cpu.r[15] != before_sp or cpu.pr != before_pr:
        raise ValueError("AB30 failed to restore R14/SP/PR")
    if (cpu.mach, cpu.macl) != before_special:
        raise ValueError("AB30 changed MACH/MACL")
    return {"case": case_name, "seed": seed, "current": hex(case["current"] & 0xFFFFFFFF),
            "previous": hex(case["previous"] & 0xFFFFFFFF),
            "delta": hex((case["current"]-case["previous"]) & 0xFFFFFFFF),
            "steps": cpu.steps, "table_sha256_before": sha(before),
            "table_sha256_after": sha(actual), "expected_table_sha256": sha(expected),
            "table_matches_model": actual == expected,
            "current_after": hex(current_after), "previous_after": hex(previous_after),
            "reads": reads, "writes": writes, "pc_visits": len(pcs),
            "r14_sp_pr_restored": True, "mach_macl_preserved": True,
            "original_bytes_execution": not mutate, "mutated": mutate}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-ab30-count-update.v1", "status": "failure",
              "entry": hex(ENTRY), "code_range": [hex(ENTRY), hex(END)],
              "limits": ["Constructed 18-row counters/current/previous globals and entry registers",
                         "One exact cache-through counter alias and bounded table/stack memory only",
                         "No natural AB94 scheduling, hardware timing, gameplay, or full-game claim"]}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        print(f"FAIL: fresh private report required: {error}")
        return 1
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        try:
            meta = json.loads(args.checkpoint.read_text())
            state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
            if (meta.get("frame") != 1200 or meta.get("state_sha256") != STATE_SHA or
                    meta.get("identity", {}).get("core_sha256") != CORE_SHA or sha(state) != STATE_SHA):
                raise ValueError("frame-1200 state/checkpoint/core identity differs")
            kernel = pinned.read_bounded(args.kernel, SIZE)
            if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA:
                raise ValueError("original Japan kernel SHA/length differs")
            ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
            emu = pinned.interpreter(args.saturn_recomp)
            results = []
            for name in CASES:
                pair = [execute(kernel, ram, emu, name, seed) for seed in SEEDS]
                semantic_writes = lambda run: [event for event in run["writes"] if event[0] != "stack"]
                if (pair[0]["table_sha256_after"], semantic_writes(pair[0])) != (pair[1]["table_sha256_after"], semantic_writes(pair[1])):
                    raise ValueError(f"paired AB30 input runs differ in {name}")
                results.append({"case": name, "runs": pair})
            mutation = execute(kernel, ram, emu, "subtract_and_floor", 0, mutate=True)
            if mutation["table_matches_model"]:
                raise ValueError("mutated AB30 boundary branch survived independent model")
            report.update(status="success", cases=len(results), executions_per_case=2,
                          total_original_executions=sum(len(row["runs"]) for row in results),
                          original_game_bytes_executed=True, results=results,
                          mutation_control={"pc": "0x0600AB5C", "original": "0x8B03",
                                            "replacement": "0x8903", "model_rejected": True},
                          kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA,
                          normalized_workram_sha256=RAM_SHA,
                          probe_sha256=sha(Path(__file__).read_bytes()),
                          interpreter_revision=pinned.INTERPRETER_REVISION,
                          interpreter_sources=pinned.SOURCE_HASHES,
                          contract="AB30 computes unsigned current-minus-previous delta modulo 2^32. If nonzero, it scans 18 rows; only rows with nonzero field80 and counter>1 are considered. Such a counter becomes value-delta when value>delta, otherwise one; counters zero/one are untouched. It then stores current into previous. Equal counters return without table reads or stores.")
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
