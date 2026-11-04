#!/usr/bin/env python3
"""Exercise bounded original AB94 task-row eligibility states from caller-derived input."""
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
RESUME, STOP = 0x0600AD38, 0x060BCC80
ACE8, ACE8_END = 0x0600ACE8, 0x0600AD60
CONTEXT, CONTEXT_SIZE = 0x060BDD7C, 48
SP, LIMIT = 0x060BD8F4, 8192
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
STACK_WINDOWS = ((SP - 256, SP + 64), (0x060BCC6C - 256, 0x060BCC6C + 64),
                 (0x060BE18C - 256, 0x060BE18C + 64),
                 (0x06002000 - 256, 0x06002000 + 64))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(kernel, ram, emu, slot, seed, mutate=False, caller=None, candidate=None):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA:
        raise ValueError("original Japan kernel identity differs")
    if len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("captured frame-1200 WorkRAM-H identity differs")
    if ram[ENTRY-WRAM:END-WRAM] != kernel[ENTRY-BASE:END-BASE]:
        raise ValueError("captured AB94 continuation differs from original bytes")
    if ram[AB30-WRAM:AB30_END-WRAM] != kernel[AB30-BASE:AB30_END-BASE]:
        raise ValueError("captured AB30 callee differs from original bytes")
    for code_start, code_end in ((RESTORE, RESTORE_END), (ACE8, ACE8_END)):
        if ram[code_start-WRAM:code_end-WRAM] != kernel[code_start-BASE:code_end-BASE]:
            raise ValueError(f"captured A186/ACE8 code differs from original at {code_start:08x}")
    if slot not in SLOTS or seed not in SEEDS:
        raise ValueError("VBR slot or register seed outside declared set")
    vbr = 0x06000000 + slot * 0x400

    work = bytearray(ram)
    if caller is None or caller.get("pc_stop") != hex(ENTRY):
        raise ValueError("caller record does not stop at original AB94")
    for kind, address, width, value in caller["writes"]:
        if kind not in ("stack", "task_row", "cache_alias"):
            raise ValueError(f"unsupported A208 write class {kind}")
        physical = address - 0x20000000 if kind == "cache_alias" else address
        if physical < WRAM or physical + width > WRAM + WRAM_SIZE:
            raise ValueError(f"replayed A208 write outside WorkRAM-H {address:08x}/{width}")
        work[physical-WRAM:physical-WRAM+width] = (value & ((1 << (8*width))-1)).to_bytes(width, "big")
    if candidate is not None:
        index, state = candidate
        if index not in range(COUNT) or state not in (0, 1, 2, 3):
            raise ValueError("candidate row/state outside bounded matrix")
        row = TABLE + index * ROW_SIZE
        work[row-WRAM:row-WRAM+4] = (1).to_bytes(4, "big")
        work[row+80-WRAM] = state
    if mutate:
        work[0x0600ABCC-WRAM:0x0600ABCE-WRAM] = (0x8800).to_bytes(2, "big")
    reads, writes, pcs = [], [], []
    code_ranges = ((ENTRY, END), (AB30, AB30_END), (RESTORE, RESTORE_END), (ACE8, ACE8_END))

    class Memory(emu.Memory):
        def translate(self, address, width):
            for alias, physical in ALIASES.items():
                if alias <= address and address + width <= alias + 4:
                    return physical + address - alias
            return address

        def read(self, address, width):
            if self.fetching:
                if width != 2 or not any(lo <= address < hi for lo, hi in code_ranges) or address & 1:
                    raise ValueError(f"AB94/AB30/ACE8 PC fence {address:08x}/{width}")
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
                raise ValueError(f"AB94/AB30/ACE8 fetch escaped bounded code {pc:08x}")
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= LIMIT or not any(lo <= pc < hi for lo, hi in code_ranges):
                raise ValueError(f"AB94/AB30/ACE8 instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

        def step(self):
            if self.steps >= LIMIT - 1:
                self.stop_pc = self.pc
                self.budget_exhausted = True
                self.pc = emu.RETURN_SENTINEL
                return
            if self.pc == RESTORE:
                self.restore_entry = {"r": self.r.copy(), "pr": self.pr,
                                      "mach": self.mach, "macl": self.macl}
            if self.pc == RESUME:
                self.resume_registers = self.r.copy()
                self.resume_special = (self.pr, self.mach, self.macl)
            if self.pc == STOP or not any(lo <= self.pc < hi for lo, hi in code_ranges):
                self.stop_pc = self.pc
                self.pc = emu.RETURN_SENTINEL
                return
            if self.pc == emu.RETURN_SENTINEL:
                return
            return super().step()

    cpu = CPU(memory)
    if caller["slot"] != slot or caller["seed"] != seed:
        raise ValueError("A208 caller slot/seed does not match this continuation")
    cpu.r = [int(value, 16) for value in caller["registers_at_ab94"]]
    special = caller["special_at_ab94"]
    cpu.vbr = int(special["vbr"], 16)
    cpu.pr, cpu.mach, cpu.macl = (int(special[key], 16) for key in ("pr", "mach", "macl"))
    cpu.pc = ENTRY
    initial_registers = cpu.r.copy()
    while cpu.pc != emu.RETURN_SENTINEL:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("AB94/AD38 return instruction budget exceeded")
    if not hasattr(cpu, "stop_pc"):
        raise ValueError(f"AB94/A186/AD38 did not reach a bounded-code boundary; pc={cpu.pc:08x}")
    restore_validated = hasattr(cpu, "restore_entry") and hasattr(cpu, "resume_registers")
    frame = None
    if restore_validated:
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
    return {"slot": slot, "seed": seed, "vbr": hex(vbr), "start_registers": [hex(v) for v in initial_registers],
            "stop_pc": hex(cpu.stop_pc), "expected_stop_pc": hex(STOP), "restore_entry_pc": hex(RESTORE),
            "restored_resume_pc": hex(RESUME) if restore_validated else None,
            "restored_context_pointer": hex(frame) if frame is not None else None,
            "restored_context_sha256": sha(bytes(mapped[frame-WRAM:frame-WRAM+CONTEXT_SIZE])) if frame is not None else None,
            "a186_restore_matches_selected_frame": restore_validated,
            "stop_before_return_instruction": cpu.stop_pc == STOP,
            "steps": cpu.steps, "budget_exhausted": getattr(cpu, "budget_exhausted", False), "pc_visits": len(pcs),
            "pcs_sha256": sha(b"".join(pc.to_bytes(4, "big") for pc in pcs)),
            "pc_tail": [hex(pc) for pc in pcs[-16:]],
            "reads": reads, "writes": writes,
            "registers_at_handoff": [hex(v) for v in cpu.r],
            "pr_at_handoff": hex(cpu.pr), "sp_at_handoff": hex(cpu.r[15]),
            "original_bytes_executed": not mutate, "mutated": mutate,
            "caller_derived_registers": True, "prefix_writes_replayed": len(caller["writes"]),
            "candidate_row_state": list(candidate) if candidate is not None else None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report", "caller-report"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-ab94-row-scan-cases.v1", "status": "failure",
              "entry": hex(ENTRY), "stop": hex(STOP), "caller_tail": [hex(ACE8), hex(ACE8_END)],
              "limits": ["A208 registers and bounded writes replayed into a separate CPU instance; R6/R7 remain seeded",
                         "Constructed candidate row0 first-word/+80 states test original branch behavior; no natural task-state transition claim",
                         "Stops at first PC outside bounded AB94/AB30/A186/ACE8 or the 8192 instruction budget"]}
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
            caller_report = json.loads(args.caller_report.read_text())
            if (caller_report.get("schema") != "neptune.original-japan-a208-ae3a-ab94-resume.v1" or
                    caller_report.get("status") != "success" or
                    caller_report.get("source_kernel_sha256") != KERNEL_SHA or
                    caller_report.get("state_sha256") != STATE_SHA):
                raise ValueError("A208 caller report identity/status differs")
            caller_rows = {row["seed"]: row for row in caller_report["results"]
                           if row["slot"] == 0 and row.get("original_bytes_executed")}
            if set(caller_rows) != set(SEEDS):
                raise ValueError("A208 caller report lacks original slot-0 seed rows")
            results = [execute(kernel, ram, emu, 0, seed, caller=caller_rows[seed]) for seed in SEEDS]
            candidates = [execute(kernel, ram, emu, 0, 0, caller=caller_rows[0], candidate=(0, state))
                          for state in (0, 1, 2, 3)]
            results.extend(candidates)
            mutation = {"pc": "0x0600ABCC", "original": "0x88FF", "replacement": "0x8800"}
            try:
                altered = execute(kernel, ram, emu, 0, 0, mutate=True, caller=caller_rows[0])
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
                          original_executions=len(results), candidate_cases=len(candidates),
                          original_game_bytes_executed=True, results=results,
                          mutation_control=mutation,
                          caller_report_sha256=sha(args.caller_report.read_bytes()),
                          kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA,
                          normalized_workram_sha256=RAM_SHA,
                          probe_sha256=sha(Path(__file__).read_bytes()),
                          interpreter_revision=pinned.INTERPRETER_REVISION,
                          interpreter_sources=pinned.SOURCE_HASHES,
                          static_disassembly_sha256="2aa132ac887fbd15f9e0dc7bc1112edb4960f154e28cbfdc312d8f38be9433b2",
                          contract="AB94 runs from caller registers and prefix write events captured by the A208 report, replayed into a new CPU/memory instance; it calls original AB30, executes A186 from the selected task row, resumes at AD38, and stops at the first PC outside bounded code or the instruction budget. A budget stop records a bounded repeating continuation, not a completed return. This does not establish same-instance caller continuation.")
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("original_executions", report.get("cases", 0)), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
