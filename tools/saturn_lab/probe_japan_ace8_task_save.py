#!/usr/bin/env python3
"""Execute ACE8 through its original A164 save and stop at the A186 edge."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg
import probe_japan_a80e_table_update as a80e

BASE, SIZE = a80e.BASE, a80e.SIZE
WRAM, WRAM_SIZE = a80e.WRAM, a80e.WRAM_SIZE
ENTRY, END = 0x0600ACE8, 0x0600AD60
SAVE, SAVE_END = 0x0600A164, 0x0600A186
RESTORE_EDGE = 0x0600A186
RESTORE_END = 0x0600A1AA
RESUME_PC = 0x0600AB94
RESTORE_CONTEXT = 0x060BDD7C
RESTORE_CONTEXT_BYTES = 48
TABLE, ROW_SIZE, ROWS = a80e.TABLE, a80e.ROW_SIZE, a80e.ROWS
TABLE_SIZE = ROW_SIZE * ROWS
SP, LIMIT = 0x06002000, 512
EXIT_NAME = "a186_restore_entry_not_executed"
ALIASES = {0x2600A018: 0x0600A018, 0x2600A01C: 0x0600A01C,
           0x2600A020: 0x0600A020, 0x2600A024: 0x0600A024,
           0x2600A028: 0x0600A028, 0x2600A02C: 0x0600A02C,
           0x2600A044: 0x0600A044}
LITERALS = {0x0600ADA4: (4, 0x2600A020), 0x0600AD9C: (4, 0x2600A044),
            0x0600AD8C: (4, SAVE), 0x0600AD88: (4, 0x060BDD7C),
            0x0600ADA8: (4, RESTORE_EDGE), 0x0600ADAC: (4, 0x2600A028)}
CASES = ((0, 3), (1, 12))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_frame(registers, mach, macl, pr):
    values = {0: registers[8], 4: registers[8], 8: registers[9],
              12: registers[10], 16: registers[11], 20: registers[12],
              24: registers[13], 28: registers[14], 32: registers[15],
              36: pr, 40: mach, 44: macl}
    out = bytearray(48)
    for offset, value in values.items():
        out[offset:offset+4] = (value & 0xFFFFFFFF).to_bytes(4, "big")
    return bytes(out), values


def execute(kernel, ram, emu, slot, row, seed, mutate=False,
            continue_restore=False, mutate_restore=False):
    if (len(kernel) != SIZE or sha(kernel) != a80e.KERNEL_SHA or
            len(ram) != WRAM_SIZE or sha(ram) != a80e.RAM_SHA):
        raise ValueError("original Japan kernel or captured frame-1200 WorkRAM-H differs")
    if slot not in (0, 1) or not 0 <= row < ROWS or seed not in (0, 1):
        raise ValueError("slot, row, or seed outside declared corpus")
    for start, end in ((ENTRY, END), (SAVE, SAVE_END)):
        if ram[start-WRAM:end-WRAM] != kernel[start-BASE:end-BASE]:
            raise ValueError(f"captured code differs from original at {start:08x}")

    work = bytearray(ram)
    # Make the selected table row distinct and put the two task slots on
    # different rows. Only the chosen row and declared global words are writable.
    row_base = TABLE + row * ROW_SIZE
    for i in range(ROW_SIZE):
        work[row_base-WRAM+i] = (0x31 + i * 7 + seed * 13) & 0xFF
    ptr0, ptr1 = TABLE + 3 * ROW_SIZE, TABLE + 12 * ROW_SIZE
    work[0x0600A020-WRAM:0x0600A024-WRAM] = ptr0.to_bytes(4, "big")
    work[0x0600A024-WRAM:0x0600A028-WRAM] = ptr1.to_bytes(4, "big")
    work[0x0600A044-WRAM:0x0600A048-WRAM] = (0xC0DE0000 | (seed << 8) | slot).to_bytes(4, "big")
    work[0x0600A028-WRAM:0x0600A02C-WRAM] = (0xA5000001).to_bytes(4, "big")
    work[0x0600A02C-WRAM:0x0600A030-WRAM] = (0x5A000001).to_bytes(4, "big")
    if mutate:
        work[SAVE-WRAM:SAVE-WRAM+2] = (0x1490).to_bytes(2, "big")
    if mutate_restore:
        work[0x0600A19E-WRAM:0x0600A1A0-WRAM] = (0x504A).to_bytes(2, "big")

    reads, writes, pcs = [], [], []
    at_save = []
    selected_row_start = row_base
    allowed_table = (row_base, row_base + ROW_SIZE)

    class Memory(emu.Memory):
        def translate(self, address, width):
            for alias, physical in ALIASES.items():
                if alias <= address and address + width <= alias + 4:
                    return physical + address - alias
            return address

        def read(self, address, width):
            if self.fetching:
                if width != 2 or address not in allowed_code:
                    raise ValueError(f"ACE8 PC fence {address:08x}/{width}")
                return super().read(address, width)
            translated = self.translate(address, width)
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
            if allowed_table[0] <= address and address + width <= allowed_table[1] and width in (1, 4):
                value = super().read(address, width)
                reads.append(["table", address, width, value])
                return value
            if (continue_restore and RESTORE_CONTEXT <= address and
                    address + width <= RESTORE_CONTEXT + RESTORE_CONTEXT_BYTES and width == 4):
                value = super().read(address, width)
                reads.append(["saved_context", address, width, value])
                return value
            if SP - 32 <= address and address + width <= SP and width == 4:
                value = super().read(address, width)
                reads.append(["stack", address, width, value])
                return value
            raise ValueError(f"unexpected ACE8 read {address:08x}/{width}")

        def write(self, address, width, value):
            value &= 0xFFFFFFFF
            translated = self.translate(address, width)
            if translated != address:
                if width != 4:
                    raise ValueError(f"cache-through alias write width {width}")
                if address not in (0x2600A028 + 4*slot,):
                    raise ValueError(f"ACE8 wrote unselected cache alias {address:08x}")
                writes.append(["cache_alias", address, width, value])
                return super().write(translated, width, value)
            if allowed_table[0] <= address and address + width <= allowed_table[1] and width == 4:
                writes.append(["table", address, width, value])
            elif SP - 32 <= address and address + width <= SP and width == 4:
                writes.append(["stack", address, width, value])
            else:
                raise ValueError(f"unexpected ACE8 write {address:08x}/{width}/{value:08x}")
            return super().write(address, width, value)

    memory = Memory()
    mapped = memory.add(WRAM, WRAM_SIZE, work)
    code_before = {a: bytes(mapped[a-WRAM:b-WRAM]) for a, b in ((ENTRY, END), (SAVE, SAVE_END))}
    restore_code = tuple(range(RESTORE_EDGE, RESTORE_END, 2)) if continue_restore else ()
    allowed_code = CODE + restore_code
    captured_restore_context = bytes(mapped[RESTORE_CONTEXT-WRAM:RESTORE_CONTEXT-WRAM+RESTORE_CONTEXT_BYTES])
    captured_resume = int.from_bytes(captured_restore_context[36:40], "big")
    class CPU(emu.CPU):
        def fetch(self, pc):
            if pc not in allowed_code:
                raise ValueError(f"ACE8 fetch outside scheduler/save ranges {pc:08x}")
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False
        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or pc not in allowed_code:
                raise ValueError(f"ACE8 instruction fence {pc:08x}")
            if pc == SAVE:
                at_save.append({"r": self.r.copy(), "mach": self.mach,
                                "macl": self.macl, "pr": self.pr,
                                "sp": self.r[15]})
            pcs.append(pc)
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0x41000000 + n * 0x0103070B + seed * 0x11111111) & 0xFFFFFFFF for n in range(16)]
    cpu.r[4] = 1                 # A8E8 success path sets R4 to one before ACE8.
    cpu.r[15] = SP
    cpu.sr = 0xF0
    cpu.vbr = 0x06000400 if slot else 0x06000000
    cpu.mach, cpu.macl = 0x10203040 ^ seed, 0xA1B2C3D4 ^ seed
    cpu.pr, cpu.pc = emu.RETURN_SENTINEL, ENTRY
    while cpu.pc in allowed_code:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("ACE8 prefix instruction budget exceeded")
    if len(at_save) != 1:
        raise ValueError("ACE8 did not call A164 exactly once")
    pre = at_save[0]
    expected_frame_bytes, frame_values = expected_frame(pre["r"], pre["mach"], pre["macl"], pre["pr"])
    actual_frame = bytes(mapped[row_base + 32 - WRAM:row_base + 80 - WRAM])
    expected_global = 0xC0DE0000 | (seed << 8) | slot
    got_global = int.from_bytes(mapped[0x0600A044-WRAM:0x0600A048-WRAM], "big")
    ready0 = int.from_bytes(mapped[0x0600A028-WRAM:0x0600A02C-WRAM], "big")
    ready1 = int.from_bytes(mapped[0x0600A02C-WRAM:0x0600A030-WRAM], "big")
    expected_ready = (0xA5000001, 0x5A000001)
    if not mutate and not mutate_restore:
        if actual_frame != expected_frame_bytes:
            raise ValueError("A164 context bytes differ from pre-call register snapshot")
        if (ready0, ready1) != expected_ready:
            raise ValueError("ready words changed before the bounded A186 restore edge")
        if got_global != expected_global:
            raise ValueError("ACE8 task record global field differs")
        if mapped[row_base-WRAM:row_base-WRAM+4] != (1).to_bytes(4, "big") or mapped[row_base-WRAM+4:row_base-WRAM+8] != (1).to_bytes(4, "big"):
            raise ValueError("ACE8 failed to store selected task code/index")
        expected_stop = captured_resume if continue_restore else RESTORE_EDGE
        if cpu.pc != expected_stop or not pcs.count(SAVE):
            raise ValueError("ACE8/A186 did not stop at the expected bounded edge")
        if continue_restore:
            saved = [int.from_bytes(captured_restore_context[o:o+4], "big") for o in range(0, 48, 4)]
            restore_expected = {0: 1, 4: saved[0], 8: saved[1], 9: saved[2],
                                10: saved[3], 11: saved[4], 12: saved[5],
                                13: saved[6], 14: saved[7], 15: saved[8]}
            for reg, value in restore_expected.items():
                if cpu.r[reg] != value:
                    raise ValueError(f"A186 restored R{reg} incorrectly")
            if (cpu.pr, cpu.mach, cpu.macl) != (saved[9], saved[10], saved[11]):
                raise ValueError("A186 restored PR/MACH/MACL incorrectly")
            if cpu.r[4] != saved[0] or cpu.r[0] != 1 or cpu.r[15] != saved[8]:
                raise ValueError("A186 R4/R0/stack return-delay contract differs")
            if bytes(mapped[RESTORE_CONTEXT-WRAM:RESTORE_CONTEXT-WRAM+RESTORE_CONTEXT_BYTES]) != captured_restore_context:
                raise ValueError("A186 modified its captured read-only context")
            resume_off = RESUME_PC - WRAM
            if captured_resume != RESUME_PC or ram[resume_off:resume_off+2] != kernel[RESUME_PC-BASE:RESUME_PC-BASE+2]:
                raise ValueError("captured restore PR does not identify original AB94 bytes")
        elif cpu.pc != RESTORE_EDGE or cpu.r[15] != SP - 16:
            raise ValueError("ACE8 did not stop before A186 with the expected bounded frame")
        if any(code_before[ENTRY][k-ENTRY:k-ENTRY+2] != bytes(mapped[k-WRAM:k-WRAM+2])
               for k in range(ENTRY, END, 2)):
            raise ValueError("ACE8 unexpectedly modified its caller code window")
    return {"slot": slot, "row": row, "seed": seed, "vbr": hex(cpu.vbr),
            "steps": cpu.steps, "pc_stop": hex(cpu.pc),
            "stop_reason": "ab94_resume_target_not_executed" if continue_restore else EXIT_NAME,
            "a164_calls": len(at_save), "a186_executed": RESTORE_EDGE in pcs,
            "stack_at_edge": hex(cpu.r[15]), "saved_context_sha256": sha(actual_frame),
            "expected_context_sha256": sha(expected_frame_bytes),
            "saved_context_matches_pre_call_registers": actual_frame == expected_frame_bytes,
            "saved_context_values": {str(k): hex(v) for k, v in frame_values.items()},
            "task_code_and_index": [hex(int.from_bytes(mapped[row_base-WRAM+i:row_base-WRAM+i+4], "big")) for i in (0, 4)],
            "global_field": hex(got_global), "ready_words": [hex(ready0), hex(ready1)],
            "captured_restore_context_sha256": sha(captured_restore_context),
            "captured_restore_context_pr": hex(captured_resume),
            "original_bytes_execution": not mutate and not mutate_restore,
            "reads": reads, "writes": writes, "pc_visits": len(pcs), "mutation": mutate}


CODE = tuple(range(ENTRY, END, 2)) + tuple(range(SAVE, SAVE_END, 2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-ace8-task-save-prefix.v1", "status": "failure",
              "entry": hex(ENTRY), "stop": hex(RESTORE_EDGE),
              "limits": ["Constructed task rows, VBR-selected pointers, cache-through words and registers",
                         "Executes ACE8 and A164 through the A186 entry boundary; A186 restore body is not executed",
                         "No natural task scheduling, device effects, timing, gameplay or full-game claim"]}
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
                emu = pinned.interpreter(args.saturn_recomp)
                results = []
                for slot, row in CASES:
                    pair = [execute(kernel, ram, emu, slot, row, seed) for seed in (0, 1)]
                    if pair[0]["saved_context_sha256"] == pair[1]["saved_context_sha256"]:
                        raise ValueError("seeded context rows unexpectedly identical")
                    results.append({"slot": slot, "row": row, "runs": pair})
                handoffs = []
                for slot, row in CASES:
                    pair = [execute(kernel, ram, emu, slot, row, seed, continue_restore=True)
                            for seed in (0, 1)]
                    if any(run["pc_stop"] != hex(RESUME_PC) or not run["a186_executed"] for run in pair):
                        raise ValueError("ACE8/A186 composition did not reach captured AB94 PR")
                    handoffs.append({"slot": slot, "row": row, "runs": pair})
                control = execute(kernel, ram, emu, 0, 3, 0, continue_restore=True, mutate_restore=True)
                if control["pc_stop"] == hex(RESUME_PC):
                    raise ValueError("mutated A186 PR load survived resume-target control")
                context_control = execute(kernel, ram, emu, 0, 3, 0, mutate=True)
                if context_control["saved_context_matches_pre_call_registers"]:
                    raise ValueError("mutated A164 store survived saved-context control")
                report.update(status="success", cases=len(results), executions_per_case=2,
                              prefix_original_executions=sum(len(row["runs"]) for row in results),
                              restore_handoff_original_executions=sum(len(row["runs"]) for row in handoffs),
                              total_original_executions=sum(len(row["runs"]) for row in results + handoffs),
                              original_game_bytes_executed=True, results=results,
                              composed_restore_handoffs=handoffs,
                              mutation_control={"pc": hex(SAVE), "original": "0x1480", "replacement": "0x1490",
                                                "pre_call_frame_rejected": True},
                              restore_mutation_control={"pc": "0x0600A19E", "original": "0x5049",
                                                        "replacement": "0x504A", "resume_target_rejected": True},
                              kernel_sha256=a80e.KERNEL_SHA, state_sha256=a80e.STATE_SHA,
                              normalized_workram_sha256=a80e.RAM_SHA,
                              probe_sha256=sha(Path(__file__).read_bytes()),
                              interpreter_revision=pinned.INTERPRETER_REVISION,
                              interpreter_sources=pinned.SOURCE_HASHES,
                              contract="ACE8 stores R4 into the VBR-selected task row, saves the caller context through A164, follows the zero-return delay slot into A186, restores the captured frame at BDD7C and transfers to its PR AB94. The probe stops before executing AB94.")
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
