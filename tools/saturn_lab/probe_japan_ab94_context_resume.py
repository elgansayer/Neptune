#!/usr/bin/env python3
"""Continue the captured Japan task context through AB94 to its A186 handoff."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg

BASE, SIZE = 0x0600A000, 786432
WRAM, WRAM_SIZE = 0x06000000, 0x100000
ENTRY, END = 0x0600AB94, 0x0600AD60
COUNT, ROW_SIZE, TABLE = 18, 88, 0x060BCEEC
TABLE_END = TABLE + COUNT * ROW_SIZE
AB30, AB30_END = 0x0600AB30, 0x0600AB78
RESTORE, RESTORE_END = 0x0600A186, 0x0600A1AA
RESUME, STOP = 0x0600AD38, 0x0600AD5C
CONTEXT, CONTEXT_SIZE = 0x060BDD7C, 48
SP, LIMIT = 0x060BD8F4, 1024
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
RAM_SHA = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
CORE_SHA = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
SLOTS = (0, 1)
ALIASES = {a: a - 0x20000000 for a in
           (0x2600A018, 0x2600A01C, 0x2600A020, 0x2600A024,
            0x2600A028, 0x2600A02C, 0x2600A038, 0x2600A040, 0x2600A044)}
LITERALS = {a: 4 for a in range(0x0600AD7C, 0x0600ADB0, 4)}
SEEDS = (0, 1)
STACK_WINDOWS = ((SP - 256, SP + 64), (0x060BCC6C - 256, 0x060BCC6C + 64))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(kernel, ram, emu, slot, seed, mutate=False):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA:
        raise ValueError("original Japan kernel identity differs")
    if len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("captured frame-1200 WorkRAM-H identity differs")
    if ram[ENTRY-WRAM:END-WRAM] != kernel[ENTRY-BASE:END-BASE]:
        raise ValueError("captured AB94 continuation differs from original bytes")
    if ram[AB30-WRAM:AB30_END-WRAM] != kernel[AB30-BASE:AB30_END-BASE]:
        raise ValueError("captured AB30 callee differs from original bytes")
    if slot not in SLOTS or seed not in SEEDS:
        raise ValueError("VBR slot or register seed outside declared set")
    vbr = 0x06000000 + slot * 0x400

    work = bytearray(ram)
    if mutate:
        work[0x0600ABCC-WRAM:0x0600ABCE-WRAM] = (0x8800).to_bytes(2, "big")
    reads, writes, pcs = [], [], []
    code_ranges = ((ENTRY, END), (AB30, AB30_END), (RESTORE, RESTORE_END))

    class Memory(emu.Memory):
        def translate(self, address, width):
            for alias, physical in ALIASES.items():
                if alias <= address and address + width <= alias + 4:
                    return physical + address - alias
            return address

        def read(self, address, width):
            if self.fetching:
                if width != 2 or not any(lo <= address < hi for lo, hi in code_ranges) or address & 1:
                    raise ValueError(f"AB94/AB30 PC fence {address:08x}/{width}")
                return super().read(address, width)
            translated = self.translate(address, width)
            if translated != address:
                if width != 4:
                    raise ValueError(f"cache-through alias read width {width}")
                value = super().read(translated, width)
                reads.append(["alias", address, width, value])
                return value
            if address in LITERALS and width == LITERALS[address]:
                value = super().read(address, width)
                reads.append(["literal", address, width, value])
                return value
            if address == 0x060BDDAC and width == 4:
                value = super().read(address, width)
                reads.append(["previous_counter", address, width, value])
                return value
            if 0x060B3D4C <= address and address + width <= 0x060B3D54 and width == 4:
                value = super().read(address, width)
                reads.append(["scheduler_pointer", address, width, value])
                return value
            if 0x060B3D54 <= address and address + width <= 0x060B3D5C and width == 4:
                value = super().read(address, width)
                reads.append(["scheduler_cursor", address, width, value])
                return value
            if TABLE <= address and address + width <= TABLE_END and width in (1, 4):
                value = super().read(address, width)
                reads.append(["task_table", address, width, value])
                return value
            for lo, hi in STACK_WINDOWS:
                if lo <= address and address + width <= hi and width == 4:
                    value = super().read(address, width)
                    reads.append(["stack", address, width, value])
                    return value
            raise ValueError(f"unexpected AB94/AB30 read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            translated = self.translate(address, width)
            if translated != address:
                if width != 4:
                    raise ValueError(f"cache-through alias write width {width}")
                writes.append(["alias", address, width, value])
                return super().write(translated, width, value)
            if TABLE <= address and address + width <= TABLE_END and width in (1, 4):
                writes.append(["task_table", address, width, value])
            elif address == 0x060BDDAC and width == 4:
                writes.append(["previous_counter", address, width, value])
            elif 0x060B3D54 <= address and address + width <= 0x060B3D5C and width == 4:
                writes.append(["scheduler_cursor", address, width, value])
            else:
                for lo, hi in STACK_WINDOWS:
                    if lo <= address and address + width <= hi and width == 4:
                        writes.append(["stack", address, width, value])
                        return super().write(address, width, value)
                raise ValueError(f"unexpected AB94/AB30 write {address:08x}/{width}/{value:08x}")
            return super().write(address, width, value)

    memory = Memory()
    mapped = memory.add(WRAM, WRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            if not any(lo <= pc < hi for lo, hi in code_ranges) or pc & 1:
                raise ValueError(f"AB94/AB30 fetch escaped bounded code {pc:08x}")
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= LIMIT or not any(lo <= pc < hi for lo, hi in code_ranges):
                raise ValueError(f"AB94/AB30 instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

        def step(self):
            if self.pc == RESTORE:
                self.restore_entry = {"r": self.r.copy(), "pr": self.pr,
                                      "mach": self.mach, "macl": self.macl}
            if self.pc == RESUME:
                self.resume_registers = self.r.copy()
                self.resume_special = (self.pr, self.mach, self.macl)
            if self.pc == STOP:
                self.stop_pc = self.pc
                self.pc = emu.RETURN_SENTINEL
                return
            if self.pc == emu.RETURN_SENTINEL:
                return
            return super().step()

    cpu = CPU(memory)
    cpu.r = [(0x33000000 + i * 0x0103070B + seed * 0x11111111) & 0xFFFFFFFF for i in range(16)]
    ctx = ram[CONTEXT-WRAM:CONTEXT-WRAM+CONTEXT_SIZE]
    saved = [int.from_bytes(ctx[i:i+4], "big") for i in range(0, CONTEXT_SIZE, 4)]
    for i in range(8, 15):
        cpu.r[i] = saved[i-8]
    cpu.r[15] = saved[8]
    cpu.r[0] = 0
    cpu.vbr = vbr
    cpu.pr, cpu.mach, cpu.macl, cpu.pc = saved[9], saved[10], saved[11], ENTRY
    while cpu.pc != emu.RETURN_SENTINEL:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("AB94 instruction budget exceeded")
    if getattr(cpu, "stop_pc", None) != STOP or not hasattr(cpu, "restore_entry") or not hasattr(cpu, "resume_registers"):
        raise ValueError(f"AB94/A186 did not reach bounded AD5C return boundary; stop={getattr(cpu, 'stop_pc', None)} pc={cpu.pc:08x}")
    frame = cpu.restore_entry["r"][4]
    frame_values = [int.from_bytes(mapped[frame-WRAM+i:frame-WRAM+i+4], "big")
                    for i in range(0, CONTEXT_SIZE, 4)]
    expected_restored = {8: frame_values[1], 9: frame_values[2], 10: frame_values[3],
                         11: frame_values[4], 12: frame_values[5], 13: frame_values[6],
                         14: frame_values[7], 15: frame_values[8]}
    for reg, value in expected_restored.items():
        if cpu.resume_registers[reg] != value:
            raise ValueError(f"A186 restored R{reg} from the wrong task-context word")
    if cpu.resume_special != (frame_values[9], frame_values[10], frame_values[11]):
        raise ValueError("A186 restored PR/MACH/MACL from the wrong task-context words")
    if cpu.resume_registers[4] != frame_values[0] or cpu.resume_registers[0] != cpu.resume_registers[5]:
        raise ValueError("A186 R4 or RTS delay-slot R0 contract differs")
    return {"slot": slot, "seed": seed, "vbr": hex(vbr), "start_registers": {
                str(i): hex((0 if i == 0 else saved[i-8] if i >= 8 else
                             (0x33000000 + i*0x0103070B + seed*0x11111111) & 0xFFFFFFFF)) for i in range(16)},
            "stop_pc": hex(STOP), "restore_entry_pc": hex(RESTORE),
            "restored_resume_pc": hex(RESUME), "restored_context_pointer": hex(frame),
            "restored_context_sha256": sha(bytes(mapped[frame-WRAM:frame-WRAM+CONTEXT_SIZE])),
            "a186_restore_matches_selected_frame": True,
            "stop_before_return_instruction": True,
            "steps": cpu.steps, "pc_visits": len(pcs),
            "pcs_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in pcs)),
            "reads": reads, "writes": writes,
            "registers_at_handoff": [hex(v) for v in cpu.r],
            "pr_at_handoff": hex(cpu.pr), "sp_at_handoff": hex(cpu.r[15]),
            "original_bytes_executed": not mutate, "mutated": mutate}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-ab94-context-resume.v1", "status": "failure",
              "entry": hex(ENTRY), "stop": hex(STOP),
              "limits": ["Captured frame-1200 WorkRAM-H plus saved context at BDD7C; R0-R7 and VBR are constructed",
                         "Original AB94/AB30/A186 path; stops before AD5C RTS after resume at AD38",
                         "No natural resume/caller, hardware cache/device effect, gameplay, or full-game claim"]}
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
                raise ValueError("original Japan kernel identity differs")
            ram = sg.cpu_words(sg.field(sg.parse(state), "MAIN", "WorkRAMH", WRAM_SIZE), "little")
            emu = pinned.interpreter(args.saturn_recomp)
            results = []
            for slot in SLOTS:
                pair = [execute(kernel, ram, emu, slot, seed) for seed in SEEDS]
                if (pair[0]["stop_pc"], pair[0]["pc_visits"], pair[0]["writes"]) != \
                        (pair[1]["stop_pc"], pair[1]["pc_visits"], pair[1]["writes"]):
                    raise ValueError(f"register seeds changed scheduler path/effects in slot {slot}")
                results.extend(pair)
            if any(row["stop_pc"] != hex(STOP) for row in results):
                raise ValueError("seeded runs did not stop at AD5C")
            mutation = {"pc": "0x0600ABCC", "original": "0x88FF", "replacement": "0x8800"}
            try:
                altered = execute(kernel, ram, emu, 0, 0, mutate=True)
            except Exception as error:
                mutation.update(rejected=True, rejection=f"{type(error).__name__}: {error}")
            else:
                baseline = results[0]
                if (altered["stop_pc"], altered["pcs_sha256"], altered["writes"]) == \
                        (baseline["stop_pc"], baseline["pcs_sha256"], baseline["writes"]):
                    raise ValueError("mutated AB94 cursor branch survived path/effect comparison")
                mutation.update(rejected=True, rejection="path_or_effect_mismatch",
                                mutated_stop=altered["stop_pc"], mutated_steps=altered["steps"])
            report.update(status="success", slots=len(SLOTS), seeds_per_slot=len(SEEDS),
                          original_executions=len(results),
                          original_game_bytes_executed=True, results=results,
                          mutation_control=mutation,
                          kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA,
                          normalized_workram_sha256=RAM_SHA,
                          probe_sha256=sha(Path(__file__).read_bytes()),
                          interpreter_revision=pinned.INTERPRETER_REVISION,
                          interpreter_sources=pinned.SOURCE_HASHES,
                          static_disassembly_sha256="2aa132ac887fbd15f9e0dc7bc1112edb4960f154e28cbfdc312d8f38be9433b2",
                          contract="AB94 runs from captured frame-1200 WorkRAM-H with captured BDD7C R8-R15/PR/MAC and constructed R0-R7/VBR, calls original AB30, executes A186 from the selected live task row, resumes at AD38 with independently checked restored registers, then stops before AD5C RTS.")
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
