#!/usr/bin/env python3
"""Match SH-2 functions across flat modules by masked instruction hashes.

Generic and content-free.  A function body is the run of code halfwords from
its entry up to the next entry (or the end of its code range).  The
displacement fields of PC-relative instructions (``bra``/``bsr``,
``bt``/``bf``/``bt.s``/``bf.s``, ``mov.w``/``mov.l`` literal loads and
``mova``) are masked, so the same object code linked at a different address
hashes equally; literal-pool contents are ignored.  Bodies shorter than
``minimum`` instructions are skipped because tiny bodies collide by chance.

Typical use: find the same library object code in modules built by
different teams, or map functions between two releases of one program.
"""
from __future__ import annotations

import collections
import hashlib


def mask(word: int) -> int:
    """Clear the displacement bits of PC-relative SH-2 instructions."""
    hi, n = word >> 12, (word >> 8) & 15
    if hi in (0xA, 0xB):  # bra, bsr: 12-bit displacement
        return word & 0xF000
    if hi == 0x8 and n in (0x9, 0xB, 0xD, 0xF):  # bt, bf, bt/s, bf/s
        return word & 0xFF00
    if hi in (0x9, 0xD) or (hi == 0xC and n == 0x7):  # mov.w/mov.l @(disp,PC), mova
        return word & 0xFF00
    return word


def bodies(data: bytes, base: int, code: set[int], entries: list[int], minimum: int = 12) -> dict[int, tuple[str, int]]:
    """``entry -> (sha1 of masked body, instruction count)`` for one module."""
    entries = sorted(entries)
    out = {}
    for i, entry in enumerate(entries):
        stop = entries[i + 1] if i + 1 < len(entries) else base + len(data)
        words, address = [], entry
        while address < stop and address in code and address + 2 <= base + len(data):
            words.append(mask((data[address - base] << 8) | data[address - base + 1]))
            address += 2
        if len(words) >= minimum:
            digest = hashlib.sha1(b"".join(w.to_bytes(2, "big") for w in words)).hexdigest()
            out[entry] = (digest, len(words))
    return out


def match(modules: dict[str, dict[int, tuple[str, int]]]) -> tuple[dict, collections.Counter]:
    """Index bodies by hash; returns ``(hash -> [(module, entry)], pair counts)``."""
    index = collections.defaultdict(list)
    for name, funcs in modules.items():
        for entry, (digest, _) in funcs.items():
            index[digest].append((name, entry))
    pairs = collections.Counter()
    for rows in index.values():
        names = sorted({name for name, _ in rows})
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                pairs[(a, b)] += 1
    return index, pairs
