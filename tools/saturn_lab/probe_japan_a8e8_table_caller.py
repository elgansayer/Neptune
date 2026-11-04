#!/usr/bin/env python3
"""Execute the original A8E8 caller through A80E/AACC with constructed task state."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a80e_table_update as a80e

BASE, SIZE = a80e.BASE, a80e.SIZE
WRAM, WRAM_SIZE = a80e.WRAM, a80e.WRAM_SIZE
ENTRY, END = 0x0600A8E8, 0x0600A946
EXIT = {0x0600A79C: "error_loop", 0x0600ACE8: "scheduler_handoff"}
CALLER_CODE = tuple(range(ENTRY, END, 2))
CODE = CALLER_CODE + tuple(range(a80e.ENTRY, a80e.END, 2)) + tuple(range(a80e.CALLBACK, a80e.CALLBACK_END, 2))
ALIASES = {0x2600A018: 0x0600A018, 0x2600A01C: 0x0600A01C,
           0x2600A020: 0x0600A020, 0x2600A024: 0x0600A024,
           0x2600A030: 0x0600A030}
LITERALS = {0x0600AA1C: (4, 0x2600A030), 0x0600AA20: (4, 0x2600A020),
            0x0600AA24: (4, 0x2600A018), 0x0600AA2C: (4, ENTRY),
            0x0600A8D8: (4, a80e.TABLE), 0x0600A8C2: (2, 0x0630),
            0x0600AB2C: (4, a80e.TABLE)}
SP, LIMIT = 0x06002000, 4096
SEEDS = (0, 1)
CASES = {
    "free_slot_success": {"indices": (5, 6), "count": 2, "fields": {
        5: {82: 0xFF, 83: 9}, 0: {80: 1, 82: 5}, 1: {80: 1, 82: 5}}},
    "active_slot_success": {"indices": (5, 6), "count": 2, "fields": {
        5: {80: 1, 81: 4, 82: 2, 83: 7}, 2: {80: 1, 81: 4, 82: 0xFF, 83: 1},
        0: {80: 1, 82: 5}, 3: {80: 1, 82: 5},
        6: {80: 1, 81: 4, 82: 4, 83: 6}, 4: {80: 1, 81: 4, 82: 0xFF, 83: 1},
        1: {80: 1, 82: 6}, 7: {80: 1, 82: 6}}},
    "callback_latch_success": {"indices": (5, 6), "count": 2, "fields": {
        5: {80: 1, 81: 4, 82: 2}, 2: {80: 1, 81: 4, 83: 1},
        6: {80: 1, 81: 4, 82: 4}, 4: {80: 1, 81: 4, 83: 1}}},
    "free_slot_exhausted": {"indices": (16, 17), "count": 1, "fields": {
        16: {82: 0xFF, 83: 1}, 17: {82: 0xFF, 83: 1},
        0: {80: 1, 82: 17}, 1: {80: 1, 82: 16}}},
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def modeled_table(case, idx):
    table = a80e.initial_table(case)
    table[idx * a80e.ROW_SIZE + 80] = 0
    table[idx * a80e.ROW_SIZE + 81] = 0
    return a80e.expected_table(table, idx)


def execute(kernel, ram, emu, case_name, seed, mutate=False):
    if (len(kernel) != SIZE or sha(kernel) != a80e.KERNEL_SHA or
            len(ram) != WRAM_SIZE or sha(ram) != a80e.RAM_SHA):
        raise ValueError("original kernel or frame-1200 WorkRAM-H identity differs")
    if case_name not in CASES or seed not in SEEDS:
        raise ValueError("case or seed outside declared corpus")
    for start, end in ((ENTRY, END), (a80e.ENTRY, a80e.END),
                       (a80e.CALLBACK, a80e.CALLBACK_END)):
        if ram[start-WRAM:end-WRAM] != kernel[start-BASE:end-BASE]:
            raise ValueError(f"captured code differs from original at {start:08x}")

    case = CASES[case_name]
    idx = case["indices"][seed]
    work = bytearray(ram)
    before = a80e.initial_table(case)
    work[a80e.TABLE-WRAM:a80e.TABLE-WRAM+a80e.TABLE_SIZE] = before
    # VBR-indexed cache-through words are explicit aliases of the corresponding
    # WorkRAM-H addresses; they do not model cache-maintenance side effects.
    for slot, selected in enumerate(case["indices"]):
        work[0x0600A018-WRAM+4*slot:0x0600A01C-WRAM+4*slot] = selected.to_bytes(4, "big")
    for slot in (0, 1):
        rowptr = a80e.TABLE + case["indices"][slot] * a80e.ROW_SIZE
        work[0x0600A020-WRAM+4*slot:0x0600A024-WRAM+4*slot] = rowptr.to_bytes(4, "big")
    work[0x0600A030-WRAM:0x0600A034-WRAM] = case["count"].to_bytes(4, "big")
    if mutate:
        work[0x0600A816-WRAM+1] = 0xFE

    reads, writes, pcs = [], [], []
    class Memory(emu.Memory):
        def _translate(self, address, width):
            for alias, physical in ALIASES.items():
                if alias <= address and address + width <= alias + 4:
                    return physical + address - alias, alias
            return address, address

        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in CODE:
                    raise ValueError(f"A8E8 PC fence {address:08x}/{width}")
                return super().read(address, width)
            translated, reported = self._translate(address, width)
            if translated != address:
                if width != 4:
                    raise ValueError(f"cache-through alias width {width}")
                value = super().read(translated, width)
                reads.append(["cache_alias", address, width, value])
                return value
            if address in LITERALS and LITERALS[address][0] == width:
                value = super().read(address, width)
                reads.append(["literal", address, width, value])
                return value
            if a80e.TABLE <= address and address + width <= a80e.TABLE + a80e.TABLE_SIZE and width in (1, 4):
                value = super().read(address, width)
                reads.append(["table", address, width, value])
                return value
            if SP - 64 <= address and address + width <= SP and width == 4:
                value = super().read(address, width)
                reads.append(["stack", address, width, value])
                return value
            raise ValueError(f"unexpected A8E8 read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            translated, reported = self._translate(address, width)
            if translated != address:
                if width != 4:
                    raise ValueError(f"cache-through alias write width {width}")
                writes.append(["cache_alias", address, width, value])
                return super().write(translated, width, value)
            if a80e.TABLE <= address and address + width <= a80e.TABLE + a80e.TABLE_SIZE and width in (1, 4):
                writes.append(["table", address, width, value])
            elif SP - 64 <= address and address + width <= SP and width == 4:
                writes.append(["stack", address, width, value])
            else:
                raise ValueError(f"unexpected A8E8 write {address:08x}/{width}/{value:08x}")
            return super().write(address, width, value)

    memory = Memory()
    mapped = memory.add(WRAM, WRAM_SIZE, work)
    class CPU(emu.CPU):
        def fetch(self, pc):
            if pc not in CODE:
                raise ValueError(f"A8E8 fetch outside caller/A80E/AACC {pc:08x}")
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False
        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or pc not in CODE:
                raise ValueError(f"A8E8 instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0x41000000 + n * 0x0103070B + seed * 0x11111111) & 0xFFFFFFFF for n in range(16)]
    cpu.r[15] = SP
    cpu.sr = 0xF0
    cpu.vbr = 0x06000400 if seed else 0x06000000
    cpu.mach, cpu.macl = 0x10203040 ^ seed, 0xA1B2C3D4 ^ seed
    initial_sp, initial_pr = cpu.r[15], emu.RETURN_SENTINEL
    cpu.pr, cpu.pc = initial_pr, ENTRY
    while cpu.pc not in EXIT:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("A8E8 instruction budget exceeded")
    actual = bytes(mapped[a80e.TABLE-WRAM:a80e.TABLE-WRAM+a80e.TABLE_SIZE])
    expected = modeled_table(case, idx)
    if not mutate and actual != expected:
        raise ValueError(f"composed table differs from independent model in {case_name}")
    expected_count = case["count"] - 1
    got_count = int.from_bytes(mapped[0x0600A030-WRAM:0x0600A034-WRAM], "big")
    expected_exit = "scheduler_handoff" if expected_count else "error_loop"
    if not mutate and (got_count != expected_count or EXIT[cpu.pc] != expected_exit):
        raise ValueError("A8E8 count/handoff differs from independent model")
    if cpu.r[15] != initial_sp or cpu.pr != initial_pr:
        raise ValueError("A8E8 failed to restore caller stack/link")
    return {"case": case_name, "seed": seed, "vbr": hex(cpu.vbr), "selected_index": idx, "steps": cpu.steps,
            "exit": EXIT[cpu.pc], "count_before": case["count"], "count_after": got_count,
            "table_sha256_before": sha(before), "table_sha256_after": sha(actual),
            "expected_table_sha256": sha(expected), "table_matches_model": actual == expected,
            "a80e_calls": pcs.count(a80e.ENTRY), "aacc_calls": pcs.count(a80e.CALLBACK),
            "reads": reads, "writes": writes, "pc_visits": len(pcs),
            "sp_restored": cpu.r[15] == initial_sp, "pr_restored": cpu.pr == initial_pr,
            "original_bytes_execution": not mutate, "mutated": mutate}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a8e8-table-caller.v1", "status": "failure",
              "entry": hex(ENTRY), "exits": {hex(k): v for k, v in EXIT.items()},
              "limits": ["Constructed VBR/global/table values; natural A8E8 reachability is not established",
                         "Cache-through aliases map only to declared WorkRAM-H words; no cache effects modeled",
                         "Execution stops at A79C/ACE8 edges; downstream scheduler/error behavior is not executed"]}
    try:
        with args.report.open("x", encoding="utf-8") as out:
            try:
                meta = json.loads(args.checkpoint.read_text())
                state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
                if (meta.get("frame") != 1200 or meta.get("state_sha256") != a80e.STATE_SHA or
                        meta.get("identity", {}).get("core_sha256") != a80e.CORE_SHA or sha(state) != a80e.STATE_SHA):
                    raise ValueError("frame-1200 state/checkpoint/core identity differs")
                kernel = pinned.read_bounded(args.kernel, SIZE)
                ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
                # Existing frame schema uses the canonical WorkRAM-H field spelling.
                emu = pinned.interpreter(args.saturn_recomp)
                results = []
                for case_name in CASES:
                    pair = [execute(kernel, ram, emu, case_name, seed) for seed in SEEDS]
                    if (pair[0]["selected_index"], pair[1]["selected_index"]) != CASES[case_name]["indices"]:
                        raise ValueError(f"VBR-selected table indices differ for {case_name}")
                    for run in pair:
                        expected_exit = "scheduler_handoff" if CASES[case_name]["count"] > 1 else "error_loop"
                        if run["exit"] != expected_exit or run["count_after"] != CASES[case_name]["count"] - 1 or not run["table_matches_model"]:
                            raise ValueError(f"constructed VBR run violates independent model for {case_name}")
                    results.append({"case": case_name, "runs": pair})
                control = execute(kernel, ram, emu, "free_slot_success", 0, mutate=True)
                if control["table_matches_model"]:
                    raise ValueError("mutated A80E instruction escaped transition-model control")
                report.update(status="success", cases=len(results), executions_per_case=2,
                              total_original_executions=sum(len(row["runs"]) for row in results),
                              original_game_bytes_executed=True, results=results,
                              mutation_control={"pc": "0x0600A816", "replacement_low_byte": "0xFE",
                                                "model_rejected": True},
                              probe_sha256=sha(Path(__file__).read_bytes()),
                              kernel_sha256=a80e.KERNEL_SHA, state_sha256=a80e.STATE_SHA,
                              normalized_workram_sha256=a80e.RAM_SHA,
                              interpreter_revision=pinned.INTERPRETER_REVISION,
                              interpreter_sources=pinned.SOURCE_HASHES,
                              contract="Original A8E8 selects VBR-indexed cache-through words, decrements the global count, clears fields 80/81 on the selected row, calls original A80E/AACC, then exits through the observed scheduler or error branch. Only constructed caller state is tested.")
            except Exception as error:
                report["error"] = {"type": type(error).__name__, "reason": str(error)}
            out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
        print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
        return 0 if report["status"] == "success" else 1
    except FileExistsError:
        print(json.dumps({"status": "failure", "reason": "report exists; immutable"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
