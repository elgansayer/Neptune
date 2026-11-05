#!/usr/bin/env python3
"""SND host-command mailbox: natural history ring, boot self-patch and executor.

Original USA SND (`BOMSS/PROGRAM.BIN[0x44:0x6418]`, Sega sound driver Ver2.04),
loaded at sound-CPU address 0. Three linked checks are reported together:

* natural: decode SND's own 128-entry command-history ring at 0x800 from
  private snapshots of accepted natural coverage runs. Cross-check it against
  the coverage observer (dispatch edges, vector-26 interrupts, the self-patch
  path and the 0x141E code counter).
* self_patch: run original 0x1768 in isolation for every value of host byte
  0x4E1, then derive the resident code image from the disc bytes.
* executor: run original 0x1A60 for all 256 command bytes against an
  independent contract, then replay every natural ring record.

Original bytes, states and raw rings stay private. Reports hold hashes,
counts, contracts and the decoded command records only.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from pathlib import Path

import analyze_sound_driver as sound
import m68k_probe as native
import probe_kernel as pinned

SCHEMA = 'neptune.snd-command-mailbox.v1'
CODE_END = 0x63D4
VECTOR_END, WORK_END = 0x400, 0x1000
NOP2 = 0x4E714E71
# Self-patch routine 0x1768, called once by the reset code at 0x10BA.
CONFIG = 0x4E1
PATCH_ENTRY, PATCH_END, PATCH_RETURN, PATCH_CALLER = 0x1768, 0x17BA, 0x10BE, 0x10BA
# (config bit, first patched address, longwords) in the routine's write order.
PATCH_SITES = ((7, 0x10E4, 2), (6, 0x2BE6, 1), (5, 0x1AAE, 1), (4, 0x116C, 1), (3, 0x1168, 1), (1, 0x1170, 1))
# Instruction PCs of 0x1768: always-executed groups and per-bit patch groups.
PATCH_PCS = ([0x1768, 0x176E, 0x1772], (7, [0x1774, 0x1778, 0x177A]), [0x177C, 0x177E], (6, [0x1780, 0x1784]),
             [0x1786, 0x1788], (5, [0x178A, 0x178E]), [0x1790, 0x1792], (4, [0x1794, 0x1798]),
             [0x179A, 0x179C], (3, [0x179E, 0x17A2]), [0x17A4, 0x17A6, 0x17A8], (1, [0x17AA, 0x17AE]),
             [0x17B0, 0x17B4, 0x17B8])
# Self-modifying sequencer-tick counter: immediate at 0x141E, stored by 0x1428.
COUNTER, COUNTER_STORE = 0x141E, 0x1428
# Zero-filled runtime record table inside the image, addressed by lea ($5E,PC,D1.w),A1 at 0x5380.
TABLE, TABLE_END, TABLE_LEA, TABLE_LEA_WORDS = 0x53E0, 0x54E0, 0x5380, 0x43FB105E
# Command executor 0x1A60, called once per non-zero slot by the main loop.
EXEC_ENTRY, EXEC_CALLER, EXEC_RETURN = 0x1A60, 0x10FE, 0x1102
EXEC_RANGES = [(0x1A60, 0x1BEE), (0x1DAC, 0x1DAE)]
SLOTS, RING, RING_ENTRIES = 0x700, 0x800, 128
STAMP, OFFSET, HOST_OFFSET = 0x8838, 0x883A, 0x41A
LOW_JSR, HIGH_JSR, LOW_RETURN, HIGH_RETURN = 0x1B60, 0x1AD2, 0x1B64, 0x1AD6
LOW_TABLE, HIGH_TABLE, IGNORE = 0x1B6E, 0x1ADA, 0x1B6A
LOW_HANDLERS = {0x01: 0x2364, 0x02: 0x2396, 0x03: 0x23FE, 0x04: 0x242E, 0x05: 0x2466, 0x06: 0x1BEE,
                0x07: 0x1BF6, 0x08: 0x18FE, 0x09: 0x1C04, 0x0A: 0x1C2A, 0x0B: 0x1C32, 0x0C: 0x1C3A,
                0x0D: 0x1C4C, 0x0E: 0x1C88, 0x10: 0x20DC, 0x11: 0x20CA, 0x12: 0x20C0, 0x13: 0x20D6}
HIGH_HANDLERS = {0x0: 0x1D10, 0x1: 0x1D54, 0x2: 0x1D98, 0x3: 0x1DA4, 0x5: 0x1DAE, 0x6: 0x2056,
                 0x7: 0x17FC, 0x8: 0x20A2, 0x9: 0x2162, 0xA: 0x1FA0}
PREFIX_PCS = [0x1A60, 0x1A62, 0x1A66, 0x1A6A, 0x1A6E, 0x1A72, 0x1A74, 0x1A78, 0x1A7C, 0x1A80, 0x1A84,
              0x1A88, 0x1A8C, 0x1A90, 0x1A94, 0x1A9A, 0x1A9E, 0x1AA2, 0x1AA4, 0x1AA6, 0x1AA8, 0x1AAA,
              0x1AAC, 0x1AAE, 0x1AB0, 0x1AB2, 0x1AB6, 0x1AB8, 0x1ABC, 0x1ABE]
INTERRUPT_COUNTER_STORE, TIMER_VECTOR = 0x175A, '26'
A2_NATURAL, A5_NATURAL, A6_NATURAL = 0x9000, 0x100000, 0x7000
EXEC_SP, PATCH_SP = 0x9FF0, 0x9FFC
# Stored offsets are (read & 0x7F0) + 16, so 0x0800 is the natural post-wrap value; 0xFFF0 is constructed.
EXEC_OFFSETS = (0x0000, 0x0590, 0x07E0, 0x07F0, 0x0800, 0xFFF0)
EXEC_SLOTS = (0, 3, 7)
# (D0 upper bits, SR, D7 upper word): natural main-loop values, then constructed ones.
EXEC_VARIANTS = ((0x00000000, 0x2000, 0x0000), (0xFFFFFF00, 0x271F, 0xFFFF))
SENTINEL = 0xA5A5A5A5
EXEC_CONTROLS = (
    ('ring_mask_03F0', 0x1A70, '03f0'), ('end_marker_zero', 0x1AA4, '7000'),
    ('stamp_not_cleared', 0x1A96, '0001'), ('host_offset_41C', 0x1A8E, '041c'),
    ('high_bound_92', 0x1AC4, '0092'), ('low_bound_21', 0x1B50, '0021'),
    ('low_table_shift', 0x1B62, '7010'))
PATCH_CONTROLS = (
    ('nop_constant', 0x176C, '4e70'), ('site_shift', 0x1782, '1468'),
    ('bit_order', 0x17A6, '4e71'), ('branch_sense', 0x1772, '6a08'))
NATURAL_CONTROLS = ('drop_entry', 'stamp_plus_one', 'prefix_swap', 'config_0x80', 'counter_plus_one')


def u16(data, address):
    return int.from_bytes(data[address:address + 2], 'big')


def u32(data, address):
    return int.from_bytes(data[address:address + 4], 'big')


def ccr(x=0, n=0, z=0, v=0, c=0):
    return (x << 4) | (n << 3) | (z << 2) | (v << 1) | c


# ---------------------------------------------------------------- self-patch

def patch_contract(value, d0, a0, sr, disc):
    """Independent contract of original 0x1768 for host configuration byte `value`."""
    events, pcs, address = [[1, CONFIG, 1, value]], [], a0
    sites = {}
    for bit, site, longs in PATCH_SITES:
        if not value >> bit & 1:
            for k in range(longs):
                events.append([2, site + 4 * k, 4, NOP2])
            address = site + 4 * (longs if longs > 1 else 0)
            sites[site] = longs
    events += [[1, CONFIG, 1, value], [1, PATCH_SP, 4, PATCH_RETURN]]
    for group in PATCH_PCS:
        if isinstance(group, tuple):
            if not value >> group[0] & 1:
                pcs += group[1]
        else:
            pcs += group
    regs = [SENTINEL] * 18
    regs[0] = (d0 & 0xFFFFFF00) | (value & 0x7F)
    regs[1], regs[8], regs[15], regs[16] = NOP2, address, PATCH_SP + 4, PATCH_RETURN
    regs[17] = (sr & 0xFF00) | ccr(x=value >> 2 & 1, z=int(value & 0x7F == 0))
    patched = bytearray(disc)
    for site, longs in sites.items():
        patched[site:site + 4 * longs] = NOP2.to_bytes(4, 'big') * longs
    return {'events': events, 'pcs': pcs, 'registers': regs, 'patched_sites': sorted(sites),
            'image': bytes(patched)}


def patch_regions(value, image):
    stack = bytes([0xCD] * 4) + PATCH_RETURN.to_bytes(4, 'big')
    regions = [(0x4E0, bytes([0x11, value, 0x22, 0x33]), False)]
    regions += [(site, image[site:site + 4 * longs], True) for _, site, longs in PATCH_SITES]
    return regions + [(PATCH_SP - 4, stack, True)]


def patch_cases():
    return [(value, d0, sr) for value in range(256) for d0, sr in ((SENTINEL, 0x2700), (0x00000080, 0x271F))]


def run_patch(code, library, disc, value, d0, sr):
    regs = [SENTINEL] * 18
    regs[0], regs[15], regs[16], regs[17] = d0, PATCH_SP, PATCH_ENTRY, sr
    regions = patch_regions(value, code)
    actual = library.run(code, PATCH_ENTRY, PATCH_RETURN, [(PATCH_ENTRY, PATCH_END)], regions, regs, budget=64)
    expected = patch_contract(value, d0, SENTINEL, sr, disc)
    if actual['status_code'] != 1:
        raise ValueError('Native guard: ' + actual['status'])
    if actual['pcs'] != expected['pcs'] or actual['steps'] != len(expected['pcs']):
        raise ValueError('Self-patch instruction path differs from contract')
    if actual['registers'] != expected['registers']:
        raise ValueError('Self-patch register/CCR result differs from contract')
    if actual['events'] != expected['events'] or not actual['code_unchanged']:
        raise ValueError('Self-patch ordered accesses differ from contract')
    if actual['regions_after'] != [data for _, data, _ in patch_regions(value, expected['image'])]:
        raise ValueError('Self-patch memory result differs from contract')
    return {'value': value, 'd0': d0, 'sr': sr, 'steps': actual['steps'],
            'patched_sites': [hex(s) for s in expected['patched_sites']],
            'events_sha256': pinned.digest(json.dumps(actual['events']).encode())}, expected['image']


# ------------------------------------------------------------------ executor

def exec_outcome(cmd):
    """Path class and stop/target for one command byte (independent of execution)."""
    if cmd < 0x80:
        if cmd >= 0x20:
            return 'ignored', None
        if cmd == 0:
            return 'low-noop', None
        if cmd in LOW_HANDLERS:
            return 'low-handler', LOW_HANDLERS[cmd]
        return 'low-ignored', None
    if cmd >= 0x91:
        return 'ignored', None
    index = cmd & 0xF
    if index in HIGH_HANDLERS:
        return 'high-handler', HIGH_HANDLERS[index]
    return {0x4: 'high-rts', 0xB: 'high-ignored', 0xE: 'high-ignored', 0xD: 'high-ori',
            0xC: 'high-device', 0xF: 'high-device'}[index], None


def slot_bytes(cmd, slot, payload=None):
    data = bytearray((0x31 + i + cmd) & 0xFF for i in range(0x80))
    base = 16 * slot
    if payload is not None:
        data[base:base + 14] = payload
    data[base] = cmd
    return bytes(data)


def ring_bytes():
    return bytes((i * 7 + 3) & 0xFF for i in range(0x800))


def device_bytes():
    return bytes((0xB0 + i) & 0xFF for i in range(8))


def exec_regions(slots, ring, offset, stamp, stack=None):
    work = bytearray(0x10)
    work[8:10], work[10:12] = stamp.to_bytes(2, 'big'), offset.to_bytes(2, 'big')
    if stack is None:
        stack = bytes([0xCD] * 0x30) + EXEC_RETURN.to_bytes(4, 'big') + bytes([0xEE] * 12)
    return [(SLOTS, slots, False), (RING, ring, True), (0x8830, bytes(work), True),
            (0x410, bytes([0x5C] * 0x10), True), (EXEC_SP - 0x30, stack, True),
            (0xDEF8, device_bytes(), False)]


def exec_contract(cmd, offset, stamp, slot, slots, ring, d0, sr, d7hi=0):
    """Independent register/access/memory contract of original 0x1A60."""
    kind, target = exec_outcome(cmd)
    s, sp = SLOTS + 16 * slot, EXEC_SP
    # The read offset is masked before the add, so the stored value never exceeds 0x800 or carries.
    r0, o2 = RING + (offset & 0x7F0), (offset & 0x7F0) + 16
    r1 = RING + (o2 & 0x7F0)
    regs_in = [SENTINEL] * 18
    regs_in[0], regs_in[7], regs_in[8] = d0, (d7hi << 16) | (7 - slot), s
    regs_in[10], regs_in[13], regs_in[14], regs_in[15], regs_in[16], regs_in[17] = (
        A2_NATURAL, A5_NATURAL, A6_NATURAL, sp, EXEC_ENTRY, sr)
    words = lambda a: u16(slots, a - SLOTS)
    longs = lambda a: u32(slots, a - SLOTS)
    events = [[2, sp - 2, 2, d0 & 0xFFFF], [2, sp - 4, 2, d0 >> 16], [1, OFFSET, 2, offset],
              [1, s, 2, words(s)], [2, r0, 2, words(s)]]
    for k in (2, 6, 10):
        events += [[1, s + k, 4, longs(s + k)], [2, r0 + k, 4, longs(s + k)]]
    events += [[2, OFFSET, 2, o2], [2, HOST_OFFSET, 2, o2], [1, STAMP, 2, stamp], [2, r0 + 14, 2, stamp],
               [2, STAMP, 2, 0]] + [[2, r1 + 4 * k, 4, 0xFFFFFFFF] for k in range(4)] + [[1, sp - 4, 4, d0]]
    pcs = list(PREFIX_PCS)
    d0_out, a4, a7, stop, status, error = d0, SENTINEL, sp + 4, EXEC_RETURN, 1, (0, 0)
    if cmd < 0x80:
        pcs += [0x1B4E, 0x1B52]
        d7 = cmd
        if cmd < 0x20:
            d7, a4 = cmd * 4, A6_NATURAL
            pcs += [0x1B56, 0x1B58, 0x1B5A, 0x1B5C, 0x1B60, LOW_TABLE + 4 * cmd]
            events += [[2, sp - 2, 2, A6_NATURAL & 0xFFFF], [2, sp - 4, 2, A6_NATURAL >> 16],
                       [2, sp - 6, 2, A5_NATURAL & 0xFFFF], [2, sp - 8, 2, A5_NATURAL >> 16],
                       [2, sp - 12, 4, LOW_RETURN]]
            if kind == 'low-handler':
                stop, a7 = target, sp - 12
            else:
                pcs += ([] if kind == 'low-noop' else [IGNORE, IGNORE + 2]) + [LOW_RETURN, LOW_RETURN + 4]
                events += [[1, sp - 12, 4, LOW_RETURN], [1, sp - 8, 4, A5_NATURAL],
                           [1, sp - 4, 4, A6_NATURAL], [1, sp, 4, EXEC_RETURN]]
        else:
            pcs += [IGNORE, IGNORE + 2]
            events.append([1, sp, 4, EXEC_RETURN])
    else:
        pcs += [0x1AC2, 0x1AC6]
        d7 = cmd
        if cmd >= 0x91:
            pcs += [IGNORE, IGNORE + 2]
            events.append([1, sp, 4, EXEC_RETURN])
        else:
            d7 = (cmd & 0xF) * 4
            thunk = HIGH_TABLE + d7
            pcs += [0x1ACA, 0x1ACE, 0x1AD0, 0x1AD2, thunk]
            events.append([2, sp - 4, 4, HIGH_RETURN])
            tail = [IGNORE, IGNORE + 2, HIGH_RETURN, IGNORE, IGNORE + 2]
            back = [[1, sp - 4, 4, HIGH_RETURN], [1, sp, 4, EXEC_RETURN]]
            if kind == 'high-handler':
                stop, a7 = target, sp - 4
            elif kind == 'high-rts':
                pcs += [0x1DAC, HIGH_RETURN, IGNORE, IGNORE + 2]
                events += back
            elif kind == 'high-ignored':
                pcs += tail
                events += back
            elif kind == 'high-ori':
                d0_out = d0 | 0x6A
                pcs += [0x1B12] + tail
                events += back
            else:  # misaligned bytes: byte read through A2, then a device-register write via A5
                displacement, written = (0x4EF9, A5_NATURAL) if cmd & 0xF == 0xC else (0x4EFA, A5_NATURAL + 0x50)
                source = A2_NATURAL + displacement
                events.append([1, source, 1, device_bytes()[source - 0xDEF8]])
                status, error = 5, (written, 1)
    regs = list(regs_in)
    regs[0], regs[7] = d0_out, (regs_in[7] & 0xFFFF0000) | d7
    regs[8], regs[9], regs[15], regs[16] = s + 2, r1 + 16, a7, stop
    if a4 != SENTINEL:
        regs[12] = a4
    if kind in ('low-handler', 'high-handler', 'low-noop'):
        flags = ccr(z=int(d7 == 0))
    else:
        # X is cleared by the offset add (no carry) or by the dispatch scaling adds.
        flags = ccr(n=d0_out >> 15 & 1, z=int(d0_out & 0xFFFF == 0))
    regs[17] = (sr & 0xFF00) | flags
    ring_after = bytearray(ring)
    entry = slots[s - SLOTS:s - SLOTS + 14] + stamp.to_bytes(2, 'big')
    ring_after[r0 - RING:r0 - RING + 16] = entry
    ring_after[r1 - RING:r1 - RING + 16] = b'\xff' * 16
    return {'kind': kind, 'target': target, 'stop': stop, 'status': status, 'error': error,
            'registers_in': regs_in, 'registers': regs, 'pcs': pcs, 'events': events,
            'ring_after': bytes(ring_after), 'offset_after': o2, 'entry': entry}


def exec_cases():
    rows = []
    for cmd in range(256):
        for offset in EXEC_OFFSETS:
            for slot in EXEC_SLOTS:
                for variant, (d0hi, sr, d7hi) in enumerate(EXEC_VARIANTS):
                    rows.append((cmd, offset, slot, variant, (cmd * 257 + offset + slot) & 0xFFFF, d0hi | cmd, sr, d7hi))
    return rows


def applied(lo, data, events):
    out = bytearray(data)
    for kind, address, size, value in events:
        if kind == 2 and lo <= address and address + size <= lo + len(out):
            out[address - lo:address - lo + size] = value.to_bytes(size, 'big')
    return bytes(out)


def run_exec(code, library, cmd, offset, slot, variant, stamp, d0, sr, d7hi=0, payload=None, ring=None):
    slots = slot_bytes(cmd, slot, payload)
    ring = ring_bytes() if ring is None else ring
    expected = exec_contract(cmd, offset, stamp, slot, slots, ring, d0, sr, d7hi)
    regions = exec_regions(slots, ring, offset, stamp)
    actual = library.run(code, EXEC_ENTRY, expected['stop'], EXEC_RANGES, regions,
                         expected['registers_in'], budget=96)
    if actual['status_code'] != expected['status'] or (actual['status_code'] != 1 and (
            actual['error_address'], actual['error_size']) != expected['error']):
        raise ValueError('Executor outcome differs from contract: ' + actual['status'])
    if actual['pcs'] != expected['pcs'] or actual['steps'] != len(expected['pcs']):
        raise ValueError('Executor instruction path differs from contract')
    if actual['events'] != expected['events'] or not actual['code_unchanged']:
        raise ValueError('Executor ordered accesses differ from contract')
    if expected['status'] == 1 and actual['registers'] != expected['registers']:
        raise ValueError('Executor register/CCR/stack result differs from contract')
    work = bytearray(0x10)
    work[10:12] = expected['offset_after'].to_bytes(2, 'big')
    host = bytearray([0x5C] * 0x10)
    host[0xA:0xC] = expected['offset_after'].to_bytes(2, 'big')
    if (actual['regions_after'][0] != slots or actual['regions_after'][1] != expected['ring_after']
            or actual['regions_after'][2] != bytes(work) or actual['regions_after'][3] != bytes(host)
            or actual['regions_after'][4] != applied(EXEC_SP - 0x30, regions[4][1], expected['events'])
            or actual['regions_after'][5] != device_bytes()):
        raise ValueError('Executor memory result differs from contract')
    return {'command': cmd, 'offset': offset, 'slot': slot, 'variant': variant, 'kind': expected['kind'],
            'stop': hex(expected['stop']) if expected['status'] == 1 else None,
            'error': [hex(expected['error'][0]), expected['error'][1]] if expected['status'] != 1 else None,
            'steps': actual['steps'], 'events_sha256': pinned.digest(json.dumps(actual['events']).encode())}


def static_tables(code):
    """Decode both thunk tables from original words; must agree with the declared map."""
    found = {}
    for cmd in range(0x20):
        thunk = LOW_TABLE + 4 * cmd
        found[cmd] = thunk_target(code, thunk)
    for index in range(16):
        found[0x80 | index] = thunk_target(code, HIGH_TABLE + 4 * index)
    return found


def declared_tables():
    """Expected thunk decode, written from the listing independently of the decoder above."""
    table = {0x00: 'rts'}
    for cmd in range(1, 0x20):
        table[cmd] = LOW_HANDLERS.get(cmd, IGNORE)
    for index in range(16):
        table[0x80 | index] = HIGH_HANDLERS.get(index, IGNORE)
    table.update({0x84: 0x1DAC, 0x8C: 'not-a-thunk:1b6a', 0x8D: 'not-a-thunk:0000', 0x8F: 'not-a-thunk:1b6a'})
    return table


def thunk_target(code, thunk):
    op = u16(code, thunk)
    if op == 0x4E75:
        return 'rts'
    if op == 0x4EFA:
        return thunk + 2 + int.from_bytes(code[thunk + 2:thunk + 4], 'big', signed=True)
    if op == 0x4EF9:
        return u32(code, thunk + 2)
    return 'not-a-thunk:%04x' % op


# ------------------------------------------------------------------- natural

def decode_ring(ram):
    host, work, live = u16(ram, HOST_OFFSET), u16(ram, OFFSET), u16(ram, STAMP)
    if host != work or host % 16 or host >= 0x800:
        raise ValueError('Ring offsets disagree, are unaligned or wrapped; history is not complete')
    count = host // 16
    entries = [bytes(ram[RING + 16 * i:RING + 16 * i + 16]) for i in range(RING_ENTRIES)]
    if entries[count] != b'\xff' * 16:
        raise ValueError('Ring end marker missing at the published offset')
    if any(not e[0] for e in entries[:count]) or any(any(e) for e in entries[count + 1:]):
        raise ValueError('Ring holds empty records or a non-zero tail; history is not complete')
    return {'count': count, 'live_stamp': live, 'entries': entries[:count]}


def commands_from(entries):
    rows, total = [], 0
    for index, entry in enumerate(entries):
        stamp = u16(entry, 14)
        total += stamp
        rows.append({'index': index, 'command': entry[0], 'bytes_1_13': entry[1:14].hex(),
                     'stamp_ticks': stamp, 'cumulative_ticks': total})
    return rows


def dispatch_thunk(cmd):
    return LOW_TABLE + 4 * cmd if cmd < 0x80 else HIGH_TABLE + 4 * (cmd & 0xF)


def natural_checks(snapshots, epoch, counter_disc):
    """Cross-check decoded rings against one natural coverage epoch; raise on any mismatch."""
    frames = sorted(snapshots)
    rings = {f: decode_ring(snapshots[f]) for f in frames}
    for a, b in zip(frames, frames[1:]):
        if rings[b]['entries'][:rings[a]['count']] != rings[a]['entries']:
            raise ValueError('Earlier snapshot ring is not a prefix of a later one')
    final = rings[frames[-1]]
    if frames[-1] != epoch['last_frame'] + 1:
        raise ValueError('Final snapshot does not close the coverage epoch')
    words = {w[0]: w for w in epoch['words']}
    edges = collections.Counter()
    for frm, to, kind, _vector, count, _first in epoch['edges']:
        if kind == 'flow':
            edges[frm, to] += count
    commands = [e[0] for e in final['entries']]
    by_command = collections.Counter(commands)
    observed = {to: n for (frm, to), n in edges.items() if frm in (LOW_JSR, HIGH_JSR)}
    expected = collections.Counter(dispatch_thunk(c) for c in commands)
    if observed != dict(expected):
        raise ValueError('Ring command counts differ from natural table dispatch edges')
    if edges[EXEC_CALLER, EXEC_ENTRY] != final['count'] or words.get(EXEC_ENTRY, [0, 0])[1] != final['count']:
        raise ValueError('Executor natural entries differ from ring records')
    low = sum(n for c, n in by_command.items() if c < 0x80)
    if words.get(0x1B4E, [0, 0])[1] != low or words.get(0x1AC2, [0, 0])[1] != final['count'] - low:
        raise ValueError('Executor low/high path counts differ from ring records')
    interrupts = epoch['exceptions'].get(TIMER_VECTOR, 0)
    ticks = sum(u16(e, 14) for e in final['entries']) + final['live_stamp']
    if ticks != interrupts or words.get(INTERRUPT_COUNTER_STORE, [0, 0])[1] != interrupts:
        raise ValueError('Ring stamps plus live counter differ from natural vector-26 interrupts')
    phases = {f: u16(snapshots[f], COUNTER) for f in frames}
    if any(p & 0xFCFF for p in phases.values()):
        raise ValueError('Counter immediate outside its four phases')
    stores = words.get(COUNTER_STORE, [0, 0])[1]
    if ((counter_disc >> 8) + stores) % 4 != phases[frames[-1]] >> 8:
        raise ValueError('Counter phase differs from natural store count')
    return {'snapshot_frames': frames, 'records': final['count'],
            'records_by_snapshot': {str(f): rings[f]['count'] for f in frames},
            'live_stamp_by_snapshot': {str(f): rings[f]['live_stamp'] for f in frames},
            'by_command': {'0x%02X' % c: n for c, n in sorted(by_command.items())},
            'thunk_dispatch_edges': {'0x%04X' % t: n for t, n in sorted(observed.items())},
            'executor_entries': final['count'], 'low_path': low, 'high_path': final['count'] - low,
            'vector26_interrupts': interrupts, 'stamp_sum': ticks - final['live_stamp'],
            'live_stamp': final['live_stamp'], 'counter_phases': {str(f): hex(p) for f, p in phases.items()},
            'counter_stores': stores, 'commands': commands_from(final['entries'])}


def natural_patch_checks(snapshots, epoch, disc, derived, value):
    """Resident code equals disc bytes plus the isolated self-patch writes; natural path matches."""
    if any(ram[CONFIG] != value for ram in snapshots.values()):
        raise ValueError('Host configuration byte differs from the declared natural value')
    if u32(disc, TABLE_LEA) != TABLE_LEA_WORDS or any(disc[TABLE:TABLE_END]):
        raise ValueError('Runtime record table witness differs from the original image')
    table_changes = {}
    for frame, ram in snapshots.items():
        for lo, hi in ((0, VECTOR_END), (WORK_END, COUNTER), (COUNTER + 2, TABLE), (TABLE_END, CODE_END)):
            if ram[lo:hi] != derived[lo:hi]:
                raise ValueError('Natural resident code differs from derived self-patched image')
        table_changes[str(frame)] = sum(1 for a in range(TABLE, TABLE_END) if ram[a])
    words = {w[0]: w for w in epoch['words']}
    if any(TABLE <= a < TABLE_END for a in words):
        raise ValueError('Natural run executed inside the runtime record table')
    for address, hits, _first, opcode, changed in epoch['words']:
        if address < CODE_END and (changed or opcode != u16(derived, address)):
            raise ValueError('Executed opcode differs from derived self-patched image')
    edges = {(frm, to): count for frm, to, kind, _v, count, _f in epoch['edges'] if kind == 'flow'}
    path = patch_contract(value, 0, 0, 0x2700, disc)['pcs']
    chain = [PATCH_CALLER] + path + [PATCH_RETURN]
    if any(edges.get(pair) != 1 for pair in zip(chain, chain[1:])) or any(
            words.get(pc, [0, 0])[1] != 1 for pc in path):
        raise ValueError('Natural self-patch path differs from the isolated contract path')
    skipped = [pc for group in PATCH_PCS if isinstance(group, tuple) and value >> group[0] & 1 for pc in group[1]]
    if any(pc in words for pc in skipped):
        raise ValueError('Natural run executed a patch store the configuration should skip')
    differing = [a for a in range(VECTOR_END, CODE_END) if derived[a] != disc[a] and a >= WORK_END]
    return {'config_value': value, 'derived_code_bytes_changed': len(differing),
            'natural_path_instructions': len(path), 'snapshots_equal': sorted(snapshots),
            'runtime_table': [hex(TABLE), hex(TABLE_END)], 'runtime_table_nonzero_bytes': table_changes}


# --------------------------------------------------------------- experiment

def apply(code, offset, hexbytes):
    changed = bytearray(code)
    data = bytes.fromhex(hexbytes)
    if changed[offset:offset + len(data)] == data:
        raise ValueError('Control does not change the original bytes')
    changed[offset:offset + len(data)] = data
    return bytes(changed)


def control(name, offset, replacement, code, attempt, cases):
    mutated = apply(code, offset, replacement)
    rejected, reasons = 0, set()
    for case in cases:
        try:
            attempt(mutated, case)
        except ValueError as error:
            rejected += 1
            reasons.add(str(error))
    if not rejected:
        raise ValueError('Original-copy mutation survived: ' + name)
    return {'address': hex(offset), 'replacement': replacement, 'tested': len(cases), 'rejected': rejected,
            'reasons': sorted(reasons), 'mutated_driver_sha256': pinned.digest(mutated)}


def natural_controls(snapshots, epoch, counter_disc, disc, derived, value):
    final = max(snapshots)
    results = {}
    for name in NATURAL_CONTROLS:
        snaps = {f: bytearray(r) for f, r in snapshots.items()}
        ep, image = json.loads(json.dumps(epoch)), derived
        ram = snaps[final]
        if name == 'drop_entry':  # after the earlier snapshots, so only the count checks can see it
            ram[RING + 16 * 80:RING + 0x7F0] = ram[RING + 16 * 81:RING + 0x800]
            ram[RING + 0x7F0:RING + 0x800] = bytes(16)
            for a in (HOST_OFFSET, OFFSET):
                ram[a:a + 2] = (u16(ram, a) - 16).to_bytes(2, 'big')
        elif name == 'stamp_plus_one':  # every snapshot, so only the interrupt total can see it
            for r in snaps.values():
                r[RING + 16 * 10 + 15] = (r[RING + 16 * 10 + 15] + 1) & 0xFF
        elif name == 'prefix_swap':
            middle = sorted(snaps)[1]
            m = snaps[middle]
            a, b = bytes(m[RING + 48:RING + 64]), bytes(m[RING + 64:RING + 80])
            m[RING + 48:RING + 64], m[RING + 64:RING + 80] = b, a
        elif name == 'config_0x80':
            image = patch_contract(0x80, 0, 0, 0x2700, disc)['image']
        elif name == 'counter_plus_one':
            for w in ep['words']:
                if w[0] == COUNTER_STORE:
                    w[1] += 1
        try:
            natural_checks({f: bytes(r) for f, r in snaps.items()}, ep, counter_disc)
            natural_patch_checks({f: bytes(r) for f, r in snaps.items()}, ep, disc, image, value)
        except ValueError as error:
            results[name] = {'rejected': True, 'reason': str(error)}
            continue
        raise ValueError('Natural-data control survived: ' + name)
    return results


def load_natural(run, driver_bytes, coverage_core):
    run = Path(run)
    result = json.loads(pinned.read_bounded(run / 'result.json', 32 * 1024 * 1024))
    raw = pinned.read_bounded(run / 'coverage.json', 64 * 1024 * 1024)
    coverage = json.loads(raw)
    status = coverage.get('status', {})
    if (result.get('status') != 'success' or result.get('mode') != 'enabled'
            or pinned.digest(raw) != result.get('coverage_sha256')
            or coverage.get('schema') != 'neptune.m68k-natural-coverage.v1'
            or any(status.get(k) for k in ('alloc_failed', 'epoch_overflow', 'unepoched_steps'))
            or any(e['edge_overflow'] or e['outside_steps'] for e in coverage['epochs'])):
        raise ValueError('Natural run is not an accepted, intact enabled coverage run')
    epoch = coverage['epochs'][-1]
    snapshots, identities = {}, {}
    for snap in result['snapshots']:
        if snap['frame'] <= epoch['first_frame']:
            continue
        data = pinned.read_bounded(run / ('snapshot-%06d.state' % snap['frame']), 64 * 1024 * 1024)
        if pinned.digest(data) != snap['state_sha256']:
            raise ValueError('Snapshot state differs from its run record')
        snapshots[snap['frame']] = coverage_core.sound_ram(data)
        identities[str(snap['frame'])] = snap['state_sha256']
    if len(snapshots) < 2:
        raise ValueError('Require at least two snapshots inside the SND epoch')
    observations = json.loads(pinned.read_bounded(run / 'observations.json', 256 * 1024 * 1024))
    if coverage_core.digest(observations['frames']) != result['frame_observations_sha256']:
        raise ValueError('Frame observations differ from their run record')
    timing = output_timing(observations['frames'], epoch)
    return snapshots, epoch, {'output_timing': timing,'final_state_sha256': result['final_state_sha256'],
                              'coverage_sha256': result['coverage_sha256'],
                              'frame_observations_sha256': result['frame_observations_sha256'],
                              'selected_core_sha256': result['selected_core_sha256'],
                              'actions_sha256': result['actions_sha256'], 'snapshot_states': identities,
                              'epoch': {k: epoch[k] for k in ('first_frame', 'last_frame', 'steps',
                                                               'opcode_changes', 'outside_steps')}}


def output_timing(frames, epoch):
    """Average emulator output samples per natural vector-26 interrupt and per counter store."""
    interrupts = epoch['exceptions'].get(TIMER_VECTOR, 0)
    stores = next((w[1] for w in epoch['words'] if w[0] == COUNTER_STORE), 0)
    if not interrupts or not stores:
        raise ValueError('Epoch lacks timer interrupts or counter stores')
    first, last = epoch['first_frame'], epoch['last_frame']
    wide = sum(f['audio_frames'] for f in frames[first:last + 1])
    narrow = sum(f['audio_frames'] for f in frames[first + 1:last + 1])
    return {'output_samples_frames_first_to_last': wide, 'output_samples_after_reset_frame': narrow,
            'vector26_interrupts': interrupts, 'counter_stores': stores,
            'samples_per_interrupt_bounds': [round(narrow / interrupts, 4), round(wide / interrupts, 4)],
            'samples_per_counter_store_bounds': [round(narrow / stores, 3), round(wide / stores, 3)],
            'basis': 'emulator output-rate samples per video frame; not hardware timing'}


def natural_replay(code, library, commands, entries):
    """Feed every natural ring record through original 0x1A60 with its natural offset and stamp."""
    ring = bytearray(0x800)  # initial ring contents are not assumed; entry 0 is overwritten
    rows = []
    for row, entry in zip(commands, entries):
        index = row['index']
        result = run_exec(code, library, entry[0], 16 * index, 0, 0, u16(entry, 14), entry[0], 0x2000,
                          payload=entry[:14], ring=bytes(ring))
        if result['kind'] not in ('low-handler', 'high-handler'):
            raise ValueError('Natural record did not reach a handler')
        ring[16 * index:16 * index + 16] = entry
        ring[16 * index + 16:16 * index + 32] = b'\xff' * 16
        rows.append({'index': index, 'command': '0x%02X' % entry[0], 'kind': result['kind'], 'stop': result['stop']})
    return rows, bytes(ring)


def execute(code, disc, library, naturals):
    report = {}
    if static_tables(code) != declared_tables():
        raise ValueError('Original thunk tables differ from the declared dispatch map')
    # Self-patch for every host configuration value.
    rows, images = [], {}
    for case in patch_cases():
        row, image = run_patch(code, library, disc, *case)
        rows.append(row)
        images[case[0]] = image
    site_map = {str(bit): [hex(site), longs * 4] for bit, site, longs in PATCH_SITES}
    report['self_patch'] = {
        'entry': hex(PATCH_ENTRY), 'caller': hex(PATCH_CALLER), 'cases': len(rows),
        'results_sha256': pinned.digest(json.dumps(rows, sort_keys=True).encode()),
        'site_by_clear_bit': site_map, 'unused_bits': [2, 0],
        'controls': {name: control(name, off, rep, code,
                                   lambda m, c: run_patch(m, library, disc, *c), patch_cases()[::17])
                     for name, off, rep in PATCH_CONTROLS}}
    # Executor sweep on the image derived for the natural configuration (checked below).
    natural_value = None
    for snapshots, _epoch, _identity in naturals:
        values = {ram[CONFIG] for ram in snapshots.values()}
        if len(values) != 1 or (natural_value is not None and values != {natural_value}):
            raise ValueError('Natural host configuration differs between snapshots or runs')
        natural_value = values.pop()
    derived = images[natural_value]
    rows = [run_exec(derived, library, *case) for case in exec_cases()]
    outcomes = {}
    for cmd in range(256):
        kind, target = exec_outcome(cmd)
        outcomes['0x%02X' % cmd] = [kind, None if target is None else hex(target)]
    report['executor'] = {
        'entry': hex(EXEC_ENTRY), 'caller': hex(EXEC_CALLER), 'image': 'disc + isolated 0x1768 writes for natural 0x4E1',
        'cases': len(rows), 'results_sha256': pinned.digest(json.dumps(rows, sort_keys=True).encode()),
        'outcome_by_command': outcomes,
        'kind_counts': dict(collections.Counter(r['kind'] for r in rows)),
        'controls': {name: control(name, off, rep, derived,
                                   lambda m, c: run_exec(m, library, *c), exec_cases()[::5])
                     for name, off, rep in EXEC_CONTROLS}}
    # Natural checks, per run, then the natural replay.
    runs, first = [], None
    for snapshots, epoch, identity in naturals:
        checks = natural_checks(snapshots, epoch, u16(disc, COUNTER))
        patch = natural_patch_checks(snapshots, epoch, disc, derived, natural_value)
        final = decode_ring(snapshots[max(snapshots)])
        replay, ring = natural_replay(derived, library, checks['commands'], final['entries'])
        if ring[:16 * final['count'] + 16] != snapshots[max(snapshots)][RING:RING + 16 * final['count'] + 16]:
            raise ValueError('Replayed ring differs from the natural ring')
        dispatched = {r['command']: r['stop'] for r in replay}
        controls = natural_controls(snapshots, epoch, u16(disc, COUNTER), disc, derived, natural_value)
        summary = {'identity': identity, 'checks': {k: v for k, v in checks.items() if k != 'commands'},
                   'self_patch': patch, 'replay_dispatch': dispatched, 'natural_controls': controls}
        if first is None:
            first = checks['commands']
        elif checks['commands'] != first:
            raise ValueError('Natural command stream differs between repeated runs')
        runs.append(summary)
    report['natural'] = {'runs': runs, 'commands': first,
                         'commands_sha256': pinned.digest(json.dumps(first, sort_keys=True).encode())}
    report['counter'] = {'immediate': hex(COUNTER), 'store': hex(COUNTER_STORE), 'disc_value': hex(u16(disc, COUNTER)),
                         'rule': 'value := (value + 0x100) & 0x300 on every store'}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--source-file', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--run', type=Path, action='append', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    report = {'schema': SCHEMA, 'status': 'failure', 'release': 'usa-mk81070-v1003', 'module': 'SND',
              'cpu': 'm68000', 'load_address': 0, 'source_path': 'BOMSS/PROGRAM.BIN[0x44:0x6418]',
              'lifetime': 'SND game sound driver (natural 68000 epoch after the second reset)',
              'driver_sha256': sound.SOURCES['SND'][1], 'native_identity': native.identity(),
              'probe_sha256': pinned.digest(Path(__file__).read_bytes()),
              'limitations': [
                  'Isolated CPU interpreter for 0x1768/0x1A60; no SCSP model, interrupts or bus timing',
                  'Executor contract stops at handler entry; handler semantics are not recovered here',
                  'Natural evidence is one Beetle lineage, one route and one release',
                  'Command-name meanings from Sega driver documentation remain source hypotheses']}
    try:
        fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        print('FAIL: report requires a fresh writable path')
        return 1
    with os.fdopen(fd, 'w') as output:
        phase = 'source_identity'
        try:
            import run_m68k_coverage as coverage_core
            disc = sound.source_bytes(args.source_file, 'SND')
            report['driver_bytes_sha256'] = pinned.digest(disc)
            phase = 'prepared_identity'
            library = native.Library(args.prepared)
            report['prepared_binary_sha256'] = pinned.digest(library.path.read_bytes())
            phase = 'owned_smoke'
            report['owned_smoke'] = native.smoke(library)
            phase = 'natural_inputs'
            naturals = [load_natural(run, disc, coverage_core) for run in args.run]
            phase = 'original_execution'
            report.update(execute(disc, disc, library, naturals), status='success')
        except Exception as error:  # report every failure, never a partial success
            report['error'] = {'phase': phase, 'type': type(error).__name__, 'reason': str(error)}
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': report['status'], 'error': report.get('error')}))
    return 0 if report['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
