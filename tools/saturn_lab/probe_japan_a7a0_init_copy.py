#!/usr/bin/env python3
"""Execute original A7A0, its A164 context save, and A95610 copy helper."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg

BASE, SIZE = 0x0600A000, 786432
WRAM, WRAM_SIZE = 0x06000000, 0x100000
ENTRY, EXIT = 0x0600A7A0, 0x0600A80E
SAVE, SAVE_END = 0x0600A164, 0x0600A186
COPY, COPY_END = 0x06095610, 0x060956D0
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
RAM_SHA = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
CORE_SHA = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
SP = 0x06002000
FRAME, FRAME_SIZE = 0x060BDD24, 0x58
TABLE, TABLE_SIZE, ROW_SIZE = 0x060BCEEC, 0x630, 0x58
COUNT_LITERAL = 0x0600A8C2
CODE = (tuple(range(ENTRY, EXIT, 2)) + tuple(range(SAVE, SAVE_END, 2))
        + tuple(range(COPY, COPY_END, 2)))
SEEDS = (0, 1)
LIMIT = 10000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Fence(ValueError):
    pass


def execute(kernel: bytes, ram: bytes, emu, seed: int, mutate_count: bool = False):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA or len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("original kernel or captured WorkRAM-H identity differs")
    if seed not in SEEDS:
        raise ValueError("seed outside declared pair")
    for start, end in ((ENTRY, EXIT), (SAVE, SAVE_END), (COPY, COPY_END)):
        if ram[start - WRAM:end - WRAM] != kernel[start - BASE:end - BASE]:
            raise ValueError(f"captured code differs from 0KRNL.BIN at {start:08x}")
    if int.from_bytes(kernel[COUNT_LITERAL - BASE:COUNT_LITERAL - BASE + 2], "big") != TABLE_SIZE:
        raise ValueError("original A7A0 copy count literal differs")

    class CPU(emu.CPU):
        def fetch(self, pc):
            if pc not in CODE:
                raise Fence(f"A7A0 composed PC fence {pc:08x}")
            return super().fetch(pc)

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or pc not in CODE:
                raise Fence(f"A7A0 composed instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    class StrictMemory(emu.Memory):
        def write(self, address, width, value):
            stack_store = SP - 0x18 <= address and address + width <= SP and width == 4
            global_words = {0x2600A018, 0x2600A01C, 0x2600A020, 0x2600A024,
                            0x2600A030, 0x2600A034, 0x2600A038}
            global_store = address in global_words and width == 4
            frame_store = FRAME <= address and address + width <= FRAME + FRAME_SIZE
            table_store = TABLE <= address and address + width <= TABLE + TABLE_SIZE and width == 4
            if not (stack_store or global_store or frame_store or table_store):
                raise ValueError(f"A7A0 write outside declared WorkRAM contract {address:08x}/{width}/{value:08x}")
            return super().write(address, width, value)

    memory = StrictMemory()
    work = memory.add(WRAM, WRAM_SIZE, ram)
    if mutate_count:
        work[COUNT_LITERAL - WRAM:COUNT_LITERAL - WRAM + 2] = (TABLE_SIZE - ROW_SIZE).to_bytes(2, "big")
    events, pcs = [], []
    memory.log = events

    cpu = CPU(memory)
    cpu.r = [(0xA5000000 + i * 0x00010203 + seed * 0x11111111) & 0xFFFFFFFF
             for i in range(16)]
    cpu.r[15] = SP
    initial = cpu.r.copy()
    cpu.mach = 0x13579BDF ^ seed
    cpu.macl = 0x2468ACE0 ^ seed
    initial_mach, initial_macl = cpu.mach, cpu.macl
    cpu.sr, cpu.pr, cpu.pc = 0xF0, emu.RETURN_SENTINEL, ENTRY
    initial_sr = cpu.sr
    before = bytes(work)
    while cpu.pc != emu.RETURN_SENTINEL:
        cpu.step()
        if cpu.steps > LIMIT:
            raise Fence("A7A0 instruction budget exceeded")

    stores = [e for e in events if e[0] == "w"]
    frame = bytes(work[FRAME - WRAM:FRAME - WRAM + FRAME_SIZE])
    destinations = [bytes(work[TABLE - WRAM + n * ROW_SIZE:TABLE - WRAM + (n + 1) * ROW_SIZE])
                    for n in range(TABLE_SIZE // ROW_SIZE)]
    expected_globals = {
        0x0600A018: 0xFFFFFFFF, 0x0600A01C: 0xFFFFFFFF,
        0x0600A020: 0, 0x0600A024: 0, 0x0600A030: 0,
        0x0600A034: 0, 0x0600A038: 0,
    }
    for address, value in expected_globals.items():
        actual = int.from_bytes(work[address - WRAM:address - WRAM + 4], "big")
        if actual != value:
            raise ValueError(f"A7A0 global initialization differs at {address:08x}: {actual:08x}")
    if not mutate_count and (len(destinations) != 18 or any(row != destinations[0] for row in destinations)):
        raise ValueError("A7A0 did not initialize eighteen identical 88-byte records")
    if mutate_count and any(row != destinations[0] for row in destinations[:17]):
        raise ValueError("mutated A7A0 prefix rows differ")
    if not mutate_count and any(row != frame for row in destinations):
        raise ValueError("A95610 record copy differs from the A7A0 frame template")
    if not mutate_count and len(stores) != 459:
        raise ValueError(f"A7A0 expected 459 WorkRAM stores, observed {len(stores)}")
    if cpu.r[15] != SP or cpu.pr != emu.RETURN_SENTINEL:
        raise ValueError("A7A0 stack/return state differs")
    if cpu.r[8:16] != initial[8:16] or (cpu.mach, cpu.macl) != (initial_mach, initial_macl):
        raise ValueError(f"A7A0 callee-saved registers/MACH/MACL differ: GPR={cpu.r[8:16]!r}, MACH/MACL={cpu.mach:08x}/{cpu.macl:08x}")
    if (cpu.sr ^ initial_sr) != 1 or cpu.sr & 1 != 1:
        raise ValueError(f"A7A0 final SR differs outside expected T-bit result: {initial_sr:08x}->{cpu.sr:08x}")
    if not mutate_count and (cpu.steps != 2431 or pcs.count(0x0600A7F2) != 18):
        raise ValueError("A7A0 step or 18-call count differs")
    for start, end in ((ENTRY, EXIT), (SAVE, SAVE_END), (COPY, COPY_END)):
        if bytes(work[start - WRAM:end - WRAM]) != ram[start - WRAM:end - WRAM]:
            raise ValueError(f"A7A0 composition modified original code at {start:08x}")

    digest = hashlib.sha256()
    counts = {}
    for kind, address, width, value in events:
        digest.update(f"{kind}:{address:08x}:{width}:{value:08x}\n".encode())
        counts[(kind, width)] = counts.get((kind, width), 0) + 1
    changed = [i for i, (a, b) in enumerate(zip(before, work)) if a != b]
    return {"seed": seed, "steps": cpu.steps, "return_pc": hex(cpu.pc), "sp_after": hex(cpu.r[15]),
            "a164_entry_visits": pcs.count(SAVE), "a95610_entry_visits": pcs.count(COPY),
            "a164_callsite_visits": pcs.count(0x0600A7D2), "a95610_callsite_visits": pcs.count(0x0600A7F2),
            "copy_rows": sum(row == frame for row in destinations), "frame_sha256": sha(frame),
            "table_sha256": sha(bytes(work[TABLE - WRAM:TABLE - WRAM + TABLE_SIZE])),
            "event_counts": {f"{kind}/{width}": n for (kind, width), n in sorted(counts.items())},
            "event_sha256": digest.hexdigest(), "writes": len(stores),
            "changed_bytes": len(changed), "changed_range": [hex(WRAM + changed[0]), hex(WRAM + changed[-1] + 1)],
            "workram_sha256_after": sha(bytes(work)), "registers_after": [hex(x) for x in cpu.r],
            "initial_registers": [hex(x) for x in initial], "sr_after": hex(cpu.sr), "sr_before": hex(initial_sr),
            "mach_after": hex(cpu.mach), "macl_after": hex(cpu.macl), "mutated_count": mutate_count}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a7a0-init-copy.v1", "status": "failure",
              "entry": hex(ENTRY), "limits": ["Direct constructed A7A0 entry/registers; natural startup/task reachability unproven",
                         "Captured frame-1200 WorkRAM-H; cache-through addresses alias mapped WorkRAM-H",
                         "Original A164 context save and A95610 copy helper only; no device, timing, gameplay or all-game claim"]}
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
                rows = []
                for seed in SEEDS:
                    first, second = execute(kernel, ram, emu, seed), execute(kernel, ram, emu, seed)
                    if first != second:
                        raise ValueError(f"paired A7A0 runs differ for seed {seed}")
                    rows.append(first)
                control = execute(kernel, ram, emu, 0, mutate_count=True)
                if control["copy_rows"] != 17 or control["a95610_entry_visits"] != 17:
                    raise ValueError("A7A0 copy-count mutation was not detected")
                report.update(status="success", original_game_bytes_executed=True,
                              captured_snapshot_data_used=True, release="Japan T-14302G V1.000",
                              source_file="0KRNL.BIN", cpu="master SH-2",
                              code_ranges=[[hex(ENTRY), hex(EXIT)], [hex(SAVE), hex(SAVE_END)],
                                            [hex(COPY), hex(COPY_END)]],
                              cases=len(rows), executions_per_case=2, results=rows,
                              mutation_control={"literal": hex(COUNT_LITERAL), "replacement": hex(TABLE_SIZE - ROW_SIZE),
                                                "detected_copy_rows": control["copy_rows"],
                                                "detected_helper_calls": control["a95610_entry_visits"]},
                              kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA, normalized_workram_sha256=RAM_SHA,
                              probe_sha256=sha(Path(__file__).read_bytes()),
                              interpreter_revision=pinned.INTERPRETER_REVISION,
                              interpreter_sources=pinned.SOURCE_HASHES,
                              contract="A7A0 initializes global WorkRAM words, calls original A164 to save a 48-byte SH-2 context into the 88-byte template at 060BDD24, then calls original A95610 eighteen times to copy that exact 88-byte template across 060BCEEC..060BD51B. Cache-through writes are captured as WorkRAM-H aliases.")
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
