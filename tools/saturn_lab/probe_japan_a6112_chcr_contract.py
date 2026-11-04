#!/usr/bin/env python3
"""Execute original A6112 against the documented SH7604 CHCR register contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import probe_kernel as pinned
import state_graphics as sg

BASE, KERNEL_SIZE = 0x0600A000, 786432
KERNEL_SHA = "23685e15fb4f0c49d16859b4e5bbb6ded619611f99ac830e8c93a00590ca44fb"
CORE_SHA = "c862380e94ba749e020e58ba5b2ec483f88a60ced38171fc63fda306b2f54f5e"
STATE_SHA = "c115d4b4da8a24f62834235456263465d9bc2c1b8d4ab0deecb7784c1afe8f2f"
RAM_SHA = "3cdda8bc44460237fd86948ef5dabb548c95c8fe1149b15e647178339c81efff"
WORKRAM_BASE, WORKRAM_SIZE = 0x06000000, 0x100000
ENTRY, END = 0x060A6112, 0x060A6124
CHCR = {0: 0xFFFFFF8C, 1: 0xFFFFFF9C}
CHCR_DE, CHCR_TE = 1, 2
EXPECTED_PCS = tuple(range(ENTRY, END, 2))
VALUES = tuple(range(256)) + tuple((1 << bit) | de for bit in range(8, 16) for de in (0, 1))
STATE_MAX, LIMIT = 16 * 1024 * 1024, 32


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def corpus():
    return [(channel, value) for channel in (0, 1) for value in VALUES]


class PCFence(ValueError):
    pass


class CHCRContractMemory:
    """Explicit CHCR state contract; this does not run the DMA engine."""
    def __init__(self, emu, channel: int, value: int):
        self.mem = emu.Memory()
        self.register_address = CHCR[channel]
        self.register_value = value & 0xFFFF
        self.events = []
        self.fetching = False

    def add(self, address, size, data):
        return self.mem.add(address, size, data)

    def read(self, address, size):
        if self.fetching:
            if size != 2 or address not in EXPECTED_PCS:
                raise PCFence(f"A6112 PC fence at {address:08x}/{size}")
            return self.mem.read(address, size)
        if address == self.register_address and size == 4:
            value = self.register_value
            self.events.append(["read", address, size, value])
            return value
        raise ValueError(f"unexpected A6112 contract read: {address:08x}/{size}")

    def write(self, address, size, value):
        if address != self.register_address or size != 4:
            raise ValueError(f"unexpected A6112 contract write: {address:08x}/{size}")
        value &= 0xFFFFFFFF
        old = self.register_value
        if value & 0xFFFF0000:
            raise ValueError("CHCR upper sixteen bits must remain zero")
        # SH7604 CHCR.TE (bit 1) is cleared only by writing zero. The A6112
        # mask leaves TE unchanged, while DE (bit 0) is ordinary read/write.
        te = (old & CHCR_TE) if value & CHCR_TE else 0
        self.register_value = (value & ~CHCR_TE) | te
        self.events.append(["write", address, size, value, self.register_value])


def execute(kernel: bytes, emu, channel: int, value: int):
    if channel not in CHCR or type(value) is not int or not 0 <= value <= 0xFFFF:
        raise ValueError("A6112 channel/value is outside the declared CHCR contract")
    memory = CHCRContractMemory(emu, channel, value)
    memory.add(BASE, KERNEL_SIZE, kernel)

    class CPU(emu.CPU):
        def fetch(self, pc):
            memory.fetching = True
            try:
                return super().fetch(pc)
            finally:
                memory.fetching = False

        def exec(self, ins, pc, in_slot=False):
            if self.steps >= LIMIT or pc not in EXPECTED_PCS:
                raise PCFence(f"A6112 PC/budget fence at {pc:08x}")
            return super().exec(ins, pc, in_slot=in_slot)

    cpu = CPU(memory)
    cpu.r = [(0xA5000000 + reg * 0x00010203) & 0xFFFFFFFF for reg in range(16)]
    cpu.r[0] = 0x13579BDF
    cpu.r[4] = channel
    initial_r0 = cpu.r[0]
    expected = value & ~CHCR_DE
    result = cpu.call(ENTRY, max_steps=LIMIT)
    if cpu.r[4] != expected or memory.register_value != expected:
        raise ValueError(f"A6112 CHCR result differs: {cpu.r[4]:08x}/{memory.register_value:08x}/{expected:08x}")
    if result != initial_r0 or cpu.r[0] != initial_r0:
        raise ValueError("A6112 unexpectedly changed R0")
    if cpu.steps != len(EXPECTED_PCS) or len(memory.events) != 2:
        raise ValueError("A6112 exact step or MMIO event count differs")
    if memory.events != [["read", CHCR[channel], 4, value],
        ["write", CHCR[channel], 4, expected, expected]]:
        raise ValueError(f"A6112 CHCR event trace differs: {memory.events!r}")
    return {"channel": channel, "chcr_before": value, "chcr_after": memory.register_value,
        "r4_return": cpu.r[4], "r0_preserved": cpu.r[0], "events": memory.events,
        "steps": cpu.steps}


def run_pair(kernel, emu, values):
    first = execute(kernel, emu, *values)
    second = execute(kernel, emu, *values)
    if first != second:
        raise ValueError(f"repeated A6112 execution differs: {values!r}")
    return first


def mutation_control(kernel: bytes, emu, channel: int):
    mutated = bytearray(kernel)
    # Original 0xE3FE is MOV #-2,R3; E3FF leaves DE set after AND.
    offset = 0x060A6114 - BASE + 1
    if mutated[offset] != 0xFE:
        raise ValueError("A6112 immediate mutation site differs from original")
    mutated[offset] = 0xFF
    try:
        execute(bytes(mutated), emu, channel, CHCR_DE)
    except ValueError as error:
        if "result differs" not in str(error):
            raise
        return True
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "state", "checkpoint", "saturn-recomp", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": "neptune.original-japan-a6112-chcr-contract.v1", "status": "failure",
        "entry": hex(ENTRY), "code_range": [hex(ENTRY), hex(END)],
        "register_contract": {"CHCR0": hex(CHCR[0]), "CHCR1": hex(CHCR[1]),
            "DE_bit": 0, "TE_bit": 1, "access_size": 4, "dma_engine_executed": False},
        "limits": ["Original A6112 instructions with explicit SH7604 CHCR state contract",
            "No DMA transfer/timing or natural game-time register values claimed"]}
    try:
        with args.report.open("x", encoding="utf-8") as output:
            try:
                metadata = json.loads(args.checkpoint.read_text())
                identity = metadata.get("identity", {})
                if metadata.get("frame") != 1200 or identity.get("core_sha256") != CORE_SHA:
                    raise ValueError("frame-1200 checkpoint/core identity differs")
                state = pinned.read_bounded(args.state, STATE_MAX)
                if sha(state) != STATE_SHA or metadata.get("state_sha256") != STATE_SHA:
                    raise ValueError("frame-1200 state identity differs")
                kernel = pinned.read_bounded(args.kernel, KERNEL_SIZE)
                if len(kernel) != KERNEL_SIZE or sha(kernel) != KERNEL_SHA:
                    raise ValueError("original Japan kernel identity mismatch")
                parsed = sg.parse(state)
                raw = sg.field(parsed, "MAIN", "WorkRAMH", WORKRAM_SIZE)
                ram = sg.cpu_words(raw, "little")
                if sha(ram) != RAM_SHA or ram[ENTRY - WORKRAM_BASE:END - WORKRAM_BASE] != kernel[ENTRY - BASE:END - BASE]:
                    raise ValueError("A6112 bytes differ from original frame-1200 WorkRAM-H")
                emu = pinned.interpreter(args.saturn_recomp)
                rows = [run_pair(kernel, emu, values) for values in corpus()]
                controls = {str(channel): mutation_control(kernel, emu, channel) for channel in (0, 1)}
                if not all(controls.values()):
                    raise ValueError("A6112 changed-AND mutation control escaped")
                data = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                report.update(status="success", original_game_bytes_executed=True,
                    captured_snapshot_data_used=True, cases=len(rows), executions_per_case=2,
                    results=rows, results_sha256=sha(data), mutation_controls=controls,
                    source_code_sha256=sha(kernel[ENTRY - BASE:END - BASE]),
                    kernel_sha256=KERNEL_SHA, state_sha256=STATE_SHA,
                    normalized_workram_sha256=RAM_SHA,
                    probe_sha256=sha(Path(__file__).read_bytes()),
                    interpreter_revision=pinned.INTERPRETER_REVISION,
                    interpreter_sources=pinned.SOURCE_HASHES,
                    contract="A6112 selects SH7604 CHCR0 for R4=0 and CHCR1 for R4=1, reads the 32-bit register, clears DE bit 0, writes the result in the RTS delay slot, returns that value in R4, and preserves TE bit 1 under its write-zero-to-clear rule. Register state is a constructed contract fixture; no transfer engine or timing is simulated.")
            except Exception as error:
                report["error"] = {"type": type(error).__name__, "reason": str(error)}
            output.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError as error:
        print(f"FAIL: fresh report path required: {error}")
        return 1
    print(json.dumps({"status": report["status"], "cases": report.get("cases", 0), "report": str(args.report)}))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
