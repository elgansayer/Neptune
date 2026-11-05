#!/usr/bin/env python3
"""Independent static SH-2 function discovery for one flat original module.

Neptune-owned decoder and recursive descent, standard library only. Given one
declared module mapping (bytes, load base) and explicit seeds, it classifies
halfwords as instructions, PC-relative literal data or switch-table data and
finds function entries in three separately labelled tiers:

* ``A`` call-reached: seeds, ``bsr`` targets, ``jsr``/``bsrf`` targets resolved
  from PC-relative literals in the same straight line or from a register the
  function loads from exactly one literal, and recognised switch tables.
* ``B`` pointer-reached hypotheses: in-module code pointers held in literal
  pools or aligned unclassified words whose descent is clean and which sit at a
  boundary or open with a stack-frame prologue.
* ``C`` prologue-only hypotheses: an unreferenced ``mov.l r14,@-r15`` or
  ``sts.l pr,@-r15`` at a boundary in still-unclassified bytes.

This is static disassembly evidence. Nothing is executed. A discovered entry is
not proof that the code runs, that it is a source-level function, or that the
whole module is classified; unknown denominators stay explicit. ``base-check``
compares a declared mapping with deliberately wrong bases and byte order, and
``reconcile`` classifies externally observed or claimed addresses against an
inventory without treating either side as an oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

SCHEMA = "neptune.sh2-function-inventory.v1"
BASE_SCHEMA = "neptune.sh2-base-check.v1"
RECONCILE_SCHEMA = "neptune.sh2-reconcile.v1"
RESIDENCY_SCHEMA = "neptune.sh2-residency-classes.v1"
RESIDENT_SCHEMA = "neptune.resident-module-comparison.v1"
MAX_MODULE = 4 << 20
MAX_ITERATIONS = 512
MAX_TABLE = 512
MAX_TRIAL = 4096
MIN_POINTER_INSNS = 4
MIN_PROLOGUE_INSNS = 8
MIN_CLOSED_INSNS = 8
MASK = 0xFFFFFFFF
# BIOS service slot documented by the repository's Japan startup evidence
# (docs/restart/research/2026-11-04-japan-system-area-static-triage.md).
SYS_SETUINT_SLOT = 0x06000300
PREFERENCE = ("argument-pointer", "literal-pointer", "table-pointer", "prologue-gap")

DELAYED = frozenset({"bra", "bsr", "braf", "bsrf", "jmp", "jsr", "rts", "rte", "bt/s", "bf/s"})
FLOW = DELAYED | {"bt", "bf", "trapa"}


class Ins:
    """One decoded halfword. ``r`` is the register a flow instruction reads."""

    __slots__ = ("word", "op", "n", "m", "imm", "flow", "writes", "pcrel", "illegal", "r")

    def __init__(self, word, op, n=None, m=None, imm=None, flow=None, writes=(), pcrel=None, r=None):
        self.word, self.op, self.n, self.m, self.imm = word, op, n, m, imm
        self.flow, self.writes, self.pcrel, self.r = flow, frozenset(writes), pcrel, r
        self.illegal = op == "illegal"

    @property
    def delayed(self) -> bool:
        return self.flow in DELAYED


def _s8(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def _s12(value: int) -> int:
    return value - 0x1000 if value & 0x800 else value


def _s16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def _s32(value: int) -> int:
    return value - 0x100000000 if value & 0x80000000 else value


_SYS = ("sr", "gbr", "vbr")
_SPECIAL = ("mach", "macl", "pr")
_ARITH2 = {0x7: "div0s", 0x8: "tst", 0x9: "and", 0xA: "xor", 0xB: "or", 0xC: "cmp/str",
           0xD: "xtrct", 0xE: "mulu.w", 0xF: "muls.w"}
_ARITH3 = {0x0: "cmp/eq", 0x2: "cmp/hs", 0x3: "cmp/ge", 0x4: "div1", 0x5: "dmulu.l", 0x6: "cmp/hi",
           0x7: "cmp/gt", 0x8: "sub", 0xA: "subc", 0xB: "subv", 0xC: "add", 0xD: "dmuls.l",
           0xE: "addc", 0xF: "addv"}
_WRITES_N3 = {"div1", "sub", "subc", "subv", "add", "addc", "addv"}
_UNARY6 = {0x7: "not", 0x8: "swap.b", 0x9: "swap.w", 0xA: "negc", 0xB: "neg", 0xC: "extu.b",
           0xD: "extu.w", 0xE: "exts.b", 0xF: "exts.w"}
_SHIFT4 = {(0x0, 0): "shll", (0x0, 1): "dt", (0x0, 2): "shal", (0x1, 0): "shlr", (0x1, 1): "cmp/pz",
           (0x1, 2): "shar", (0x4, 0): "rotl", (0x4, 2): "rotcl", (0x5, 0): "rotr", (0x5, 1): "cmp/pl",
           (0x5, 2): "rotcr", (0x8, 0): "shll2", (0x8, 1): "shll8", (0x8, 2): "shll16",
           (0x9, 0): "shlr2", (0x9, 1): "shlr8", (0x9, 2): "shlr16"}
_SIZE = "bwl"


def _decode(w: int) -> Ins:
    hi, n, m, lo, d8 = w >> 12, (w >> 8) & 15, (w >> 4) & 15, w & 15, w & 0xFF
    if hi == 0x0:
        if lo == 0x2 and m <= 2:
            return Ins(w, "stc " + _SYS[m] + ",rn", n=n, writes=(n,))
        if lo == 0x3 and m == 0:
            return Ins(w, "bsrf rm", m=n, flow="bsrf", r=n)
        if lo == 0x3 and m == 2:
            return Ins(w, "braf rm", m=n, flow="braf", r=n)
        if 0x4 <= lo <= 0x6:
            return Ins(w, "mov.%s rm,@(r0,rn)" % _SIZE[lo - 4], n=n, m=m)
        if lo == 0x7:
            return Ins(w, "mul.l rm,rn", n=n, m=m)
        if n == 0 and lo == 0x8 and m <= 2:
            return Ins(w, ("clrt", "sett", "clrmac")[m])
        if n == 0 and lo == 0x9 and m <= 1:
            return Ins(w, ("nop", "div0u")[m])
        if lo == 0x9 and m == 2:
            return Ins(w, "movt rn", n=n, writes=(n,))
        if n == 0 and lo == 0xB and m <= 2:
            op = ("rts", "sleep", "rte")[m]
            return Ins(w, op, flow=None if op == "sleep" else op)
        if lo == 0xA and m <= 2:
            return Ins(w, "sts " + _SPECIAL[m] + ",rn", n=n, writes=(n,))
        if 0xC <= lo <= 0xE:
            return Ins(w, "mov.%s @(r0,rm),rn" % _SIZE[lo - 0xC], n=n, m=m, writes=(n,))
        if lo == 0xF:
            return Ins(w, "mac.l @rm+,@rn+", n=n, m=m, writes=(n, m))
        return Ins(w, "illegal")
    if hi == 0x1:
        return Ins(w, "mov.l rm,@(disp,rn)", n=n, m=m, imm=lo)
    if hi == 0x2:
        if lo <= 0x2:
            return Ins(w, "mov.%s rm,@rn" % _SIZE[lo], n=n, m=m)
        if 0x4 <= lo <= 0x6:
            return Ins(w, "mov.%s rm,@-rn" % _SIZE[lo - 4], n=n, m=m, writes=(n,))
        if lo in _ARITH2:
            op = _ARITH2[lo]
            return Ins(w, op + " rm,rn", n=n, m=m, writes=(n,) if op in ("and", "xor", "or", "xtrct") else ())
        return Ins(w, "illegal")
    if hi == 0x3:
        if lo in _ARITH3:
            op = _ARITH3[lo]
            return Ins(w, op + " rm,rn", n=n, m=m, writes=(n,) if op in _WRITES_N3 else ())
        return Ins(w, "illegal")
    if hi == 0x4:
        if (lo, m) in _SHIFT4:
            op = _SHIFT4[(lo, m)]
            return Ins(w, op + " rn", n=n, writes=() if op.startswith("cmp/") else (n,))
        if lo == 0x2 and m <= 2:
            return Ins(w, "sts.l " + _SPECIAL[m] + ",@-rn", n=n, writes=(n,))
        if lo == 0x3 and m <= 2:
            return Ins(w, "stc.l " + _SYS[m] + ",@-rn", n=n, writes=(n,))
        if lo == 0x6 and m <= 2:
            return Ins(w, "lds.l @rm+," + _SPECIAL[m], m=n, writes=(n,))
        if lo == 0x7 and m <= 2:
            return Ins(w, "ldc.l @rm+," + _SYS[m], m=n, writes=(n,))
        if lo == 0xA and m <= 2:
            return Ins(w, "lds rm," + _SPECIAL[m], m=n)
        if lo == 0xB and m == 0:
            return Ins(w, "jsr @rm", m=n, flow="jsr", r=n)
        if lo == 0xB and m == 1:
            return Ins(w, "tas.b @rn", n=n)
        if lo == 0xB and m == 2:
            return Ins(w, "jmp @rm", m=n, flow="jmp", r=n)
        if lo == 0xE and m <= 2:
            return Ins(w, "ldc rm," + _SYS[m], m=n)
        if lo == 0xF:
            return Ins(w, "mac.w @rm+,@rn+", n=n, m=m, writes=(n, m))
        return Ins(w, "illegal")
    if hi == 0x5:
        return Ins(w, "mov.l @(disp,rm),rn", n=n, m=m, imm=lo, writes=(n,))
    if hi == 0x6:
        if lo <= 0x2:
            return Ins(w, "mov.%s @rm,rn" % _SIZE[lo], n=n, m=m, writes=(n,))
        if lo == 0x3:
            return Ins(w, "mov rm,rn", n=n, m=m, writes=(n,))
        if 0x4 <= lo <= 0x6:
            return Ins(w, "mov.%s @rm+,rn" % _SIZE[lo - 4], n=n, m=m, writes=(n, m))
        return Ins(w, _UNARY6[lo] + " rm,rn", n=n, m=m, writes=(n,))
    if hi == 0x7:
        return Ins(w, "add #imm,rn", n=n, imm=_s8(d8), writes=(n,))
    if hi == 0x8:
        if n in (0x0, 0x1):
            return Ins(w, "mov.%s r0,@(disp,rn)" % _SIZE[n], n=m, imm=lo)
        if n in (0x4, 0x5):
            return Ins(w, "mov.%s @(disp,rm),r0" % _SIZE[n - 4], m=m, imm=lo, writes=(0,))
        if n == 0x8:
            return Ins(w, "cmp/eq #imm,r0", imm=_s8(d8))
        branch = {0x9: "bt", 0xB: "bf", 0xD: "bt/s", 0xF: "bf/s"}.get(n)
        if branch:
            return Ins(w, branch + " label", imm=_s8(d8), flow=branch)
        return Ins(w, "illegal")
    if hi == 0x9:
        return Ins(w, "mov.w @(disp,pc),rn", n=n, imm=d8, writes=(n,), pcrel="w")
    if hi in (0xA, 0xB):
        op = "bra" if hi == 0xA else "bsr"
        return Ins(w, op + " label", imm=_s12(w & 0xFFF), flow=op)
    if hi == 0xC:
        if n <= 0x2:
            return Ins(w, "mov.%s r0,@(disp,gbr)" % _SIZE[n], imm=d8)
        if n == 0x3:
            return Ins(w, "trapa #imm", imm=d8, flow="trapa")
        if 0x4 <= n <= 0x6:
            return Ins(w, "mov.%s @(disp,gbr),r0" % _SIZE[n - 4], imm=d8, writes=(0,))
        if n == 0x7:
            return Ins(w, "mova @(disp,pc),r0", imm=d8, writes=(0,), pcrel="a")
        op = ("tst", "and", "xor", "or", "tst.b", "and.b", "xor.b", "or.b")[n - 8]
        suffix = " #imm,r0" if n < 0xC else " #imm,@(r0,gbr)"
        return Ins(w, op + suffix, imm=d8, writes=(0,) if op in ("and", "xor", "or") else ())
    if hi == 0xD:
        return Ins(w, "mov.l @(disp,pc),rn", n=n, imm=d8, writes=(n,), pcrel="l")
    if hi == 0xE:
        return Ins(w, "mov #imm,rn", n=n, imm=_s8(d8), writes=(n,))
    return Ins(w, "illegal")


_TABLE: list | None = None


def decode(word: int) -> Ins:
    global _TABLE
    if _TABLE is None:
        _TABLE = [_decode(value) for value in range(0x10000)]
    return _TABLE[word & 0xFFFF]


def pcrel_address(ins: Ins, pc: int) -> int:
    """Effective address of a PC-relative load/mova at ``pc`` (slot uses its own address)."""
    if ins.pcrel == "w":
        return (pc + 4 + ins.imm * 2) & MASK
    return ((pc & ~3) + 4 + ins.imm * 4) & MASK


def branch_target(ins: Ins, pc: int) -> int:
    return (pc + 4 + ins.imm * 2) & MASK


def canonical(address: int) -> int:
    """Fold the SH-2 cache-through window (0x20000000-0x3FFFFFFF) onto its cached address."""
    return address & 0x1FFFFFFF if address >> 29 == 1 else address


def is_prologue(word: int) -> bool:
    """SHC/GCC frame openings: push r8-r14 or PR, or a negative stack adjustment."""
    return (word & 0xFF0F == 0x2F06 and 8 <= (word >> 4) & 15 <= 14) or word == 0x4F22 or (
        word & 0xFF00 == 0x7F00 and word & 0x80)


def is_return_stub(module, address: int) -> bool:
    """``rts`` with a ``nop`` or ``mov #imm,r0`` slot: a do-nothing or constant callback.

    Narrowed after a runtime residency check showed a sequential data table whose
    ``0x000B`` halfword decodes as ``rts`` with an arbitrary following halfword."""
    if not module.inside(address, 4) or module.u16(address) != 0x000B:
        return False
    slot = module.u16(address + 2)
    return slot == 0x0009 or slot & 0xFF00 == 0xE000


class Function:
    __slots__ = ("entry", "insns", "normal", "calls", "tails", "far", "external", "unresolved",
                 "bad", "switches", "returns", "literals", "handlers", "arguments")

    def __init__(self, entry: int):
        self.entry = entry
        self.insns: set[int] = set()
        self.normal: set[int] = set()
        self.calls: set[tuple[int, int, str]] = set()
        self.tails: set[tuple[int, int]] = set()
        self.far: set[tuple[int, int]] = set()
        self.external: set[tuple[int, int, str]] = set()
        self.unresolved: list[tuple[int, str, int | None]] = []
        self.handlers: set[tuple[int, int | None, int]] = set()
        self.arguments: set[tuple[int, int, int]] = set()
        self.bad: list[tuple[int, str]] = []
        self.switches: list[dict] = []
        self.returns = 0
        self.literals: dict[int, int] = {}


class Module:
    """Recursive descent over one declared mapping. Addresses are absolute."""

    def __init__(self, data: bytes, base: int):
        if not data or len(data) > MAX_MODULE or len(data) & 1:
            raise ValueError("Module must be a nonempty even-length image within the size bound")
        if base & 1 or not 0 <= base <= MASK - len(data):
            raise ValueError("Invalid module base")
        self.data, self.base, self.end = data, base, base + len(data)

    def inside(self, address: int, size: int = 2) -> bool:
        return self.base <= address and address + size <= self.end

    def u16(self, address: int) -> int:
        offset = address - self.base
        return (self.data[offset] << 8) | self.data[offset + 1]

    def u32(self, address: int) -> int:
        offset = address - self.base
        return int.from_bytes(self.data[offset:offset + 4], "big")

    def ins(self, address: int) -> Ins:
        return decode(self.u16(address))

    # -- constant tracking -------------------------------------------------
    def transfer(self, state: dict, ins: Ins, pc: int) -> dict:
        if not ins.writes:
            return state
        out = dict(state)
        for reg in ins.writes:
            out.pop(reg, None)
        op = ins.op
        if ins.pcrel in ("l", "w"):
            address = pcrel_address(ins, pc)
            size = 4 if ins.pcrel == "l" else 2
            if self.inside(address, size):
                out[ins.n] = self.u32(address) if size == 4 else _s16(self.u16(address)) & MASK
        elif ins.pcrel == "a":
            out[0] = pcrel_address(ins, pc)
        elif op == "mov #imm,rn":
            out[ins.n] = ins.imm & MASK
        elif op == "mov rm,rn" and ins.m in state:
            out[ins.n] = state[ins.m]
        elif op == "add #imm,rn" and ins.n in state:
            out[ins.n] = (state[ins.n] + ins.imm) & MASK
        elif op == "add rm,rn" and ins.n in state and ins.m in state:
            out[ins.n] = (state[ins.n] + state[ins.m]) & MASK
        elif op in ("shll2 rn", "shll rn", "shll8 rn", "shll16 rn") and ins.n in state:
            out[ins.n] = (state[ins.n] << {"shll rn": 1, "shll2 rn": 2, "shll8 rn": 8, "shll16 rn": 16}[op]) & MASK
        elif op == "extu.w rm,rn" and ins.m in state:
            out[ins.n] = state[ins.m] & 0xFFFF
        elif op == "exts.w rm,rn" and ins.m in state:
            out[ins.n] = _s16(state[ins.m] & 0xFFFF) & MASK
        return out

    @staticmethod
    def clobber(state: dict) -> dict:
        return {reg: value for reg, value in state.items() if reg >= 8}

    # -- switch tables -----------------------------------------------------
    @staticmethod
    def _last_writer(history: list, reg: int):
        for index in range(len(history) - 1, -1, -1):
            if reg in history[index][1].writes:
                return index
        return None

    def _bound(self, history: list, before: int):
        """Entry count from the nearest compare against a constant and the bt/bf edge taken."""
        for index in range(before - 1, max(-1, before - 24), -1):
            pc, ins, state = history[index]
            if ins.op not in ("cmp/hs rm,rn", "cmp/hi rm,rn", "cmp/ge rm,rn", "cmp/gt rm,rn"):
                continue
            later = history[index + 1:before + 1]
            position = next((k for k, row in enumerate(later) if row[1].flow in ("bt", "bf", "bt/s", "bf/s")), None)
            if position is None:
                continue
            bpc, bins, _ = later[position]
            following = later[position + 1][0] if position + 1 < len(later) else None
            taken = following == branch_target(bins, bpc) and following not in (bpc + 2, bpc + 4)
            switch_when_true = (bins.flow in ("bt", "bt/s")) == taken
            kind = ins.op.split()[0]
            if ins.m in state and ins.n not in state:      # index in Rn, constant in Rm
                limit, index_is_n = state[ins.m], True
            elif ins.n in state and ins.m not in state:    # constant in Rn, index in Rm
                limit, index_is_n = state[ins.n], False
            else:
                continue
            limit = _s32(limit) if kind in ("cmp/ge", "cmp/gt") else limit
            inclusive = kind in ("cmp/hs", "cmp/ge")
            # T = Rn >= Rm (hs/ge) or Rn > Rm (hi/gt); keep the indices on the switch path.
            if index_is_n:
                count = None if switch_when_true else (limit if inclusive else limit + 1)
            else:
                count = (limit + 1 if inclusive else limit) if switch_when_true else None
            if count is not None and 0 < count <= MAX_TABLE:
                return count, pc
            return None
        return None

    def _stride(self, history: list, writer: int, reg: int):
        """Byte scaling applied to an index register before an indexed table load."""
        shift = 0
        for index in range(writer - 1, max(-1, writer - 24), -1):
            ins = history[index][1]
            if reg not in ins.writes:
                continue
            if ins.op == "mov rm,rn":
                reg = ins.m
                continue
            step = {"shll rn": 1, "shll2 rn": 2, "shll8 rn": 8, "shll16 rn": 16}.get(ins.op)
            if step is None and ins.op == "add rm,rn" and ins.m == ins.n:
                step = 1
            if step is None:
                break
            shift += step
        return 1 << shift if shift <= 8 else None

    def _switch(self, site: int, ins: Ins, history: list):
        """Return (form, table, size, stride, targets, bounded) or None for recognised idioms."""
        writer = self._last_writer(history, ins.r)
        if writer is None:
            return None
        wpc, wins, wstate = history[writer]
        form = table = size = relative = index = None
        if wins.op in ("mov.w @(r0,rm),rn", "mov.l @(r0,rm),rn") and ins.flow in ("braf", "jmp"):
            size = 2 if wins.op.startswith("mov.w") else 4
            if 0 in wstate and wins.m not in wstate:
                table, index = wstate[0], wins.m
            elif wins.m in wstate and 0 not in wstate:
                table, index = wstate[wins.m], 0
            if table is not None and ins.flow == "braf":
                form, relative = "braf-rel%d" % (size * 8), (site + 4) & MASK
            elif table is not None and size == 4:
                form = "jmp-abs32"
        elif wins.op == "add rm,rn" and ins.flow == "jmp" and wins.n == ins.r and wins.n in wstate:
            # GCC: mova T,r0; mov.w @(r0,rI),rI; add rI,r0; jmp @r0 (entries relative to T).
            inner = self._last_writer(history[:writer], wins.m)
            if inner is not None:
                ipc, iins, istate = history[inner]
                if iins.op == "mov.w @(r0,rm),rn" and iins.n == wins.m and 0 in istate:
                    table, size, form, relative, index = istate[0], 2, "jmp-tabrel16", istate[0], iins.m
                    writer = inner
                    if wstate.get(wins.n) != table:
                        return None
        if form is None or table & 1 or not self.inside(table, size):
            return None
        stride = self._stride(history, writer, index)
        if stride is None or stride < size:
            return None
        bound = self._bound(history, writer)
        limit = bound[0] if bound else MAX_TABLE
        targets: list[int] = []
        for slot in range(limit):
            address = table + slot * stride
            if not self.inside(address, size):
                break
            if targets and address >= min(targets) and min(targets) > table:
                if bound:
                    return None
                break
            raw = self.u32(address) if size == 4 else self.u16(address)
            if form == "jmp-abs32":
                target = raw
            else:
                target = (relative + (_s32(raw) if size == 4 else _s16(raw))) & MASK
            if target & 1 or not self.inside(target) or self.ins(target).illegal:
                if bound:
                    return None
                break
            targets.append(target)
        if not targets:
            return None
        return form, table, size, stride, targets, bool(bound)

    @staticmethod
    def _pointer_slot(history: list, reg: int):
        """Absolute address a call register was loaded from (``mov.l @Rm,Rn`` with Rm known)."""
        for index in range(len(history) - 1, -1, -1):
            pc, ins, state = history[index]
            if reg not in ins.writes:
                continue
            if ins.op == "mov.l @rm,rn" and ins.m in state:
                return state[ins.m]
            if ins.op == "mov.l @(disp,rm),rn" and ins.m in state:
                return (state[ins.m] + ins.imm * 4) & MASK
            return None
        return None

    # -- descent -----------------------------------------------------------
    def descend(self, entry: int, entries, literal: dict, resolved: dict | None = None) -> Function:
        """Explore one function. ``literal`` marks known PC-relative data words."""
        fn = Function(entry)
        resolved = resolved or {}
        work: list[tuple[int, dict, list]] = [(entry, {}, [])]
        steps = 0
        while work:
            pc, state, history = work.pop()
            while True:
                if pc in fn.normal:
                    break
                steps += 1
                if steps > 1 << 20:
                    fn.bad.append((pc, "step-limit"))
                    return fn
                if pc & 1 or not self.inside(pc):
                    fn.bad.append((pc, "outside-module"))
                    break
                if pc in literal:
                    fn.bad.append((pc, "reaches-literal"))
                    break
                ins = self.ins(pc)
                if ins.illegal:
                    fn.bad.append((pc, "illegal-opcode"))
                    break
                fn.normal.add(pc)
                fn.insns.add(pc)
                self._note_literal(fn, ins, pc)
                history = history + [(pc, ins, state)] if len(history) < 48 else history[-47:] + [(pc, ins, state)]
                if ins.flow is None:
                    state = self.transfer(state, ins, pc)
                    pc += 2
                    continue
                kind = ins.flow
                after = state
                if ins.delayed:
                    slot_pc = pc + 2
                    if not self.inside(slot_pc) or slot_pc in literal:
                        fn.bad.append((slot_pc, "slot-outside-or-literal"))
                        break
                    slot = self.ins(slot_pc)
                    if slot.illegal or slot.flow is not None:
                        fn.bad.append((slot_pc, "illegal-slot"))
                        break
                    fn.insns.add(slot_pc)
                    self._note_literal(fn, slot, slot_pc)
                    after = self.transfer(state, slot, slot_pc)
                if kind in ("bt", "bf"):
                    work.append((branch_target(ins, pc), {}, history))
                    state, pc = after, pc + 2
                    continue
                if kind in ("bt/s", "bf/s"):
                    work.append((branch_target(ins, pc), {}, history))
                    state, pc = after, pc + 4
                    continue
                if kind == "bra":
                    target = branch_target(ins, pc)
                    if target in entries and target != entry:
                        fn.tails.add((pc, target))
                        break
                    pc, state, history = target, {}, []
                    continue
                if kind in ("rts", "rte"):
                    fn.returns += 1
                    break
                if kind == "trapa":
                    fn.external.add((pc, ins.imm, "trapa"))
                    state, pc = self.clobber(after), pc + 2
                    continue
                value = state.get(ins.r, resolved.get(pc))
                alias = ""
                if value is not None and kind in ("jsr", "jmp") and canonical(value) != value:
                    value, alias = canonical(value), "-cache-through"
                if kind in ("bsr", "jsr", "bsrf"):
                    if kind == "bsr":
                        target, how = branch_target(ins, pc), "bsr"
                    elif value is None:
                        target = None
                    elif kind == "jsr":
                        target, how = value, ("jsr-literal" if ins.r in state else "jsr-register") + alias
                    else:
                        target, how = (pc + 4 + value) & MASK, "bsrf-literal" if ins.r in state else "bsrf-register"
                    slot_address = None
                    if target is None:
                        slot_address = self._pointer_slot(history, ins.r)
                        fn.unresolved.append((pc, kind, slot_address))
                    elif target & 1 == 0 and self.inside(target):
                        fn.calls.add((pc, target, how))
                    else:
                        fn.external.add((pc, target, how))
                    for reg in (4, 5, 6, 7):  # arguments are often completed in the delay slot
                        value = None if after.get(reg) is None else canonical(after[reg])
                        if value is not None and value & 1 == 0 and self.inside(value):
                            fn.arguments.add((pc, reg, value))
                    handler = after.get(5)
                    if slot_address == SYS_SETUINT_SLOT and handler is not None and handler & 1 == 0 \
                            and self.inside(handler):
                        fn.handlers.add((pc, after.get(4), handler))
                    state, pc, history = self.clobber(after), pc + 4, []
                    continue
                # jmp / braf: tail call, far branch, switch or unresolved.
                if value is not None:
                    target = value if kind == "jmp" else (pc + 4 + value) & MASK
                    if target in entries and target != entry:
                        fn.tails.add((pc, target))
                    elif target & 1 == 0 and self.inside(target) and target != entry and \
                            kind == "jmp" and is_prologue(self.u16(target)):
                        fn.tails.add((pc, target))  # a frame-opening target is another function
                        fn.calls.add((pc, target, "jmp-literal-tail" + alias))
                    elif target & 1 == 0 and self.inside(target):
                        fn.far.add((pc, target))
                        pc, state, history = target, {}, []
                        continue
                    else:
                        fn.external.add((pc, target, kind + "-literal"))
                    break
                switch = self._switch(pc, ins, history)
                if switch is None:
                    fn.unresolved.append((pc, kind, self._pointer_slot(history, ins.r)))
                    break
                form, table, size, stride, targets, bounded = switch
                fn.switches.append({"site": pc, "form": form, "table": table, "entry_size": size,
                                    "stride": stride, "entries": len(targets), "bounded": bounded,
                                    "targets": sorted(set(targets))})
                for target in sorted(set(targets), reverse=True):
                    work.append((target, {}, []))
                break
        return fn

    def _note_literal(self, fn: Function, ins: Ins, pc: int):
        if ins.pcrel in ("l", "w"):
            address = pcrel_address(ins, pc)
            size = 4 if ins.pcrel == "l" else 2
            if self.inside(address, size):
                fn.literals[address] = max(size, fn.literals.get(address, 0))


def _unique_register_literals(module: Module, fn: Function) -> dict:
    """Map unresolved jsr/jmp sites to a value when their register is written by exactly
    one in-function literal load (SHC keeps often-called addresses in r8-r14)."""
    writers: dict[int, list] = {}
    for pc in sorted(fn.insns):
        ins = module.ins(pc)
        for reg in ins.writes:
            if ins.op == "mov.l @rm+,rn" and ins.m == 15 and ins.n == reg:
                continue  # epilogue restore of the caller's value, not a new definition
            writers.setdefault(reg, []).append((pc, ins))
    out = {}
    for site, kind, slot in fn.unresolved:
        if kind not in ("jsr", "jmp") or slot is not None:
            continue
        reg = module.ins(site).r
        rows = writers.get(reg, [])
        if reg >= 8 and len(rows) == 1 and rows[0][1].pcrel == "l":
            pc, ins = rows[0]
            address = pcrel_address(ins, pc)
            if module.inside(address, 4):
                out[site] = module.u32(address)
    return out


class Discovery:
    """Fixed-point discovery with explicit provenance and tiers."""

    def __init__(self, module: Module, seeds: list[tuple[int, str]], leads: list[tuple[int, str]] = ()):
        self.module = module
        self.provenance: dict[int, set[str]] = {}
        self.tier: dict[int, str] = {}
        self.leads = list(leads)
        for address, why in seeds:
            if address & 1 or not module.inside(address):
                raise ValueError("Seed outside module: 0x%08X" % address)
            self.provenance.setdefault(address, set()).add("seed:" + why)
            self.tier[address] = "A"
        for address, why in leads:
            if address & 1 or not module.inside(address):
                raise ValueError("Lead outside module: 0x%08X" % address)
        self.resolved: dict[int, int] = {}
        self.functions: dict[int, Function] = {}
        self.code: dict[int, int] = {}
        self.literal: dict[int, int] = {}
        self.table: dict[int, int] = {}
        self.iterations = 0
        self.rejected: dict[str, int] = {}
        self.code_pointers: dict[int, set[str]] = {}
        self.lead_status: dict[int, str] = {}

    def _close(self, tier: str):
        """Descend until no new call-reached entry appears; callees inherit the best caller tier."""
        literal: dict[int, int] = dict(self.literal)
        pending = sorted(address for address in self.provenance if address not in self.functions)
        while pending:
            self.iterations += 1
            if self.iterations > MAX_ITERATIONS:
                raise RuntimeError("Discovery did not converge")
            fresh = []
            for entry in pending:
                fn = self.module.descend(entry, self.provenance, literal, self.resolved)
                extra = _unique_register_literals(self.module, fn)
                if extra:
                    self.resolved.update(extra)
                    fn = self.module.descend(entry, self.provenance, literal, self.resolved)
                self.functions[entry] = fn
                for address, size in fn.literals.items():
                    literal[address] = max(size, literal.get(address, 0))
                    if size == 4:
                        literal[address + 2] = max(2, literal.get(address + 2, 0))
                for _, target, how in self._edges(fn):
                    if target not in self.provenance:
                        fresh.append(target)
                    self.provenance.setdefault(target, set()).add(how)
                    self._inherit(target, self.tier.get(entry, tier))
                for switch in fn.switches:
                    for k in range(switch["entries"]):
                        a = switch["table"] + k * switch["stride"]
                        for h in range(a, a + switch["entry_size"], 2):
                            literal[h] = max(2, literal.get(h, 0))
            pending = sorted(set(fresh))
        self.literal = literal

    @staticmethod
    def _edges(fn: Function):
        """Call edges plus documented BIOS interrupt-handler registrations."""
        yield from fn.calls
        for site, vector, handler in fn.handlers:
            yield site, handler, "sys-setuint-handler" + ("" if vector is None else ":%02X" % (vector & 0xFF))

    def _inherit(self, target: int, tier: str):
        order = "ABCR"
        current = self.tier.get(target)
        if current is None or order.index(tier) < order.index(current):
            self.tier[target] = tier

    def settle(self):
        """Re-descend every entry with the final entry set and recompute byte classes."""
        for _ in range(8):
            literal: dict[int, int] = {}
            functions = {}
            for entry in sorted(self.provenance):
                functions[entry] = self.module.descend(entry, self.provenance, self.literal, self.resolved)
            for fn in functions.values():
                for address, size in fn.literals.items():
                    literal[address] = max(size, literal.get(address, 0))
                    if size == 4:
                        literal[address + 2] = max(2, literal.get(address + 2, 0))
            new = {t for fn in functions.values() for _, t, _ in self._edges(fn) if t not in self.provenance}
            self.functions, self.literal = functions, literal
            if not new:
                break
            for fn in functions.values():
                for _, target, how in self._edges(fn):
                    self.provenance.setdefault(target, set()).add(how)
                    self._inherit(target, self.tier.get(fn.entry, "A"))
        self.code, self.table = {}, {}
        for entry in sorted(self.functions):
            fn = self.functions[entry]
            for pc in fn.insns:
                self.code.setdefault(pc, entry)
            for switch in fn.switches:
                for k in range(switch["entries"]):
                    a = switch["table"] + k * switch["stride"]
                    for h in range(a, a + switch["entry_size"], 2):
                        self.table.setdefault(h, switch["site"])

    def classified(self, address: int) -> bool:
        return address in self.code or address in self.literal or address in self.table

    def boundary(self, address: int) -> bool:
        """Preceded (past nop/zero padding) by data, a table, or a terminator's delay slot."""
        probe = address - 2
        while self.module.inside(probe) and self.module.u16(probe) in (0x0009, 0x0000) and probe not in self.code:
            probe -= 2
        if not self.module.inside(probe):
            return True
        if probe in self.literal or probe in self.table:
            return True
        if probe in self.code and self.module.inside(probe - 2):
            before = self.module.ins(probe - 2)
            return before.flow in ("rts", "rte", "bra", "jmp", "braf") and probe - 2 in self.code
        return False

    def trial(self, address: int, minimum: int, referenced: bool = False):
        """A clean bounded descent through unclassified bytes, else None.

        It must reach an exit, or be a closed loop of at least ``MIN_CLOSED_INSNS``
        instructions (task bodies never return). A two-instruction return stub is
        accepted only when code itself loads the pointer (``referenced``)."""
        fn = self.module.descend(address, self.provenance, self.literal, self.resolved)
        if fn.bad or len(fn.insns) > MAX_TRIAL:
            return None
        if any(pc in self.code or pc in self.table for pc in fn.insns):
            return None
        if any(a in self.code for a in fn.literals):
            return None
        exits = fn.returns or fn.tails or fn.far or fn.switches
        if referenced and len(fn.insns) == 2 and fn.returns == 1 and is_return_stub(self.module, address):
            return fn
        if len(fn.insns) < minimum:
            return None
        if exits or len(fn.insns) >= MIN_CLOSED_INSNS:
            return fn
        return None

    def pointer_candidates(self):
        """In-module code pointers from literal pools and aligned unclassified longwords."""
        found = []
        for address, size in sorted(self.literal.items()):
            if size == 4 and address % 4 == 0 and self.module.inside(address, 4):
                found.append((canonical(self.module.u32(address)), "literal-pointer"))
        for fn in self.functions.values():
            for _, _, value in fn.arguments:
                found.append((value, "argument-pointer"))
        start = (self.module.base + 3) & ~3
        for address in range(start, self.module.end - 3, 4):
            if self.classified(address) or self.classified(address + 2):
                continue
            found.append((canonical(self.module.u32(address)), "table-pointer"))
        return found

    def _screen(self, value: int, why: str, minimum: int):
        if value & 1 or not self.module.inside(value) or value in self.provenance:
            return "skip", None
        if value in self.code:
            self.code_pointers.setdefault(value, set()).add(why)
            return "into-code", None
        if value in self.literal or value in self.table:
            return "into-data", None
        referenced = why in ("argument-pointer", "literal-pointer")
        stub = referenced and is_return_stub(self.module, value)
        if not (stub or is_prologue(self.module.u16(value)) or self.boundary(value)):
            return "no-boundary", None
        fn = self.trial(value, minimum, referenced)
        return ("accept", fn) if fn else ("unclean", None)

    def run(self):
        self._close("A")
        self.settle()
        for tier, gather, minimum in (("B", self.pointer_candidates, MIN_POINTER_INSNS),
                                      ("C", self.prologue_candidates, MIN_PROLOGUE_INSNS)):
            for _ in range(16):
                rejected: dict[str, int] = {}
                accepted = 0
                groups: dict[int, set[str]] = {}
                for value, why in gather():
                    groups.setdefault(value, set()).add(why)
                for value in sorted(groups):
                    whys = groups[value]
                    why = min(whys, key=PREFERENCE.index)
                    verdict, fn = self._screen(value, why, minimum)
                    if verdict == "skip":
                        continue
                    if verdict != "accept":
                        rejected[why + ":" + verdict] = rejected.get(why + ":" + verdict, 0) + 1
                        continue
                    self.provenance.setdefault(value, set()).update(whys)
                    self.tier[value] = tier
                    accepted += 1
                    for pc in fn.insns:  # provisional claim so overlapping candidates are refused
                        self.code.setdefault(pc, value)
                    for address, size in fn.literals.items():
                        self.literal[address] = max(size, self.literal.get(address, 0))
                        if size == 4:
                            self.literal[address + 2] = max(2, self.literal.get(address + 2, 0))
                if accepted:
                    self._close(tier)
                    self.settle()
                if not accepted:
                    for key, count in rejected.items():
                        self.rejected[key] = count
                    break
        # External runtime leads are seeded last, only where static tiers left bytes unclassified.
        added = 0
        for address, why in sorted(self.leads):
            if address in self.provenance or address in self.code:
                self.lead_status[address] = classify(self, address)
                continue
            self.provenance.setdefault(address, set()).add("lead:" + why)
            self.tier[address] = "R"
            self.lead_status[address] = "seeded"
            added += 1
        if added:
            self._close("R")
            self.settle()

    def prologue_candidates(self):
        found = []
        for address in range(self.module.base, self.module.end - 1, 2):
            if self.classified(address):
                continue
            if self.module.u16(address) in (0x2FE6, 0x4F22) and self.boundary(address):
                found.append((address, "prologue-gap"))
        return found

    # -- reporting ---------------------------------------------------------
    def unclassified_runs(self):
        runs, start = [], None
        for address in range(self.module.base, self.module.end, 2):
            known = self.classified(address)
            if not known and start is None:
                start = address
            elif known and start is not None:
                runs.append((start, address - start))
                start = None
        if start is not None:
            runs.append((start, self.module.end - start))
        return runs

    def conflicts(self):
        return sorted(a for a in self.code if a in self.literal or a in self.table)


def ranges(addresses) -> list[list[int]]:
    out: list[list[int]] = []
    for address in sorted(addresses):
        if out and out[-1][1] == address:
            out[-1][1] = address + 2
        else:
            out.append([address, address + 2])
    return out


def h32(value: int) -> str:
    return "%08X" % (value & MASK)


def _count(values) -> dict:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def _top_slots(functions: list, limit: int = 16) -> dict:
    counts: dict[str, int] = {}
    for row in functions:
        for _, _, slot in row["unresolved"]:
            if slot:
                counts[slot] = counts.get(slot, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit])


def inventory(discovery: Discovery, identity: dict) -> dict:
    module = discovery.module
    functions = []
    for entry in sorted(discovery.functions):
        fn = discovery.functions[entry]
        functions.append({
            "entry": h32(entry), "tier": discovery.tier.get(entry, "A"),
            "provenance": sorted(discovery.provenance.get(entry, ())),
            "instructions": len(fn.insns), "ranges": [[h32(lo), h32(hi)] for lo, hi in ranges(fn.insns)],
            "calls": sorted({h32(t) for _, t, _ in fn.calls}),
            "tail_calls": sorted({h32(t) for _, t in fn.tails}),
            "far_jumps": len(fn.far), "external": sorted({h32(t) for _, t, _ in fn.external}),
            "unresolved": [[h32(pc), kind, None if slot is None else h32(slot)]
                           for pc, kind, slot in sorted(set(fn.unresolved), key=lambda row: (row[0], row[1]))],
            "handlers": [[h32(site), None if vector is None else vector & 0xFF, h32(handler)]
                         for site, vector, handler in sorted(fn.handlers, key=lambda row: row[0])],
            "switches": [{"site": h32(s["site"]), "form": s["form"], "table": h32(s["table"]),
                          "entries": s["entries"], "bounded": s["bounded"]} for s in fn.switches],
            "returns": fn.returns, "bad": [[h32(pc), why] for pc, why in fn.bad],
        })
    halfwords = len(module.data) // 2
    code = len(discovery.code)
    literal = sum(1 for a in discovery.literal if a not in discovery.code)
    table = sum(1 for a in discovery.table if a not in discovery.code and a not in discovery.literal)
    runs = discovery.unclassified_runs()
    tiers = {t: sum(1 for e in discovery.functions if discovery.tier.get(e, "A") == t) for t in "ABCR"}
    entry_list = [row["entry"] + ":" + row["tier"] for row in functions]
    summary = {
        "functions": len(functions), "functions_by_tier": tiers,
        "functions_with_problems": sum(1 for row in functions if row["bad"]),
        "instruction_halfwords": code, "literal_halfwords": literal, "switch_table_halfwords": table,
        "unclassified_halfwords": halfwords - code - literal - table, "total_halfwords": halfwords,
        "unclassified_runs": len(runs), "largest_unclassified_run_bytes": max((n for _, n in runs), default=0),
        "unresolved_indirect_sites": sum(len(row["unresolved"]) for row in functions),
        "unresolved_via_pointer_slot": sum(1 for row in functions for u in row["unresolved"] if u[2]),
        "unresolved_pointer_slots_top": _top_slots(functions),
        "sys_setuint_registrations": sum(len(row["handlers"]) for row in functions),
        "switch_tables": sum(len(row["switches"]) for row in functions),
        "unbounded_switch_tables": sum(1 for row in functions for s in row["switches"] if not s["bounded"]),
        "code_literal_conflicts": len(discovery.conflicts()),
        "register_resolved_sites": len(discovery.resolved), "iterations": discovery.iterations,
        "rejected_candidates": dict(sorted(discovery.rejected.items())),
        "code_pointers_into_functions": len(discovery.code_pointers),
        "leads": len(discovery.leads),
        "lead_status": _count(discovery.lead_status.values()),
    }
    return {"schema": SCHEMA, "identity": identity, "summary": summary,
            "entry_list_sha256": hashlib.sha256("\n".join(entry_list).encode()).hexdigest(),
            "code_pointers_into_functions": {h32(a): sorted(w) for a, w in sorted(discovery.code_pointers.items())},
            "functions": functions,
            "limitations": [
                "Static disassembly only; no instruction was executed",
                "Tier B/C entries are hypotheses; tier A is reachability from declared seeds, not runtime proof",
                "Unclassified halfwords are not proven data; unresolved indirect sites may reach more code",
                "Function boundaries are reachable instruction sets, not source-level functions",
                "CPU role (master/slave) and residency lifetime are not established by this tool"]}


def classify(discovery: Discovery, address: int) -> str:
    if not discovery.module.inside(address):
        return "outside-module"
    if address & 1:
        return "odd-address"
    if address in discovery.functions:
        return "entry-tier-" + discovery.tier.get(address, "A")
    if address in discovery.code:
        slot = all(address not in fn.normal for fn in discovery.functions.values() if address in fn.insns)
        return "delay-slot" if slot else "instruction-in-function"
    if address in discovery.literal:
        return "literal-data"
    if address in discovery.table:
        return "switch-table"
    return "unclassified"


def base_metrics(data: bytes, base: int) -> dict:
    """Whole-image agreement of two independent encodings of function entries.

    ``bsr`` displacements are PC-relative, so their file-offset targets do not
    depend on the load base. ``mov.l @(disp,PC)`` literals hold absolute
    addresses. Under the true base, literal function pointers coincide with
    ``bsr`` targets; under a wrong base or byte order they coincide only by
    chance. Every halfword is scanned linearly, so data contributes the same
    noise to every candidate mapping."""
    bsr: set[int] = set()
    values: list[int] = []
    for offset in range(0, len(data) - 1, 2):
        word = (data[offset] << 8) | data[offset + 1]
        if word >> 12 == 0xB:
            bsr.add(offset + 4 + _s12(word & 0xFFF) * 2)
        elif word >> 12 == 0xD:
            literal = (offset & ~3) + 4 + (word & 0xFF) * 4
            if literal + 4 <= len(data):
                values.append(canonical(int.from_bytes(data[literal:literal + 4], "big")))
    inside = [v - base for v in values if base <= v < base + len(data) and not (v - base) & 1]
    agree = sum(1 for offset in inside if offset in bsr)
    prologue = sum(1 for offset in inside if is_prologue((data[offset] << 8) | data[offset + 1]))
    return {"base": h32(base), "bsr_targets": len(bsr), "literal_values": len(values),
            "literal_values_inside": len(inside), "literal_on_bsr_targets": agree,
            "agreement": round(agree / len(inside), 6) if inside else 0.0,
            "literal_on_prologue": prologue}


def replay(module: Module, prior: dict) -> Discovery:
    """Reproduce an inventory's classification from its recorded entries and tiers."""
    if prior.get("schema") != SCHEMA or prior["identity"]["source_sha256"] != hashlib.sha256(module.data).hexdigest():
        raise ValueError("Inventory does not describe this module")
    if int(prior["identity"]["base"], 16) != module.base:
        raise ValueError("Inventory describes a different base")
    discovery = Discovery(module, [(int(row["entry"], 16), "inventory") for row in prior["functions"]])
    for row in prior["functions"]:
        discovery.tier[int(row["entry"], 16)] = row["tier"]
    discovery._close("A")
    discovery.settle()
    if sorted(h32(e) for e in discovery.functions) != [row["entry"] for row in prior["functions"]]:
        raise ValueError("Inventory entries do not reproduce")
    return discovery


def residency(discovery: Discovery, resident: dict) -> dict:
    """Cross-tabulate static halfword classes with byte identity in one captured RAM image.

    Instruction halfwords that differ at runtime are either misclassified data,
    self-modifying code or not yet loaded; they are listed, never excused."""
    module = discovery.module
    if resident.get("schema") != RESIDENT_SCHEMA or resident.get("status") != "success":
        raise ValueError("Not a successful resident-module comparison")
    if resident["source_sha256"] != hashlib.sha256(module.data).hexdigest():
        raise ValueError("Residency report describes different module bytes")
    if int(resident["candidate_mapping"], 16) != module.base:
        raise ValueError("Residency report uses a different mapping")
    if resident.get("minimum_exact_range_bytes") != 2:
        raise ValueError("Use --minimum-range 2 so every identical halfword is reported")
    same = bytearray(len(module.data) // 2)
    for row in resident["matching_ranges"]:
        start, end = int(row["source_start"], 16), int(row["source_end_exclusive"], 16)
        for offset in range((start + 1) & ~1, end - 1, 2):
            same[offset // 2] = 1
    classes = {"instruction": [0, 0], "literal": [0, 0], "switch-table": [0, 0], "unclassified": [0, 0]}
    changed_code: dict[int, list[int]] = {}
    for index, identical in enumerate(same):
        address = module.base + index * 2
        if address in discovery.code:
            kind = "instruction"
        elif address in discovery.literal:
            kind = "literal"
        elif address in discovery.table:
            kind = "switch-table"
        else:
            kind = "unclassified"
        classes[kind][0 if identical else 1] += 1
        if kind == "instruction" and not identical:
            changed_code.setdefault(discovery.code[address], []).append(address)
    tiers: dict[str, int] = {}
    for entry in changed_code:
        tier = discovery.tier.get(entry, "A")
        tiers[tier] = tiers.get(tier, 0) + 1
    return {"schema": RESIDENCY_SCHEMA, "checkpoint_frame": resident["checkpoint_frame"],
            "checkpoint_state_sha256": resident["checkpoint_state_sha256"],
            "workram_h_sha256": resident["workram_h_sha256"], "mapping": h32(module.base),
            "halfwords": {k: {"identical": v[0], "changed": v[1]} for k, v in classes.items()},
            "functions_with_changed_instructions": len(changed_code),
            "changed_functions_by_tier": dict(sorted(tiers.items())),
            "changed_instruction_sites": {h32(e): [h32(a) for a in sorted(v)[:8]]
                                          for e, v in sorted(changed_code.items())},
            "limitations": ["Byte identity in one captured image does not prove execution",
                            "Unloaded or overwritten regions differ for reasons unrelated to classification"]}


# -- command line ----------------------------------------------------------

def _hex(text: str) -> int:
    return int(text, 16)


def _signed_hex(text: str) -> int:
    value = int(text, 16)
    if not -0x10000000 < value < 0x10000000 or value == 0:
        raise argparse.ArgumentTypeError("delta must be nonzero and within 0x10000000")
    return value


def _read_module(path: Path) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(MAX_MODULE + 1)
    if len(data) > MAX_MODULE:
        raise ValueError("Module exceeds size bound")
    return data


def _write_new(path: Path, value: dict):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=1, sort_keys=True) + "\n")


def _identity(args, data: bytes) -> dict:
    return {"module": args.name, "release": args.release, "source_sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data), "base": h32(args.base), "cpu": "sh2-role-unresolved",
            "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory", help="discover functions and write a new private report")
    inv.add_argument("--module", type=Path, required=True)
    inv.add_argument("--base", type=_hex, required=True)
    inv.add_argument("--seed", type=_hex, action="append", default=[], help="absolute entry, hex")
    inv.add_argument("--leads", type=Path, help="reference-address JSON; named sets seed tier R last")
    inv.add_argument("--lead-set", action="append", default=[], help="set name within --leads")
    inv.add_argument("--name", required=True)
    inv.add_argument("--release", required=True)
    inv.add_argument("--expected-sha256")
    inv.add_argument("--report", type=Path, required=True)
    chk = sub.add_parser("base-check", help="compare the declared mapping with wrong bases/byte order")
    chk.add_argument("--module", type=Path, required=True)
    chk.add_argument("--base", type=_hex, required=True)
    chk.add_argument("--wrong-delta", type=_signed_hex, action="append", default=[],
                     help="signed hex delta, e.g. -1000")
    chk.add_argument("--report", type=Path, required=True)
    res = sub.add_parser("residency", help="cross-tabulate classes with a resident-module comparison")
    res.add_argument("--module", type=Path, required=True)
    res.add_argument("--base", type=_hex, required=True)
    res.add_argument("--inventory", type=Path, required=True)
    res.add_argument("--resident", type=Path, action="append", required=True)
    res.add_argument("--report", type=Path, required=True)
    rec = sub.add_parser("reconcile", help="classify reference address sets against a module")
    rec.add_argument("--module", type=Path, required=True)
    rec.add_argument("--base", type=_hex, required=True)
    rec.add_argument("--inventory", type=Path, required=True)
    rec.add_argument("--references", type=Path, required=True)
    rec.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    data = _read_module(args.module)
    if args.command == "inventory":
        if args.expected_sha256 and hashlib.sha256(data).hexdigest() != args.expected_sha256:
            print("FAIL: module digest differs from the declared identity", file=sys.stderr)
            return 1
        if not args.seed:
            print("FAIL: at least one explicit seed is required", file=sys.stderr)
            return 1
        leads = []
        if args.lead_set and not args.leads:
            print("FAIL: --lead-set requires --leads", file=sys.stderr)
            return 1
        if args.leads:
            with args.leads.open(encoding="utf-8") as stream:
                reference = json.load(stream)
            if reference.get("source_sha256") != hashlib.sha256(data).hexdigest():
                print("FAIL: lead file describes different module bytes", file=sys.stderr)
                return 1
            chosen = {row["name"]: row for row in reference["sets"]}
            for name in args.lead_set:
                if name not in chosen:
                    print("FAIL: unknown lead set " + name, file=sys.stderr)
                    return 1
                leads += [(int(a, 16), name) for a in chosen[name]["addresses"]]
        discovery = Discovery(Module(data, args.base), [(seed, "declared") for seed in args.seed], leads)
        discovery.run()
        report = inventory(discovery, _identity(args, data))
        report["identity"]["lead_sets"] = sorted(args.lead_set)
        _write_new(args.report, report)
        print(json.dumps({"report": str(args.report), **report["summary"],
                          "entry_list_sha256": report["entry_list_sha256"]}, sort_keys=True))
        return 0 if report["summary"]["functions"] else 1
    if args.command == "base-check":
        declared = base_metrics(data, args.base)
        if not args.wrong_delta:
            print("FAIL: at least one wrong base is required", file=sys.stderr)
            return 1
        controls = []
        for delta in args.wrong_delta:
            controls.append({"kind": "wrong-base", "delta": delta,
                             **base_metrics(data, (args.base + delta) & MASK)})
        swapped = bytes(b for pair in zip(data[1::2], data[0::2]) for b in pair)
        controls.append({"kind": "byte-swapped", "delta": 0, **base_metrics(swapped, args.base)})
        best_wrong = max(c["agreement"] for c in controls)
        passed = declared["agreement"] >= 0.1 and declared["agreement"] >= 5 * best_wrong and all(
            c["agreement"] < declared["agreement"] for c in controls)
        report = {"schema": BASE_SCHEMA, "declared": declared, "controls": controls, "passed": passed,
                  "rule": "declared agreement >= 0.1, >= 5x every control, and strictly greatest",
                  "source_sha256": hashlib.sha256(data).hexdigest(),
                  "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        _write_new(args.report, report)
        print(json.dumps({"passed": passed, "declared_agreement": declared["agreement"],
                          "best_control_agreement": best_wrong}))
        return 0 if passed else 1
    with args.inventory.open(encoding="utf-8") as stream:
        prior = json.load(stream)
    try:
        discovery = replay(Module(data, args.base), prior)
    except ValueError as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1
    if args.command == "residency":
        rows = []
        for path in args.resident:
            with path.open(encoding="utf-8") as stream:
                rows.append(residency(discovery, json.load(stream)))
        report = {"schema": RESIDENCY_SCHEMA, "inventory_entry_list_sha256": prior["entry_list_sha256"],
                  "source_sha256": prior["identity"]["source_sha256"], "captures": rows}
        _write_new(args.report, report)
        print(json.dumps([{"frame": r["checkpoint_frame"], **r["halfwords"],
                           "functions_with_changed_instructions": r["functions_with_changed_instructions"]}
                          for r in rows], sort_keys=True))
        return 0
    with args.references.open(encoding="utf-8") as stream:
        references = json.load(stream)
    if not isinstance(references.get("sets"), list) or not all(
            isinstance(group, dict) and isinstance(group.get("addresses"), list) for group in references["sets"]):
        print("FAIL: references must hold a list of named address sets", file=sys.stderr)
        return 1
    sets = []
    for group in references["sets"]:
        rows = {}
        for text in group["addresses"]:
            rows[text.upper()] = classify(discovery, int(text, 16))
        counts: dict[str, int] = {}
        for value in rows.values():
            counts[value] = counts.get(value, 0) + 1
        sets.append({"name": group["name"], "provenance": group["provenance"], "count": len(rows),
                     "classes": dict(sorted(counts.items())), "addresses": dict(sorted(rows.items()))})
    report = {"schema": RECONCILE_SCHEMA, "inventory_entry_list_sha256": prior["entry_list_sha256"],
              "source_sha256": prior["identity"]["source_sha256"], "sets": sets}
    _write_new(args.report, report)
    print(json.dumps({s["name"]: s["classes"] for s in sets}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
