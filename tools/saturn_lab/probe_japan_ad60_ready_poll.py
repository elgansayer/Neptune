#!/usr/bin/env python3
"""Execute original Japan AD60's VBR-selected ready poll."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import probe_kernel as pinned
import state_graphics as sg

BASE, SIZE = 0x0600A000, 786432
WRAM, WRAM_SIZE = 0x06000000, 0x100000
ENTRY, END = 0x0600AD60, 0x0600AD7A
ACE8 = 0x0600ACE8
LITERAL, ALIAS = 0x0600ADAC, 0x2600A028
SP, LIMIT = 0x06002000, 64
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
RAM_SHA = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
CORE_SHA = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
SLOTS, READY_VALUES, SEEDS = (0, 1), (0, 1), (0, 1)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def execute(kernel, ram, emu, slot, ready, seed, mutate=False):
    if len(kernel) != SIZE or sha(kernel) != KERNEL_SHA:
        raise ValueError("original Japan kernel identity differs")
    if len(ram) != WRAM_SIZE or sha(ram) != RAM_SHA:
        raise ValueError("captured frame-1200 WorkRAM-H identity differs")
    if ram[ENTRY-WRAM:END-WRAM] != kernel[ENTRY-BASE:END-BASE]:
        raise ValueError("captured AD60 bytes differ from original source")
    if slot not in SLOTS or ready not in READY_VALUES or seed not in SEEDS:
        raise ValueError("slot, ready value, or seed outside declared corpus")
    vbr = 0x06000000 + slot * 0x400
    selected_alias = ALIAS + slot * 4
    selected_phys = selected_alias - 0x20000000
    work = bytearray(ram)
    work[selected_phys-WRAM:selected_phys-WRAM+4] = ready.to_bytes(4, "big")
    if mutate:
        work[0x0600AD70-WRAM:0x0600AD72-WRAM] = (0x8B01).to_bytes(2, "big")
    reads, writes, pcs = [], [], []

    class Memory(emu.Memory):
        def read(self, address, width):
            if self.fetching:
                if width != 2 or not ENTRY <= address < END or address & 1:
                    raise ValueError(f"AD60 PC fence {address:08x}/{width}")
                return super().read(address, width)
            if address == LITERAL and width == 4:
                value = super().read(address, width)
                reads.append(["literal", address, width, value])
                return value
            if address == selected_alias and width == 4:
                value = super().read(selected_phys, width)
                reads.append(["selected_ready_alias", address, width, value])
                return value
            raise ValueError(f"unexpected AD60 read {address:08x}/{width}")

        def write(self, address, width, value):
            writes.append([address, width, value & 0xFFFFFFFF])
            raise ValueError(f"AD60 write forbidden {address:08x}/{width}")

    memory = Memory()
    memory.add(WRAM, WRAM_SIZE, work)

    class CPU(emu.CPU):
        def fetch(self, pc):
            if not ENTRY <= pc < END or pc & 1:
                raise ValueError(f"AD60 fetch escaped bounded helper {pc:08x}")
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, instruction, pc, in_slot=False):
            if self.steps >= LIMIT or not ENTRY <= pc < END:
                raise ValueError(f"AD60 instruction fence {pc:08x}")
            pcs.append(pc)
            return super().exec(instruction, pc, in_slot=in_slot)

        def step(self):
            if self.pc == ACE8:
                self.stop_pc = self.pc
                self.pc = emu.RETURN_SENTINEL
                return
            return super().step()

    cpu = CPU(memory)
    cpu.r = [(0x73000000 + i * 0x0103070B + seed * 0x11111111) & 0xFFFFFFFF for i in range(16)]
    cpu.r[15] = SP
    cpu.vbr, cpu.pr, cpu.pc = vbr, emu.RETURN_SENTINEL, ENTRY
    before_r, before_pr = cpu.r.copy(), cpu.pr
    while cpu.pc != emu.RETURN_SENTINEL:
        cpu.step()
        if cpu.steps > LIMIT:
            raise ValueError("AD60 instruction budget exceeded")
    stop = getattr(cpu, "stop_pc", cpu.pc)
    expected_stop = ACE8 if ready or mutate else emu.RETURN_SENTINEL
    if stop != expected_stop:
        raise ValueError(f"AD60 wrong branch target {stop:08x}; expected {expected_stop:08x}")
    if cpu.r[15] != SP or cpu.pr != before_pr:
        raise ValueError("AD60 changed SP or PR")
    expected_r = before_r.copy()
    expected_r[0] = slot * 4
    expected_r[1] = ready
    if ready or mutate:
        expected_r[4] = 1
    if cpu.r != expected_r:
        raise ValueError("AD60 register changes differ from the selected branch model")
    if ready and cpu.r[4] != 1:
        raise ValueError("AD60 ready delay slot failed to set R4=1")
    if writes:
        raise ValueError("AD60 unexpectedly wrote memory")
    return {"slot": slot, "ready": ready, "seed": seed, "vbr": hex(vbr),
            "stop_pc": hex(stop), "steps": cpu.steps, "pc_visits": pcs,
            "r4_after": hex(cpu.r[4]), "r0_after": hex(cpu.r[0]),
            "sp_after": hex(cpu.r[15]), "pr_after": hex(cpu.pr),
            "reads": reads, "writes": writes,
            "original_bytes_executed": not mutate, "mutated": mutate}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args(argv)
    report = {"schema": "neptune.original-japan-ad60-ready-poll.v1", "status": "failure",
              "entry": hex(ENTRY), "code_range": [hex(ENTRY), hex(END)],
              "limits": ["Constructed ready words, VBR slot, and registers; captured frame-1200 WorkRAM-H base",
                         "Exact selected cache-through alias; zero returns, nonzero stops at ACE8 before execution",
                         "No ready-word provenance, natural caller, device timing, gameplay, or full-game claim"]}
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
                for ready in READY_VALUES:
                    pair = [execute(kernel, ram, emu, slot, ready, seed) for seed in SEEDS]
                    if (pair[0]["stop_pc"], pair[0]["steps"], pair[0]["r0_after"],
                            pair[0]["reads"]) != \
                            (pair[1]["stop_pc"], pair[1]["steps"], pair[1]["r0_after"],
                             pair[1]["reads"]):
                        raise ValueError(f"AD60 seeds differ for slot {slot} ready={ready}")
                    results.extend(pair)
            altered = execute(kernel, ram, emu, 0, 0, 0, mutate=True)
            if altered["stop_pc"] == hex(emu.RETURN_SENTINEL):
                raise ValueError("mutated AD60 ready branch survived zero-ready control")
            report.update(status="success", cases=len(results), original_executions=len(results),
                          results=results, mutation_control={"pc":"0x0600AD70","original":"0x8901",
                          "replacement":"0x8B01","zero_ready_rejected":True,
                          "mutated_stop":altered["stop_pc"]},
                          original_game_bytes_executed=True, kernel_sha256=KERNEL_SHA,
                          state_sha256=STATE_SHA, normalized_workram_sha256=RAM_SHA,
                          probe_sha256=sha(Path(__file__).read_bytes()),
                          interpreter_revision=pinned.INTERPRETER_REVISION,
                          interpreter_sources=pinned.SOURCE_HASHES,
                          contract="AD60 selects one ready word using VBR bit 2. Zero returns without register/memory changes; any nonzero value sets R4 to one in the BRA delay slot and transfers to ACE8. The probe stops before ACE8 executes.")
        except Exception as error:
            report["error"] = {"type": type(error).__name__, "reason": str(error)}
        out.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
