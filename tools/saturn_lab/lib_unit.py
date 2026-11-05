#!/usr/bin/env python3
"""Library units for byte-identical SH builds: extract, relocate and locate.

Original programs link library routines (a C runtime, compiler support code) whose
sources hold many functions per file.  To compile such a routine into a
byte-identical rebuild, and to find where the original link put it, this module:

- splits compiler output (GCC 2.x ``cc1`` for SH, or preprocessed GNU as source)
  into units: one per top-level symbol (``_name``) or constant (``LC<n>``)
  (:func:`text_lines`, :func:`chunk`);
- rewrites a unit so it can be included anywhere: its labels become unique locals,
  every external symbol becomes a caller-supplied address, ``.align N`` pads with
  zero bytes, and ``;``-separated statements are split (:func:`rewrite`);
- searches a binary for the assembled unit with the external-address words masked
  and reads those words back (:func:`find`);
- resolves units that occur more than once by reference consistency and object
  order, then drops small wrappers whose references nothing confirms
  (:func:`resolve`, :func:`confirm`).

Generic and content-free: the tests use synthetic assembly and bytes only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

REGISTERS = {f"r{i}" for i in range(16)} | {"pr", "macl", "mach", "gbr", "vbr", "sr"}
LABEL = re.compile(r"^([A-Za-z_.$][\w.$]*):")
IDENT = re.compile(r"(?<![\w.$])([A-Za-z_.$][\w.$]*)")
SKIP = re.compile(r"^\s*(\.file|\.global|\.globl|\.text|\.data|\.section|\.lcomm|\.comm)\b")
DATA_OPS = (".long", ".word", ".short", ".byte", ".4byte", ".2byte")


class UnresolvedReference(ValueError):
    def __init__(self, name: str):
        super().__init__("unresolved reference %s" % name)
        self.name = name


def text_lines(lines: list[str]) -> list[str]:
    """Only the ``.text`` lines (``.data``/``.section`` switch away, ``.text`` back)."""
    out, section = [], ".text"
    for line in lines:
        s = line.strip()
        if s in (".text", ".data") or s.startswith(".section"):
            section = ".text" if s == ".text" or s.startswith(".section .text") else s
            continue
        if section == ".text":
            out.append(line)
    return out


def top_labels(lines: list[str]) -> list[tuple[int, str]]:
    tops = []
    for i, line in enumerate(lines):
        m = LABEL.match(line)
        if m and (m.group(1).startswith("_") or re.fullmatch(r"LC\d+", m.group(1))) \
                and m.group(1) not in ("gcc2_compiled.", "___gnu_compiled_c"):
            tops.append((i, m.group(1)))
    return tops


def chunk(lines: list[str], symbol: str | None) -> list[str]:
    """The lines of one unit: from ``symbol``'s label to the next top-level label."""
    if symbol is None:
        return lines
    tops = top_labels(lines)
    names = [n for _, n in tops]
    if symbol not in names:
        raise KeyError(symbol)
    k = names.index(symbol)

    def lead(i: int) -> int:  # a preceding .align (and blank lines) belongs to the next unit
        while i > 0 and (lines[i - 1].strip().startswith(".align") or not lines[i - 1].strip()):
            i -= 1
        return i
    start = lead(tops[k][0])
    end = lead(tops[k + 1][0]) if k + 1 < len(tops) else len(lines)
    return lines[start:end]


def rewrite(unit: list[str], tag: str, refs: dict[str, int]) -> list[str]:
    """Unit lines -> includable assembly (see module docstring)."""
    unit = [part if i == 0 else "\t" + part.strip()
            for line in unit for i, part in enumerate(line.split(";"))]
    defined = {LABEL.match(l).group(1) for l in unit if LABEL.match(l)}
    used: set[str] = set()

    def local(n: str) -> str:
        return ".L%s_%s" % (tag, n.lstrip("_.").replace(".", "_") or "x")

    def operand(m: re.Match) -> str:
        n = m.group(1)
        if n in REGISTERS:
            return n
        if n in defined:
            return local(n)
        if n in refs:
            used.add(n)
            return "0x%08X" % refs[n]
        raise UnresolvedReference(n)

    out = []
    for line in unit:
        if not line.strip() or SKIP.match(line) or line.strip() in ("gcc2_compiled.:", "___gnu_compiled_c:"):
            continue
        m = LABEL.match(line)
        if m:
            out.append(local(m.group(1)) + ":")
            line = line[m.end():]
            if not line.strip():
                continue
        s = line.strip()
        if s.startswith(".align"):
            out.append("\t.align %s,0" % s.split()[1].split(",")[0])
            continue
        if s.startswith("."):
            op, _, rest = s.partition(" ") if " " in s else s.partition("\t")
            if op in DATA_OPS and rest.strip() and not re.fullmatch(r"[\s\d,xXa-fA-F+-]*", rest):
                rest = IDENT.sub(operand, rest)
            out.append("\t%s\t%s" % (op, rest.strip()) if rest.strip() else "\t" + op)
            continue
        mnem, _, ops = s.partition("\t") if "\t" in s else s.partition(" ")
        if ops.strip():
            ops = IDENT.sub(operand, ops)
        out.append("\t%s\t%s" % (mnem, ops.strip()) if ops.strip() else "\t" + mnem)
    unused = set(refs) - used
    if unused:
        raise ValueError("references given but not used: " + " ".join(sorted(unused)))
    return out


def unresolved(unit: list[str], tag: str = "T") -> list[str]:
    """Every external symbol a unit references, in first-use order."""
    names: list[str] = []
    while True:
        try:
            rewrite(unit, tag, {n: i for i, n in enumerate(names)})
            return names
        except UnresolvedReference as e:
            names.append(e.name)


def find(data: bytes, slots: dict[int, str], blob: bytes, base: int, min_anchor: int = 8):
    """[(address, {name: word})] where ``data`` occurs in ``blob`` (2-byte aligned), with the
    4-byte words at ``slots`` (offset -> reference name) masked and read back."""
    mask = bytearray(len(data))
    for off in slots:
        mask[off:off + 4] = b"\1\1\1\1"
    best, start = (0, 0), 0
    for i, mk in enumerate(bytes(mask) + b"\1"):
        if mk:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = i + 1
    a0 = best[0] + (best[0] & 1)
    anchor = data[a0:min(best[1], a0 + 16)]
    if len(anchor) < min_anchor:
        return []
    hits, pos = [], blob.find(anchor)
    while pos >= 0:
        s = pos - a0
        if s >= 0 and s % 2 == 0 and s + len(data) <= len(blob):
            seg = blob[s:s + len(data)]
            if all(m or x == y for x, y, m in zip(seg, data, mask)):
                hits.append((base + s, {n: int.from_bytes(seg[o:o + 4], "big") for o, n in slots.items()}))
        pos = blob.find(anchor, pos + 1)
    return hits


@dataclass
class Unit:
    obj: str                      # object identity (source + defines + flags)
    symbol: str                   # unit name (global names are module-wide)
    size: int
    hits: list = field(default_factory=list)   # [(address, refs)]
    is_global: bool = True


def _scope(u: Unit, name: str, globals_: set[str]) -> str:
    return name if name in globals_ else u.obj + ":" + name


def resolve(units: list[Unit]) -> list[tuple[Unit, int, dict]]:
    """Choose one hit per unit: its address and its references must agree with every
    unit placed so far, and an address may carry only one name; among several hits,
    the first after the previous unit of the same object (the linker keeps an
    object's functions in order).  Larger units are resolved first, so a small
    look-alike wrapper cannot claim an address before the function that lives
    there.  Ambiguous units stay out."""
    globals_ = {u.symbol for u in units if u.is_global}
    known: dict[str, int] = {}
    owner: dict[int, str] = {}
    chosen: dict[int, tuple[int, dict]] = {}
    order = sorted(range(len(units)), key=lambda i: -units[i].size)
    changed = True
    while changed:
        changed = False
        for idx in order:
            u = units[idx]
            if idx in chosen:
                continue
            me = _scope(u, u.symbol, globals_)
            ok = [(a, r) for a, r in u.hits
                  if known.get(me, a) == a and owner.get(a, me) == me
                  and all(known.get(_scope(u, n, globals_), v) == v
                          and owner.get(v, _scope(u, n, globals_)) == _scope(u, n, globals_)
                          for n, v in r.items())
                  and all(a != a2 for a2, _ in chosen.values())]
            prev = [chosen[j][0] for j in range(idx) if j in chosen and units[j].obj == u.obj]
            if prev and len(ok) > 1:
                ok = [h for h in ok if h[0] > max(prev)][:1] or ok
            if len(ok) == 1:
                a, r = ok[0]
                chosen[idx] = (a, r)
                known[me] = a
                owner[a] = me
                for n, v in r.items():
                    known[_scope(u, n, globals_)] = v
                    owner.setdefault(v, _scope(u, n, globals_))
                changed = True
    return [(units[i], a, r) for i, (a, r) in sorted(chosen.items())]


def confirm(placed: list[tuple[Unit, int, dict]], min_size: int = 64):
    """Drop small units with references unless a reference is confirmed: it points at
    another placed unit, or a large (distinctive) placed unit references the same address."""
    out = list(placed)
    while True:
        strong = [x for x in out if x[0].size >= min_size or not x[2]]
        anchors = {a for _, a, _ in out} | {v for _, _, r in strong for v in r.values()}
        keep = [x for x in out if x[0].size >= min_size or not x[2]
                or any(v in anchors and v != x[1] for v in x[2].values())]
        if len(keep) == len(out):
            return out
        out = keep
