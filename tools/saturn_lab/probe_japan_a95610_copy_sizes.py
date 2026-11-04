#!/usr/bin/env python3
"""Execute original Japan A95610 across its short and long copy paths."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg

BASE, SIZE = 0x0600A000, 786432
WRAM, WRAM_SIZE = 0x06000000, 0x100000
ENTRY, COPY_END = 0x06095610, 0x060956D0
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
RAM_SHA = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
CORE_SHA = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
TABLE_BASE, TABLE_END = 0x0609566C, 0x060956B0
LITERAL = 0x06095620
SP, SOURCE, DEST, ARENA_SIZE = 0x06002000, 0x06030000, 0x06031000, 96
SHORT_LENGTHS = tuple(range(0, 65, 4))
UNALIGNED_SHORT_LENGTHS = tuple(n for n in range(65) if n % 4)
LONG_LENGTHS = (65, 67, 68, 88)
CODE = (tuple(range(ENTRY, 0x06095620, 2))
        + tuple(range(0x06095626, 0x0609566A, 2))
        + tuple(range(0x060956B0, COPY_END, 2)))
LIMIT = 256


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Fence(ValueError):
    pass


def execute(kernel: bytes, ram: bytes, emu, length: int, seed: int,
            mutate_table: bool = False):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA or len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("original Japan kernel or captured WorkRAM-H identity differs")
    if length not in SHORT_LENGTHS + UNALIGNED_SHORT_LENGTHS + LONG_LENGTHS or seed not in (0, 1):
        raise ValueError("length or seed outside the declared corpus")
    if ram[ENTRY - WRAM:COPY_END - WRAM] != kernel[ENTRY - BASE:COPY_END - BASE]:
        raise ValueError("captured A95610 code differs from original kernel")
    if int.from_bytes(kernel[LITERAL - BASE:LITERAL - BASE + 4], "big") != TABLE_BASE:
        raise ValueError("A95610 literal does not identify the original jump table")

    work = bytearray(ram)
    source = bytes((i * 37 + 11) & 0xFF for i in range(ARENA_SIZE))
    destination_before = bytes((0xD0 + i) & 0xFF for i in range(ARENA_SIZE))
    work[SOURCE - WRAM:SOURCE - WRAM + ARENA_SIZE] = source
    work[DEST - WRAM:DEST - WRAM + ARENA_SIZE] = destination_before
    table_address = TABLE_BASE + length
    if mutate_table:
        if length != 4:
            raise ValueError("table mutation is declared only for length four")
        # The entry at index four normally targets one unrolled longword copy.
        work[TABLE_BASE + 4 - WRAM:TABLE_BASE + 8 - WRAM] = (0x06095660).to_bytes(4, "big")

    reads, writes, pcs = [], [], []

    class Memory(emu.Memory):
        def __init__(self):
            super().__init__()
            self.fetching = False

        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in CODE:
                    raise Fence(f"A95610 PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address == LITERAL and width == 4:
                value = super().read(address, width)
                reads.append(["literal", address, width, value])
                return value
            if length <= 64 and address == table_address and width == 4:
                value = super().read(address, width)
                reads.append(["jump-table", address, width, value])
                return value
            if SOURCE <= address and address + width <= SOURCE + ARENA_SIZE:
                value = super().read(address, width)
                reads.append(["source", address, width, value])
                return value
            if address in (SP - 4, SP - 8) and width == 4:
                value = super().read(address, width)
                reads.append(["stack", address, width, value])
                return value
            raise ValueError(f"unexpected A95610 read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            if address in (SP - 4, SP - 8) and width == 4:
                writes.append(["stack", address, width, value])
            elif DEST <= address and address + width <= DEST + ARENA_SIZE and width == 4:
                writes.append(["destination", address, width, value])
            else:
                raise ValueError(f"unexpected A95610 write {address:08x}/{width}/{value:08x}")
            return super().write(address, width, value)

    memory = Memory()
    mapped = memory.add(WRAM, WRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            if pc not in CODE:
                raise Fence(f"A95610 fetch target {pc:08x} outside copied code paths")
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or pc not in CODE:
                raise Fence(f"A95610 instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0x87000000 + i * 0x01020305 + seed * 0x11111111) & 0xFFFFFFFF
             for i in range(16)]
    cpu.r[0], cpu.r[1], cpu.r[2], cpu.r[3], cpu.r[15] = length, DEST, SOURCE, 0xC001D00D + seed, SP
    initial_r3 = cpu.r[3]
    cpu.pr, cpu.pc = emu.RETURN_SENTINEL, ENTRY
    try:
        while cpu.pc != emu.RETURN_SENTINEL:
            cpu.step()
            if cpu.steps > LIMIT:
                raise Fence("A95610 instruction budget exceeded")
    except Fence as error:
        return {"seed": seed, "length": length, "status": "bounded_fence",
                "error": str(error), "pc": hex(cpu.pc), "steps": cpu.steps,
                "writes": writes, "reads": reads, "pc_trace": [hex(x) for x in pcs]}

    copied = length if length <= 64 else (length // 4) * 4
    expected = source[:copied] + destination_before[copied:]
    actual = bytes(mapped[DEST - WRAM:DEST - WRAM + ARENA_SIZE])
    copy_writes = [event for event in writes if event[0] == "destination"]
    source_reads = [event for event in reads if event[0] == "source"]
    expected_source_reads = copied if length <= 64 else copied + 4
    if not mutate_table and actual != expected:
        raise ValueError(f"A95610 length {length} destination bytes differ from expected copy")
    if not mutate_table and (len(copy_writes) != copied // 4 or len(source_reads) != expected_source_reads // 4):
        raise ValueError(f"A95610 length {length} read/write counts differ")
    if cpu.r[15] != SP or cpu.pr != emu.RETURN_SENTINEL or cpu.r[3] != initial_r3 or cpu.r[2] != SOURCE:
        raise ValueError("A95610 stack, PR, saved R2/R3 restoration differs")
    return {"seed": seed, "length": length, "status": "returned", "steps": cpu.steps,
            "copy_bytes": copied, "source_read_bytes": len(source_reads) * 4,
            "destination_writes": len(copy_writes), "source_read_addresses": [hex(x[1]) for x in source_reads],
            "destination_write_addresses": [hex(x[1]) for x in copy_writes],
            "destination_sha256": sha(actual), "copied_prefix_sha256": sha(actual[:copied]),
            "reads": reads, "return_pc": hex(cpu.pc), "sp_after": hex(cpu.r[15]),
            "r3_restored": cpu.r[3] == initial_r3, "mutation": mutate_table,
            "expected_bytes_match": actual == expected,
            "pc_first_last": [hex(pcs[0]), hex(pcs[-1])], "pc_visits": len(pcs)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a95610-copy-sizes.v1", "status": "failure",
              "entry": hex(ENTRY), "limits": ["Direct constructed source/destination/length/registers; no natural caller proof",
                         "Captured frame-1200 WorkRAM-H; no device/timing/gameplay effects",
                         "Source and destination are disjoint and four-byte aligned; overlap and hardware alignment faults are not tested"]}
    try:
        with args.report.open("x", encoding="utf-8") as out:
            try:
                meta = json.loads(args.checkpoint.read_text())
                state = pinned.read_bounded(args.state, 16 * 1024 * 1024)
                if (meta.get("frame") != 1200 or meta.get("state_sha256") != STATE_SHA
                        or meta.get("identity", {}).get("core_sha256") != CORE_SHA or sha(state) != STATE_SHA):
                    raise ValueError("frame-1200 state/checkpoint/core identity differs")
                kernel = pinned.read_bounded(args.kernel, SIZE)
                ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
                emu = pinned.interpreter(args.saturn_recomp)
                cases = []
                for length in SHORT_LENGTHS + UNALIGNED_SHORT_LENGTHS + LONG_LENGTHS:
                    first = execute(kernel, ram, emu, length, 0)
                    second = execute(kernel, ram, emu, length, 1)
                    def comparable(row):
                        result = {k: v for k, v in row.items() if k != "seed"}
                        if "reads" in result:
                            result["reads"] = [event[:3] if event[0] == "stack" else event
                                               for event in result["reads"]]
                        if "writes" in result:
                            result["writes"] = [event[:3] if event[0] == "stack" else event
                                                for event in result["writes"]]
                        return result
                    if comparable(first) != comparable(second):
                        raise ValueError(f"A95610 paired traces differ at length {length}")
                    expected_invalid = length in UNALIGNED_SHORT_LENGTHS
                    if expected_invalid and not (first["status"] == second["status"] == "bounded_fence"
                                                 and not any(e[0] == "destination" for e in first["writes"])
                                                 and not any(e[0] == "destination" for e in second["writes"])):
                        raise ValueError(f"A95610 unaligned short length {length} did not stop before stores")
                    if not expected_invalid and first["status"] != "returned":
                        raise ValueError(f"A95610 supported length {length} did not return")
                    cases.append({"length": length, "runs": [first, second],
                                  "paired_execution_trace_identical": True})
                control = execute(kernel, ram, emu, 4, 0, mutate_table=True)
                if control["status"] != "returned" or control["expected_bytes_match"]:
                    raise ValueError("A95610 jump-table mutation escaped output comparison")
                report.update(status="success", original_game_bytes_executed=True,
                              captured_snapshot_data_used=True, release="Japan T-14302G V1.000",
                              source_file="0KRNL.BIN", cpu="master SH-2",
                              code_ranges=[[hex(ENTRY), "0x06095620"], ["0x06095626", "0x0609566A"],
                                           ["0x060956B0", hex(COPY_END)]],
                              short_lengths=list(SHORT_LENGTHS), unaligned_short_lengths=list(UNALIGNED_SHORT_LENGTHS),
                              long_lengths=list(LONG_LENGTHS), cases=cases,
                              mutation_control={"length": 4, "table_entry": "0x06095670",
                                                "replacement_target": "0x06095660",
                                                "expected_bytes_match": control["expected_bytes_match"],
                                                "destination_write_addresses": control["destination_write_addresses"]},
                              kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA,
                              normalized_workram_sha256=RAM_SHA, probe_sha256=sha(Path(__file__).read_bytes()),
                              interpreter_revision=pinned.INTERPRETER_REVISION,
                              interpreter_sources=pinned.SOURCE_HASHES,
                              contract="A95610 short dispatch returns for aligned lengths 0..64 in four-byte steps and copies exactly that many bytes. Other short lengths branch to targets outside the bounded code window before any store. The >64 path copies floor(length/4)*4 bytes and performs one additional longword source read before returning; observed lengths are 65,67,68,88.")
            except Exception as error:
                report["error"] = {"type": type(error).__name__, "reason": str(error)}
            out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
        print(json.dumps({"status": report["status"], "case_count": len(report.get("cases", [])),
                          "report": str(args.report)}))
        return 0 if report["status"] == "success" else 1
    except FileExistsError:
        print(json.dumps({"status": "failure", "reason": "report exists; immutable"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
