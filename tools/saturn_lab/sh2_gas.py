#!/usr/bin/env python3
"""SH-2 (SH7604) instruction formatter that emits GNU as syntax.

Generic and content-free: it maps one big-endian 16-bit instruction word at an
absolute address to text that GNU as (``as -big --isa=sh2``, binutils 2.44)
assembles back to the same word.  PC-relative operands (branches, ``mov.w``/
``mov.l`` literal loads and ``mova``) are expressed as labels supplied by a
caller callback.  When the callback declines a target (for example because it
lies in another assembly file, which GNU as cannot reach with these
fixed-width displacement forms), :func:`format_insn` returns ``None`` and the
caller must emit the raw word.

Words that are not SH-2 instructions also return ``None``.
"""
from __future__ import annotations

MASK = 0xFFFFFFFF
_SYS = ("sr", "gbr", "vbr")
_SPECIAL = ("mach", "macl", "pr")
_SIZE = "bwl"
_ARITH2 = {0x7: "div0s", 0x8: "tst", 0x9: "and", 0xA: "xor", 0xB: "or", 0xC: "cmp/str",
           0xD: "xtrct", 0xE: "mulu.w", 0xF: "muls.w"}
_ARITH3 = {0x0: "cmp/eq", 0x2: "cmp/hs", 0x3: "cmp/ge", 0x4: "div1", 0x5: "dmulu.l", 0x6: "cmp/hi",
           0x7: "cmp/gt", 0x8: "sub", 0xA: "subc", 0xB: "subv", 0xC: "add", 0xD: "dmuls.l",
           0xE: "addc", 0xF: "addv"}
_UNARY6 = {0x7: "not", 0x8: "swap.b", 0x9: "swap.w", 0xA: "negc", 0xB: "neg", 0xC: "extu.b",
           0xD: "extu.w", 0xE: "exts.b", 0xF: "exts.w"}
_SHIFT4 = {(0x0, 0): "shll", (0x0, 1): "dt", (0x0, 2): "shal", (0x1, 0): "shlr", (0x1, 1): "cmp/pz",
           (0x1, 2): "shar", (0x4, 0): "rotl", (0x4, 2): "rotcl", (0x5, 0): "rotr", (0x5, 1): "cmp/pl",
           (0x5, 2): "rotcr", (0x8, 0): "shll2", (0x8, 1): "shll8", (0x8, 2): "shll16",
           (0x9, 0): "shlr2", (0x9, 1): "shlr8", (0x9, 2): "shlr16"}
_BRANCH8 = {0x9: "bt", 0xB: "bf", 0xD: "bt/s", 0xF: "bf/s"}
_IMM_C = ("tst", "and", "xor", "or", "tst.b", "and.b", "xor.b", "or.b")

# Control-flow classes used by callers that walk code.
DELAYED = frozenset({"bra", "bsr", "braf", "bsrf", "jmp", "jsr", "rts", "rte", "bt/s", "bf/s"})


def s8(v: int) -> int:
    return v - 0x100 if v & 0x80 else v


def s12(v: int) -> int:
    return v - 0x1000 if v & 0x800 else v


def reference(word: int, pc: int):
    """Return ``(kind, target)`` for a PC-relative word at ``pc`` or ``None``.

    ``kind`` is ``branch`` (bra/bsr/bt/bf/bt.s/bf.s), ``word`` (mov.w literal),
    ``long`` (mov.l literal) or ``mova``.
    """
    hi, n = word >> 12, (word >> 8) & 15
    if hi == 0x8 and n in _BRANCH8:
        return "branch", (pc + 4 + s8(word & 0xFF) * 2) & MASK
    if hi in (0xA, 0xB):
        return "branch", (pc + 4 + s12(word & 0xFFF) * 2) & MASK
    if hi == 0x9:
        return "word", (pc + 4 + (word & 0xFF) * 2) & MASK
    if hi == 0xD:
        return "long", ((pc & ~3) + 4 + (word & 0xFF) * 4) & MASK
    if hi == 0xC and n == 0x7:
        return "mova", ((pc & ~3) + 4 + (word & 0xFF) * 4) & MASK
    return None


def mnemonic(word: int) -> str | None:
    """Bare mnemonic of ``word`` (``None`` when it is not an SH-2 instruction)."""
    text = format_insn(word, 0, lambda target, kind: "L")
    return None if text is None else text.split()[0]


def format_insn(word: int, pc: int, label) -> str | None:
    """GNU as text for ``word`` at absolute ``pc``.

    ``label(target, kind)`` returns the operand text for a PC-relative target or
    ``None`` to refuse it (the caller then emits the raw word).
    """
    w = word & 0xFFFF
    hi, n, m, lo, d8 = w >> 12, (w >> 8) & 15, (w >> 4) & 15, w & 15, w & 0xFF
    rn, rm = "r%d" % n, "r%d" % m
    ref = reference(w, pc)
    if ref is not None:
        target = label(ref[1], ref[0])
        if target is None:
            return None
    if hi == 0x0:
        if lo == 0x2 and m <= 2:
            return "stc %s,%s" % (_SYS[m], rn)
        if lo == 0x3 and m == 0:
            return "bsrf %s" % rn
        if lo == 0x3 and m == 2:
            return "braf %s" % rn
        if 0x4 <= lo <= 0x6:
            return "mov.%s %s,@(r0,%s)" % (_SIZE[lo - 4], rm, rn)
        if lo == 0x7:
            return "mul.l %s,%s" % (rm, rn)
        if n == 0 and lo == 0x8 and m <= 2:
            return ("clrt", "sett", "clrmac")[m]
        if n == 0 and lo == 0x9 and m <= 1:
            return ("nop", "div0u")[m]
        if lo == 0x9 and m == 2:
            return "movt %s" % rn
        if n == 0 and lo == 0xB and m <= 2:
            return ("rts", "sleep", "rte")[m]
        if lo == 0xA and m <= 2:
            return "sts %s,%s" % (_SPECIAL[m], rn)
        if 0xC <= lo <= 0xE:
            return "mov.%s @(r0,%s),%s" % (_SIZE[lo - 0xC], rm, rn)
        if lo == 0xF:
            return "mac.l @%s+,@%s+" % (rm, rn)
        return None
    if hi == 0x1:
        return "mov.l %s,@(%d,%s)" % (rm, lo * 4, rn)
    if hi == 0x2:
        if lo <= 0x2:
            return "mov.%s %s,@%s" % (_SIZE[lo], rm, rn)
        if 0x4 <= lo <= 0x6:
            return "mov.%s %s,@-%s" % (_SIZE[lo - 4], rm, rn)
        if lo in _ARITH2:
            return "%s %s,%s" % (_ARITH2[lo], rm, rn)
        return None
    if hi == 0x3:
        if lo in _ARITH3:
            return "%s %s,%s" % (_ARITH3[lo], rm, rn)
        return None
    if hi == 0x4:
        if (lo, m) in _SHIFT4:
            return "%s %s" % (_SHIFT4[(lo, m)], rn)
        if lo == 0x2 and m <= 2:
            return "sts.l %s,@-%s" % (_SPECIAL[m], rn)
        if lo == 0x3 and m <= 2:
            return "stc.l %s,@-%s" % (_SYS[m], rn)
        if lo == 0x6 and m <= 2:
            return "lds.l @%s+,%s" % (rn, _SPECIAL[m])
        if lo == 0x7 and m <= 2:
            return "ldc.l @%s+,%s" % (rn, _SYS[m])
        if lo == 0xA and m <= 2:
            return "lds %s,%s" % (rn, _SPECIAL[m])
        if lo == 0xB and m == 0:
            return "jsr @%s" % rn
        if lo == 0xB and m == 1:
            return "tas.b @%s" % rn
        if lo == 0xB and m == 2:
            return "jmp @%s" % rn
        if lo == 0xE and m <= 2:
            return "ldc %s,%s" % (rn, _SYS[m])
        if lo == 0xF:
            return "mac.w @%s+,@%s+" % (rm, rn)
        return None
    if hi == 0x5:
        return "mov.l @(%d,%s),%s" % (lo * 4, rm, rn)
    if hi == 0x6:
        if lo <= 0x2:
            return "mov.%s @%s,%s" % (_SIZE[lo], rm, rn)
        if lo == 0x3:
            return "mov %s,%s" % (rm, rn)
        if 0x4 <= lo <= 0x6:
            return "mov.%s @%s+,%s" % (_SIZE[lo - 4], rm, rn)
        return "%s %s,%s" % (_UNARY6[lo], rm, rn)
    if hi == 0x7:
        return "add #%d,%s" % (s8(d8), rn)
    if hi == 0x8:
        if n == 0x0:
            return "mov.b r0,@(%d,%s)" % (lo, rm)
        if n == 0x1:
            return "mov.w r0,@(%d,%s)" % (lo * 2, rm)
        if n == 0x4:
            return "mov.b @(%d,%s),r0" % (lo, rm)
        if n == 0x5:
            return "mov.w @(%d,%s),r0" % (lo * 2, rm)
        if n == 0x8:
            return "cmp/eq #%d,r0" % s8(d8)
        if n in _BRANCH8:
            return "%s %s" % (_BRANCH8[n], target)
        return None
    if hi == 0x9:
        return "mov.w %s,%s" % (target, rn)
    if hi == 0xA:
        return "bra %s" % target
    if hi == 0xB:
        return "bsr %s" % target
    if hi == 0xC:
        if n <= 0x2:
            return "mov.%s r0,@(%d,gbr)" % (_SIZE[n], d8 << n)
        if n == 0x3:
            return "trapa #%d" % d8
        if 0x4 <= n <= 0x6:
            return "mov.%s @(%d,gbr),r0" % (_SIZE[n - 4], d8 << (n - 4))
        if n == 0x7:
            return "mova %s,r0" % target
        op = _IMM_C[n - 8]
        return ("%s #%d,r0" if n < 0xC else "%s #%d,@(r0,gbr)") % (op, d8)
    if hi == 0xD:
        return "mov.l %s,%s" % (target, rn)
    if hi == 0xE:
        return "mov #%d,%s" % (s8(d8), rn)
    return None
