#!/usr/bin/env python3
"""Continue a caller-replayed original AB94 state through resident original A8E8."""
from __future__ import annotations
import argparse, hashlib, json, os
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


def execute(kernel, ram, emu, case_name, seed, mutate=False, caller=None, prefix_writes=()):
    if (len(kernel) != SIZE or sha(kernel) != a80e.KERNEL_SHA or
            len(ram) != WRAM_SIZE or sha(ram) != a80e.RAM_SHA):
        raise ValueError("original kernel or frame-1200 WorkRAM-H identity differs")
    if caller is None or case_name != "caller_state":
        raise ValueError("caller-state A8E8 continuation requires the AB94 row-state result")
    for start, end in ((ENTRY, END), (a80e.ENTRY, a80e.END),
                       (a80e.CALLBACK, a80e.CALLBACK_END)):
        if ram[start-WRAM:end-WRAM] != kernel[start-BASE:end-BASE]:
            raise ValueError(f"captured code differs from original at {start:08x}")

    work = bytearray(ram)
    for source_writes in (prefix_writes, caller["writes"]):
        for kind, address, width, value in source_writes:
            if kind not in ("stack", "task_row", "cache_alias", "alias", "task_table", "scheduler_cursor", "previous_counter"):
                raise ValueError(f"unsupported inherited write class {kind}")
            physical = address - 0x20000000 if kind in ("cache_alias", "alias") else address
            if physical < WRAM or physical + width > WRAM + WRAM_SIZE:
                raise ValueError(f"inherited write outside WorkRAM-H {address:08x}/{width}")
            work[physical-WRAM:physical-WRAM+width] = (value & ((1 << (8*width))-1)).to_bytes(width, "big")
    before = bytes(work[a80e.TABLE-WRAM:a80e.TABLE-WRAM+a80e.TABLE_SIZE])
    count_before = int.from_bytes(work[0x0600A030-WRAM:0x0600A034-WRAM], "big")
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
            if SP - 256 <= address and address + width <= SP and width == 4:
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
            elif SP - 256 <= address and address + width <= SP and width == 4:
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
    if caller["candidate_row_state"] != [0, 2] or caller["stop_pc"] != hex(ENTRY):
        raise ValueError("AB94 caller result is not row0/+80=2 at A8E8")
    cpu.r = [int(value, 16) for value in caller["registers_at_handoff"]]
    cpu.vbr = int(caller["vbr"], 16)
    cpu.sr = int(caller["sr_at_handoff"], 16)
    cpu.mach = int(caller["mach_at_handoff"], 16)
    cpu.macl = int(caller["macl_at_handoff"], 16)
    initial_sp, initial_pr = cpu.r[15], int(caller["pr_at_handoff"], 16)
    cpu.pr, cpu.pc = initial_pr, ENTRY
    while cpu.pc not in EXIT:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("A8E8 instruction budget exceeded")
    actual = bytes(mapped[a80e.TABLE-WRAM:a80e.TABLE-WRAM+a80e.TABLE_SIZE])
    got_count = int.from_bytes(mapped[0x0600A030-WRAM:0x0600A034-WRAM], "big")
    if cpu.r[15] != initial_sp or cpu.pr != initial_pr:
        raise ValueError("A8E8 failed to restore caller stack/link")
    return {"case": case_name, "seed": seed, "vbr": hex(cpu.vbr), "steps": cpu.steps,
            "exit": EXIT[cpu.pc], "pc_stop": hex(cpu.pc), "count_before": count_before, "count_after": got_count,
            "table_sha256_before": sha(before), "table_sha256_after": sha(actual),
            "a80e_calls": pcs.count(a80e.ENTRY), "aacc_calls": pcs.count(a80e.CALLBACK),
            "reads": reads, "writes": writes, "pc_visits": len(pcs),
            "pcs_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in pcs)),
            "registers_at_exit": [hex(v) for v in cpu.r], "sp_restored": cpu.r[15] == initial_sp,
            "pr_restored": cpu.pr == initial_pr, "original_bytes_execution": not mutate,
            "mutated": mutate, "inherited_prefix_writes": len(prefix_writes),
            "inherited_ab94_writes": len(caller["writes"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report", "prefix-report", "caller-report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-ab94-a8e8-continuation.v1", "status": "failure",
              "entry": hex(ENTRY), "exits": {hex(k): v for k, v in EXIT.items()},
              "limits": ["A208 and AB94 writes/registers are replayed into a separate CPU instance",
                         "Candidate row0/+80=2 is constructed; R6/R7 remain seeded",
                         "Stops at A79C/ACE8 edge; does not execute downstream function or claim natural scheduling"]}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print(json.dumps({"status": "failure", "reason": "fresh private report required"}))
        return 1
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        try:
            meta = json.loads(args.checkpoint.read_text())
            state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
            if (meta.get("frame") != 1200 or meta.get("state_sha256") != a80e.STATE_SHA or
                    meta.get("identity", {}).get("core_sha256") != a80e.CORE_SHA or sha(state) != a80e.STATE_SHA):
                raise ValueError("frame-1200 state/checkpoint/core identity differs")
            kernel = pinned.read_bounded(args.kernel, SIZE)
            ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
            prefix = json.loads(args.prefix_report.read_text())
            caller_doc = json.loads(args.caller_report.read_text())
            if (prefix.get("schema") != "neptune.original-japan-a208-ae3a-ab94-resume.v1" or
                    prefix.get("status") != "success" or prefix.get("source_kernel_sha256") != a80e.KERNEL_SHA or
                    caller_doc.get("schema") != "neptune.original-japan-ab94-row-scan-cases.v1" or
                    caller_doc.get("status") != "success"):
                raise ValueError("prefix/caller report identity or status differs")
            prefix_row = next(row for row in prefix["results"] if row["slot"] == 0 and row["seed"] == 0 and row["original_bytes_executed"])
            caller = next(row for row in caller_doc["results"] if row.get("candidate_row_state") == [0, 2])
            emu = pinned.interpreter(args.saturn_recomp)
            result = execute(kernel, ram, emu, "caller_state", 0, caller=caller, prefix_writes=prefix_row["writes"])
            report.update(status="success", original_executions=1, original_game_bytes_executed=True,
                          result=result, prefix_report_sha256=sha(args.prefix_report.read_bytes()),
                          caller_report_sha256=sha(args.caller_report.read_bytes()),
                          probe_sha256=sha(Path(__file__).read_bytes()), kernel_sha256=a80e.KERNEL_SHA,
                          state_sha256=a80e.STATE_SHA, normalized_workram_sha256=a80e.RAM_SHA,
                          interpreter_revision=pinned.INTERPRETER_REVISION,
                          interpreter_sources=pinned.SOURCE_HASHES,
                          contract="Original A8E8 starts from register/special state and A208/AB94 write events replayed from bounded reports. It executes through original A80E/AACC and stops before fetching A79C or ACE8. This is not same-instance composition.")
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("original_executions", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
