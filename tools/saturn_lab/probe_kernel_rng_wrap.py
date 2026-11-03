#!/usr/bin/env python3
"""Resume the original USA kernel's bounded RNG draw through its table refresh.

Each invocation executes at most 512 SH-2 instructions and saves a resumable
private CPU/RAM checkpoint. This is an explicit constructed index-55 call, not
natural gameplay or RNG-seed/call-order evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_kernel as pinned
import state_graphics

BASE = 0x06000000
ENTRY = 0x0600A0EC
NEXT_ENTRY = 0x0600A08C
REFRESH_ENTRY = 0x06009FA8
INDEX = 0x060BF4F4
TABLE_BASE = 0x060BF4F8
TABLE_WRITE_START = 0x060BF4FC
TABLE_END = 0x060BF5D8
SELECTED_WORD = 0x060BF5D4
STACK = 0x060FF000
WINDOW = 512
MAX_WINDOWS = 16
ALLOW = (
    (NEXT_ENTRY, 0x0600A0B4),
    (ENTRY, 0x0600A10E),
    (REFRESH_ENTRY, NEXT_ENTRY),
)
DEFAULT_CHECKPOINT = Path(
    "/home/dev/neptune-research-private/707/reference-window-frame1200-1800/capture/checkpoint.json"
)
DEFAULT_KERNEL = Path("/home/dev/neptune-research-private/483/0KRNL.BIN")
DEFAULT_INTERPRETER = Path("/home/dev/neptune-tools/saturn-recomp-f20de94")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checkpoint_ram(checkpoint: Path) -> tuple[dict, bytes]:
    metadata = json.loads(pinned.read_bounded(checkpoint, 2 * 1024**2))
    relative = Path(metadata["state_path"])
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
        raise ValueError("Checkpoint state path must be a sibling filename")
    state = pinned.read_bounded(checkpoint.parent / relative, state_graphics.MAX_STATE)
    if len(state) != metadata["state_bytes"] or sha(state) != metadata["state_sha256"]:
        raise ValueError("Checkpoint state size/digest mismatch")
    parsed = state_graphics.parse(state)
    ram = state_graphics.cpu_words(
        state_graphics.field(parsed, "MAIN", "WorkRAMH", 0x100000), "little"
    )
    return metadata, ram


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, default=DEFAULT_KERNEL)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--saturn-recomp", type=Path, default=DEFAULT_INTERPRETER)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="resume one saved 512-instruction window")
    args = parser.parse_args()

    kernel = pinned.kernel_bytes(args.kernel)
    checkpoint, initial = checkpoint_ram(args.checkpoint)
    if int.from_bytes(initial[INDEX - BASE:INDEX - BASE + 4], "big") != 55:
        raise ValueError("Expected captured checkpoint index 55")
    selected_before = int.from_bytes(
        initial[SELECTED_WORD - BASE:SELECTED_WORD - BASE + 4], "big"
    )
    source_ranges = (
        (NEXT_ENTRY, 0x0600A0B4),
        (ENTRY, 0x0600A10E),
        (REFRESH_ENTRY, NEXT_ENTRY),
        (0x0600A4B0, 0x0600A4F0),
    )
    for start, end in source_ranges:
        if initial[start - BASE:end - BASE] != kernel[start - pinned.BASE:end - pinned.BASE]:
            raise ValueError(f"Original code residency mismatch at 0x{start:08x}")

    emu = pinned.interpreter(args.saturn_recomp)

    class Memory(emu.Memory):
        def __init__(self) -> None:
            super().__init__()
            self.writes: list[list[int]] = []

        def write(self, address: int, size: int, value: int) -> None:
            address &= 0xFFFFFFFF
            allowed = (
                (address == INDEX and size == 4)
                or (TABLE_WRITE_START <= address and address + size <= TABLE_END)
                or (STACK - 0x100 <= address and address + size <= STACK)
            )
            if not allowed:
                raise ValueError(f"Unexpected write at 0x{address:08x}/{size}")
            self.writes.append([address, size, value & ((1 << (8 * size)) - 1)])
            return super().write(address, size, value)

    class CPU(emu.CPU):
        def __init__(self, memory: Memory) -> None:
            super().__init__(memory)
            self.trace: list[list[object]] = []

        def exec(self, instruction, pc: int, in_slot: bool = False):
            if not any(start <= pc < end for start, end in ALLOW):
                raise ValueError(f"Original instruction escaped inspected code at 0x{pc:08x}")
            self.trace.append([pc, instruction.word, instruction.op, bool(in_slot)])
            return super().exec(instruction, pc, in_slot)

    memory = Memory()
    if args.resume:
        previous = json.loads(args.report.read_text())
        expected_identity = (sha(kernel), checkpoint["state_sha256"], pinned.INTERPRETER_REVISION)
        found_identity = (
            previous["kernel_sha256"],
            previous["checkpoint_state_sha256"],
            previous["interpreter_revision"],
        )
        if found_identity != expected_identity:
            raise ValueError("Resume report does not match original/kernel/interpreter identity")
        raw = (args.report.parent / "ram.bin").read_bytes()
        if len(raw) != 0x100000 or sha(raw) != previous["ram_sha256"]:
            raise ValueError("Resumable RAM snapshot identity mismatch")
        if (len(previous["windows"]) >= MAX_WINDOWS or previous["returned"]
                or previous["windows"][-1]["escaped_pc"] is not None
                or previous["windows"][-1]["error"] is not None):
            raise ValueError("Resume window limit reached or call already returned")
        backing = memory.add(BASE, len(raw), raw)
        state = previous["cpu"]
        cpu = CPU(memory)
        cpu.r[:] = [int(value, 16) for value in state["r"]]
        for name in ("sr", "pr", "gbr", "vbr", "mach", "macl", "pc"):
            setattr(cpu, name, int(state[name], 16))
        cpu.steps = state["steps"]
        prior_instructions = previous["instructions"]
        prior_writes = previous["writes"]
        prior_windows = previous["windows"]
        previous_ram = raw
    else:
        if args.report.exists():
            raise ValueError("Report already exists; choose a fresh path or use --resume")
        backing = memory.add(BASE, len(initial), initial)
        memory.write(INDEX, 4, 55)  # Construct the predecessor that causes the index-55 refresh.
        memory.writes.clear()
        cpu = CPU(memory)
        cpu.r[15] = STACK
        cpu.r[4] = 10
        cpu.pr = emu.RETURN_SENTINEL
        cpu.pc = ENTRY
        prior_instructions = []
        prior_writes = []
        prior_windows = []
        previous_ram = initial

    memory.writes.clear()
    cpu.trace.clear()
    window_start = cpu.steps
    escaped = None
    returned = False
    error = None
    started = time.monotonic()
    try:
        while len(cpu.trace) < WINDOW:
            if cpu.pc == emu.RETURN_SENTINEL:
                returned = True
                break
            if not any(start <= cpu.pc < end for start, end in ALLOW):
                escaped = cpu.pc
                break
            instruction = cpu.fetch(cpu.pc)
            instruction_cost = 2 if instruction.delay else 1
            if len(cpu.trace) + instruction_cost > WINDOW:
                break
            cpu.step()
        if cpu.pc == emu.RETURN_SENTINEL:
            returned = True
    except Exception as exc:  # retain original faults instead of substituting semantics
        error = f"{type(exc).__name__}: {exc}"

    ram = bytes(backing)
    index_after = int.from_bytes(ram[INDEX - BASE:INDEX - BASE + 4], "big")
    table_word_after = int.from_bytes(
        ram[TABLE_BASE + 4 - BASE:TABLE_BASE + 8 - BASE], "big"
    )
    bound = 10
    expected_draw = ((((table_word_after & 0xFF) * bound) & 0xFFFFFFFF) >> 8) & 0xFF
    changed = [i for i, (before, after) in enumerate(zip(previous_ram, ram)) if before != after]
    ranges: list[list[int]] = []
    for offset in changed:
        if not ranges or offset > ranges[-1][1]:
            ranges.append([offset, offset + 1])
        else:
            ranges[-1][1] = offset + 1
    source_hashes = [
        {
            "start": f"0x{start:08x}",
            "end_exclusive": f"0x{end:08x}",
            "sha256": sha(kernel[start - pinned.BASE:end - pinned.BASE]),
        }
        for start, end in source_ranges
    ]
    current_instructions = [
        [f"0x{pc:08x}", f"0x{word:04x}", op, slot]
        for pc, word, op, slot in cpu.trace
    ]
    report = {
        "schema": "neptune.original-rng-wrap-window.v1",
        "original_game_bytes_executed": True,
        "kernel_sha256": sha(kernel),
        "kernel_mapping": "0x06006000",
        "source_ranges": source_hashes,
        "checkpoint_frame": checkpoint["frame"],
        "checkpoint_state_sha256": checkpoint["state_sha256"],
        "checkpoint_path": str(args.checkpoint),
        "interpreter_revision": pinned.INTERPRETER_REVISION,
        "interpreter_sources": pinned.SOURCE_HASHES,
        "abi": {"entry": f"0x{ENTRY:08x}", "bound_r4": bound, "stack_r15": f"0x{STACK:08x}", "index_from_checkpoint": 55},
        "captured_state": {"index_before": 55, "selected_word_before": f"0x{selected_before:08x}"},
        "window_instruction_limit": WINDOW,
        "max_resumable_windows": MAX_WINDOWS,
        "window_number": len(prior_windows) + 1,
        "window_instructions": len(cpu.trace),
        "window_cpu_steps": cpu.steps - window_start,
        "total_instructions": cpu.steps,
        "elapsed_seconds": round(time.monotonic() - started, 4),
        "pc_after_window": f"0x{cpu.pc:08x}",
        "escaped_uninspected_pc": None if escaped is None else f"0x{escaped:08x}",
        "returned": returned,
        "return_r0": None if not returned else f"0x{cpu.r[0]:08x}",
        "index_after": index_after,
        "table_entry1_after": f"0x{table_word_after:08x}",
        "independent_draw_formula": f"(({table_word_after & 0xFF:#04x} * {bound}) >> 8) & 0xff",
        "independent_draw_expected": expected_draw,
        "independent_draw_matches": returned and cpu.r[0] == expected_draw,
        "cpu": {
            "r": [f"0x{value:08x}" for value in cpu.r],
            "sr": f"0x{cpu.sr:08x}", "pr": f"0x{cpu.pr:08x}",
            "gbr": f"0x{cpu.gbr:08x}", "vbr": f"0x{cpu.vbr:08x}",
            "mach": f"0x{cpu.mach:08x}", "macl": f"0x{cpu.macl:08x}",
            "pc": f"0x{cpu.pc:08x}", "steps": cpu.steps,
        },
        "instructions": prior_instructions + current_instructions,
        "writes": prior_writes + [
            [f"0x{address:08x}", size, f"0x{value:0{size * 2}x}"]
            for address, size, value in memory.writes
        ],
        "ram_sha256": sha(ram),
        "ram_changed_ranges": [
            {"start": f"0x{BASE + start:08x}", "end_exclusive": f"0x{BASE + end:08x}", "bytes": end - start}
            for start, end in ranges
        ],
        "windows": prior_windows + [{
            "start_step": window_start,
            "end_step": cpu.steps,
            "instructions": len(cpu.trace),
            "escaped_pc": None if escaped is None else f"0x{escaped:08x}",
            "returned": returned,
            "error": error,
        }],
        "limitations": [
            "constructed direct entry, bound and stack",
            "captured frame-1800 WorkRAM supplies all nonconstructed state",
            "each invocation executes at most 512 SH-2 instructions including delay slots",
            "only the inspected helper/refresh code ranges execute; escaped PCs halt",
            "no natural caller, seed origin, call ordering, recurrence or regional claim",
        ],
    }
    args.report.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    (args.report.parent / "ram.bin").write_bytes(ram)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "window": report["window_number"], "instructions": report["window_instructions"],
        "pc": report["pc_after_window"], "escaped": report["escaped_uninspected_pc"],
        "returned": returned, "return_r0": report["return_r0"],
        "index_after": index_after, "table_entry1_after": report["table_entry1_after"],
    }))


if __name__ == "__main__":
    main()
