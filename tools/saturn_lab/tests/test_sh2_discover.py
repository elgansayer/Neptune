"""Owned synthetic SH-2 programs only: no original game code, BIOS or upstream source."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare_discovery
import sh2_discover as sd

BASE = 0x06004000


class Asm:
    """Two-pass assembler for the handful of encodings these fixtures need."""

    def __init__(self, base=BASE):
        self.base, self.items = base, []

    def label(self, name):
        self.items.append(("label", name))
        return self

    def w(self, *words):
        self.items.extend(("w", word) for word in words)
        return self

    def branch(self, opcode, name):  # bra/bsr (12-bit) or bt/bf/bt.s/bf.s (8-bit)
        self.items.append(("b", opcode, name))
        return self

    def movl(self, reg, name):
        self.items.append(("movl", reg, name))
        return self

    def mova(self, name):
        self.items.append(("mova", name))
        return self

    def align4(self):
        self.items.append(("align4",))
        return self

    def long(self, value):
        self.items.append(("long", value))
        return self

    def rel16(self, name, origin):
        self.items.append(("rel16", name, origin))
        return self

    def _layout(self):
        labels, address = {}, self.base
        for item in self.items:
            if item[0] == "label":
                labels[item[1]] = address
            elif item[0] == "align4":
                address += address & 2
            elif item[0] == "long":
                address += 4
            else:
                address += 2
        return labels

    def build(self):
        labels, out, address = self._layout(), bytearray(), self.base
        value = lambda v: labels[v] if isinstance(v, str) else v
        for item in self.items:
            kind = item[0]
            if kind == "label":
                continue
            if kind == "align4":
                if address & 2:
                    out += (0x0009).to_bytes(2, "big")
                    address += 2
                continue
            if kind == "long":
                out += value(item[1]).to_bytes(4, "big")
                address += 4
                continue
            if kind == "w":
                word = item[1]
            elif kind == "b":
                disp = (labels[item[2]] - address - 4) // 2
                word = item[1] | (disp & (0xFFF if item[1] >> 12 in (0xA, 0xB) else 0xFF))
            elif kind == "movl":
                disp = (labels[item[2]] - ((address & ~3) + 4)) // 4
                assert 0 <= disp < 256 and labels[item[2]] % 4 == 0
                word = 0xD000 | item[1] << 8 | disp
            elif kind == "mova":
                disp = (labels[item[1]] - ((address & ~3) + 4)) // 4
                word = 0xC700 | disp
            elif kind == "rel16":
                word = (labels[item[1]] - labels[item[2]]) & 0xFFFF
            out += word.to_bytes(2, "big")
            address += 2
        return bytes(out), labels


NOP, RTS = 0x0009, 0x000B


def run(data, seeds, leads=()):
    discovery = sd.Discovery(sd.Module(data, BASE), [(s, "test") for s in seeds], list(leads))
    discovery.run()
    return discovery


def switch_body(a, condition=0x8900):
    """SHC switch: mov #3,r1; cmp/hs r1,r0; b[tf] default; shll r0; mov r0,r1; mova T,r0;
    mov.w @(r0,r1),r0; braf r0 -- three rel16 entries relative to braf + 4."""
    a.w(0xE103, 0x3012).branch(condition, "default").w(0x4000, 0x6103).mova("table")
    a.w(0x001D).label("braf").w(0x0023, NOP).label("origin").align4().label("table")
    a.rel16("c0", "origin").rel16("c1", "origin").rel16("c2", "origin")
    a.label("c0").w(RTS, NOP).label("c1").w(RTS, NOP).label("c2").w(RTS, NOP)
    a.label("default").w(RTS, NOP)
    return a


def call_program():
    a = Asm()
    a.label("main").movl(1, "lit_f2").w(0x410B, NOP)          # jsr @r1 -> f2
    a.branch(0xB000, "f3").w(NOP)                              # bsr f3
    a.movl(2, "lit_f4").w(0x422B, NOP)                         # jmp @r2 -> f4 (frame-opening tail)
    a.align4().label("lit_f2").long("f2").label("lit_f4").long("f4")
    a.label("f2").w(RTS, NOP)
    a.label("f3")
    switch_body(a)
    a.label("f4").w(0x2FE6, 0x6EF6, RTS, NOP)                  # push r14; pop r14; rts
    return a.build()


class DecoderTests(unittest.TestCase):
    def test_selected_encodings_and_illegal_words(self):
        cases = {0x000B: ("rts", "rts"), 0x002B: ("rte", "rte"), 0x0009: ("nop", None),
                 0x4F22: ("sts.l pr,@-rn", None), 0xD123: ("mov.l @(disp,pc),rn", None),
                 0xA000: ("bra label", "bra"), 0xB000: ("bsr label", "bsr"), 0x8900: ("bt label", "bt"),
                 0x8D00: ("bt/s label", "bt/s"), 0x402B: ("jmp @rm", "jmp"), 0x400B: ("jsr @rm", "jsr"),
                 0x0023: ("braf rm", "braf"), 0x0003: ("bsrf rm", "bsrf"), 0xC700: ("mova @(disp,pc),r0", None),
                 0xC340: ("trapa #imm", "trapa"), 0x001B: ("sleep", None)}
        for word, (op, flow) in cases.items():
            ins = sd.decode(word)
            self.assertEqual((ins.op, ins.flow), (op, flow), hex(word))
        for word in (0xF000, 0x0601, 0x060B, 0x2003, 0x3001, 0x3009, 0x8200, 0x4C0C, 0x0018 | 0x0100):
            self.assertTrue(sd.decode(word).illegal, hex(word))
        self.assertEqual(sd.decode(0x6EF6).writes, {14, 15})
        self.assertEqual(sd.decode(0x4F26).writes, {15})            # lds.l @r15+,pr
        self.assertTrue(sd.decode(0x8D00).delayed and not sd.decode(0x8900).delayed)
        legal = sum(1 for word in range(0x10000) if not sd.decode(word).illegal)
        self.assertGreater(legal, 50000)
        self.assertLess(legal, 0x10000)

    def test_pc_relative_addresses_and_aliases(self):
        self.assertEqual(sd.pcrel_address(sd.decode(0xD101), 0x06004002), 0x06004008)
        self.assertEqual(sd.pcrel_address(sd.decode(0x9101), 0x06004002), 0x06004008)
        self.assertEqual(sd.branch_target(sd.decode(0xAFFE), 0x06004010), 0x06004010)
        self.assertEqual(sd.canonical(0x2600623A), 0x0600623A)
        self.assertEqual(sd.canonical(0x0600623A), 0x0600623A)
        self.assertEqual(sd.canonical(0xFFFFFE10), 0xFFFFFE10)


class DiscoveryTests(unittest.TestCase):
    def test_calls_tail_and_bounded_switch(self):
        data, labels = call_program()
        discovery = run(data, [labels["main"]])
        entries = set(discovery.functions)
        self.assertEqual(entries, {labels["main"], labels["f2"], labels["f3"], labels["f4"]})
        self.assertIn("jsr-literal", discovery.provenance[labels["f2"]])
        self.assertIn("bsr", discovery.provenance[labels["f3"]])
        self.assertIn("jmp-literal-tail", discovery.provenance[labels["f4"]])
        self.assertTrue(all(discovery.tier[e] == "A" for e in entries))
        (switch,) = discovery.functions[labels["f3"]].switches
        self.assertEqual((switch["form"], switch["entries"], switch["bounded"], switch["stride"]),
                         ("braf-rel16", 3, True, 2))
        self.assertEqual(set(switch["targets"]), {labels["c0"], labels["c1"], labels["c2"]})
        self.assertIn(labels["lit_f2"], discovery.literal)
        self.assertFalse(discovery.conflicts())
        report = sd.inventory(discovery, {"source_sha256": hashlib.sha256(data).hexdigest()})
        self.assertEqual(report["summary"]["functions_by_tier"], {"A": 4, "B": 0, "C": 0, "R": 0})
        self.assertEqual(report["summary"]["switch_tables"], 1)

    def test_wrong_bound_direction_is_not_a_bound(self):
        # bf default after cmp/hs r1,r0 keeps indices >= 3 on the switch path: no finite bound.
        data, labels = switch_body(Asm().label("f"), condition=0x8B00).build()
        discovery = run(data, [labels["f"]])
        (switch,) = discovery.functions[labels["f"]].switches
        self.assertFalse(switch["bounded"])
        bounded, labels2 = switch_body(Asm().label("f")).build()
        (switch2,) = run(bounded, [labels2["f"]]).functions[labels2["f"]].switches
        self.assertTrue(switch2["bounded"])

    def test_register_resolution_pointer_slot_and_bios_handler(self):
        a = Asm()
        a.label("main").w(0x2FE6, 0x4F22).movl(14, "lit_g")
        a.w(0x4E0B, NOP)                                   # jsr @r14 (straight line)
        a.branch(0xA000, "again").w(NOP).label("again")   # bra resets constants
        a.w(0x4E0B, NOP)                                   # jsr @r14 resolved by the unique-literal rule
        a.movl(1, "lit_slot").w(0x6012)                    # mov.l @r1,r0 (BIOS SYS_SETUINT slot)
        a.movl(5, "lit_handler").w(0x400B, 0xE440)         # jsr @r0; mov #0x40,r4 (vector in the slot)
        a.w(0x4F26, 0x6EF6, RTS, NOP)
        a.align4().label("lit_g").long("g").label("lit_slot").long(sd.SYS_SETUINT_SLOT)
        a.label("lit_handler").long("handler")
        a.label("g").w(RTS, NOP)
        a.label("handler").w(0x2FE6, 0x6EF6, 0x002B, NOP)  # rte
        data, labels = a.build()
        discovery = run(data, [labels["main"]])
        self.assertIn("jsr-literal", discovery.provenance[labels["g"]])
        self.assertIn("jsr-register", discovery.provenance[labels["g"]])
        self.assertIn("sys-setuint-handler:40", discovery.provenance[labels["handler"]])
        self.assertEqual(discovery.tier[labels["handler"]], "A")
        main = discovery.functions[labels["main"]]
        self.assertEqual([(kind, slot) for _, kind, slot in main.unresolved], [("jsr", sd.SYS_SETUINT_SLOT)])
        self.assertEqual(len(discovery.resolved), 1)

    def test_pointer_tiers_closed_task_stub_and_prologue_gap(self):
        a = Asm()
        a.label("main").movl(4, "lit_task").movl(1, "lit_ext").w(0x410B, NOP)   # create(task) at external
        a.movl(4, "lit_stub").movl(1, "lit_ext").w(0x410B, NOP)
        a.w(RTS, NOP).align4()
        a.label("lit_task").long("task").label("lit_ext").long(0x06000400).label("lit_stub").long("stub")
        # closed task body: never returns, eight-plus clean instructions
        a.label("task").w(0x2FE6, 0xE001, 0xE102, 0xE203, 0x7001, 0x7101, 0x7201).label("loop")
        a.w(0x7301, 0x7401).branch(0xA000, "loop").w(NOP)
        a.label("stub").w(RTS, NOP)
        a.align4().label("table").long("tabled")
        a.label("tabled").w(0x2FE6, 0x4F22, 0xE001, 0x4F26, RTS, 0x6EF6)
        a.label("gap").w(0x4F22, 0xE001, 0xE102, 0xE203, 0x7001, 0x7101, 0x7201, 0x4F26, RTS, NOP)
        data, labels = a.build()
        discovery = run(data, [labels["main"]])
        self.assertEqual(discovery.tier[labels["task"]], "B")
        self.assertIn("argument-pointer", discovery.provenance[labels["task"]])
        self.assertIn("literal-pointer", discovery.provenance[labels["task"]])
        self.assertEqual(discovery.tier[labels["stub"]], "B")
        self.assertEqual(discovery.tier[labels["tabled"]], "B")
        self.assertIn("table-pointer", discovery.provenance[labels["tabled"]])
        self.assertEqual(discovery.tier[labels["gap"]], "C")
        self.assertEqual(discovery.functions[labels["task"]].returns, 0)

    def test_data_that_decodes_as_rts_is_not_a_stub(self):
        a = Asm()
        a.label("main").movl(4, "lit_data").movl(1, "lit_ext").w(0x410B, NOP, RTS, NOP).align4()
        a.label("lit_data").long("data").label("lit_ext").long(0x06000400)
        a.label("data").w(0x000B, 0x000C, 0x000D, 0x000E)  # sequential halfword table, not code
        data, labels = a.build()
        discovery = run(data, [labels["main"]])
        self.assertNotIn(labels["data"], discovery.functions)
        self.assertFalse(sd.is_return_stub(discovery.module, labels["data"]))

    def test_lead_tier_is_separate_and_only_seeds_unclassified_bytes(self):
        data, labels = call_program()
        island = Asm(BASE + len(data)).label("x").w(0xE001, RTS, NOP)
        extra, more = island.build()
        discovery = run(data + extra, [labels["main"]], leads=[(more["x"], "runtime"), (labels["c1"], "runtime")])
        self.assertEqual(discovery.tier[more["x"]], "R")
        self.assertEqual(discovery.lead_status[more["x"]], "seeded")
        self.assertEqual(discovery.lead_status[labels["c1"]], "instruction-in-function")
        self.assertNotIn(labels["c1"], discovery.functions)

    def test_invalid_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            sd.Module(b"\x00", BASE)
        with self.assertRaises(ValueError):
            sd.Module(b"\x00\x09", BASE + 1)
        with self.assertRaises(ValueError):
            sd.Discovery(sd.Module(b"\x00\x0b\x00\x09", BASE), [(BASE + 8, "outside")])


def chain_program(count=48):
    """Functions that call their neighbours by bsr and a far partner by jsr literal."""
    a = Asm()
    for k in range(count):
        a.label("f%d" % k).w(0x2FE6, 0x4F22).movl(1, "l%d" % k).w(0x410B, NOP)
        a.branch(0xB000, "f%d" % ((k + 1) % count)).w(NOP, 0x4F26, RTS, 0x6EF6).align4()
        a.label("l%d" % k).long("f%d" % ((k + count // 2) % count))
    return a.build()


class BaseCheckTests(unittest.TestCase):
    def test_declared_base_beats_wrong_bases_and_byte_order(self):
        data, labels = chain_program()
        declared = sd.base_metrics(data, BASE)
        self.assertGreater(declared["agreement"], 0.9)
        for delta in (2, -2, 4, 0x10, -0x1000):
            self.assertLess(sd.base_metrics(data, BASE + delta)["agreement"], 0.1, delta)
        swapped = bytes(b for pair in zip(data[1::2], data[0::2]) for b in pair)
        self.assertLess(sd.base_metrics(swapped, BASE)["agreement"], 0.1)

    def test_cli_base_check_fails_without_controls_and_passes_with_them(self):
        data, _ = chain_program()
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "m.bin"
            module.write_bytes(data)
            quiet = io.StringIO()
            with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                self.assertEqual(sd.main(["base-check", "--module", str(module), "--base", "06004000",
                                          "--report", str(Path(tmp) / "a.json")]), 1)
                self.assertEqual(sd.main(["base-check", "--module", str(module), "--base", "06004000",
                                          "--wrong-delta=2", "--wrong-delta=-1000",
                                          "--report", str(Path(tmp) / "b.json")]), 0)
            report = json.loads((Path(tmp) / "b.json").read_text())
            self.assertTrue(report["passed"])
            self.assertEqual([c["kind"] for c in report["controls"]], ["wrong-base", "wrong-base", "byte-swapped"])


class CommandTests(unittest.TestCase):
    def _inventory(self, tmp, data, labels):
        module = Path(tmp) / "m.bin"
        module.write_bytes(data)
        report = Path(tmp) / "inv.json"
        quiet = io.StringIO()
        with contextlib.redirect_stdout(quiet):
            code = sd.main(["inventory", "--module", str(module), "--base", "06004000",
                            "--seed", "%08X" % labels["main"], "--name", "T", "--release", "synthetic",
                            "--expected-sha256", hashlib.sha256(data).hexdigest(), "--report", str(report)])
        self.assertEqual(code, 0)
        return module, report

    def test_inventory_reconcile_and_exclusive_reports(self):
        data, labels = call_program()
        with tempfile.TemporaryDirectory() as tmp:
            module, report = self._inventory(tmp, data, labels)
            inventory = json.loads(report.read_text())
            self.assertEqual(inventory["schema"], sd.SCHEMA)
            self.assertEqual(len(inventory["functions"]), 4)
            references = Path(tmp) / "refs.json"
            references.write_text(json.dumps({"sets": [{"name": "s", "provenance": "test", "addresses": [
                "%08X" % labels["f3"], "%08X" % labels["c1"], "%08X" % labels["lit_f2"],
                "%08X" % (labels["table"]), "%08X" % (BASE + len(data) + 8)]}]}))
            out = Path(tmp) / "rec.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sd.main(["reconcile", "--module", str(module), "--base", "06004000",
                                          "--inventory", str(report), "--references", str(references),
                                          "--report", str(out)]), 0)
            classes = json.loads(out.read_text())["sets"][0]["classes"]
            self.assertEqual(classes, {"entry-tier-A": 1, "instruction-in-function": 1, "literal-data": 1,
                                       "outside-module": 1, "switch-table": 1})
            with self.assertRaises(FileExistsError), contextlib.redirect_stdout(io.StringIO()):
                sd.main(["reconcile", "--module", str(module), "--base", "06004000", "--inventory", str(report),
                         "--references", str(references), "--report", str(out)])

    def test_digest_mismatch_and_wrong_inventory_fail(self):
        data, labels = call_program()
        with tempfile.TemporaryDirectory() as tmp:
            module, report = self._inventory(tmp, data, labels)
            quiet = io.StringIO()
            with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                self.assertEqual(sd.main(["inventory", "--module", str(module), "--base", "06004000",
                                          "--seed", "%08X" % labels["main"], "--name", "T", "--release", "x",
                                          "--expected-sha256", "0" * 64, "--report", str(Path(tmp) / "x.json")]), 1)
                other = Path(tmp) / "other.bin"
                other.write_bytes(data[:-2] + b"\x00\x0b")
                self.assertEqual(sd.main(["reconcile", "--module", str(other), "--base", "06004000",
                                          "--inventory", str(report), "--references", str(report),
                                          "--report", str(Path(tmp) / "y.json")]), 1)
                self.assertEqual(sd.main(["reconcile", "--module", str(module), "--base", "06004000",
                                          "--inventory", str(report), "--references", str(report),
                                          "--report", str(Path(tmp) / "z.json")]), 1)
            self.assertFalse((Path(tmp) / "z.json").exists())

    def test_residency_flags_changed_instruction_halfwords(self):
        data, labels = call_program()
        with tempfile.TemporaryDirectory() as tmp:
            module, report = self._inventory(tmp, data, labels)
            discovery = sd.replay(sd.Module(data, BASE), json.loads(report.read_text()))

            def resident(changed, minimum=2, mapping=BASE):
                ranges, start = [], 0
                for offset in sorted(changed) + [len(data)]:
                    if offset > start:
                        ranges.append({"source_start": hex(start), "source_end_exclusive": hex(offset)})
                    start = offset + 2
                return {"schema": sd.RESIDENT_SCHEMA, "status": "success", "checkpoint_frame": 1,
                        "checkpoint_state_sha256": "0" * 64, "workram_h_sha256": "1" * 64,
                        "source_sha256": hashlib.sha256(data).hexdigest(), "candidate_mapping": hex(mapping),
                        "minimum_exact_range_bytes": minimum, "matching_ranges": ranges}

            clean = sd.residency(discovery, resident([]))
            self.assertEqual(clean["halfwords"]["instruction"]["changed"], 0)
            code_offset = labels["f2"] - BASE
            literal_offset = labels["lit_f4"] - BASE
            flagged = sd.residency(discovery, resident([code_offset, literal_offset]))
            self.assertEqual(flagged["halfwords"]["instruction"]["changed"], 1)
            self.assertEqual(flagged["halfwords"]["literal"]["changed"], 1)
            self.assertEqual(list(flagged["changed_instruction_sites"]), ["%08X" % labels["f2"]])
            with self.assertRaises(ValueError):
                sd.residency(discovery, resident([], minimum=16))
            with self.assertRaises(ValueError):
                sd.residency(discovery, resident([], mapping=BASE + 2))


class CompareLoaderTests(unittest.TestCase):
    def test_upstream_sources_must_match_their_pins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "saturnrecomp" / "recomp").mkdir(parents=True)
            for name in compare_discovery.UPSTREAM_SOURCES:
                (root / "src" / "saturnrecomp" / name).write_text("raise SystemExit('must not run')\n")
            with self.assertRaises(ValueError):
                compare_discovery.load_upstream(root)

    def test_owned_stand_in_runs_through_the_comparison(self):
        data, labels = call_program()
        stand_in = {
            "hw.py": "",
            "sh2.py": "class Image:\n    def __init__(self, data, base):\n        self.data, self.base = data, base\n",
            "recomp/discover.py": (
                "from .. import sh2\n"
                "class Program:\n"
                "    def __init__(self, img, seeds):\n"
                "        self.funcs = {s: None for s in seeds}\n"
                "        self.code, self.data = set(), set()\n"
                "    def summary(self):\n"
                "        return {'functions': len(self.funcs)}\n")}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "saturnrecomp" / "recomp").mkdir(parents=True)
            pins = {}
            for name, text in stand_in.items():
                (root / "src" / "saturnrecomp" / name).write_text(text)
                pins[name] = hashlib.sha256(text.encode()).hexdigest()
            sh2, discover = compare_discovery.load_upstream(root, pins)
            discovery = run(data, [labels["main"]])
            inventory = sd.inventory(discovery, {"source_sha256": hashlib.sha256(data).hexdigest(),
                                                 "base": "%08X" % BASE, "tool_sha256": "t"})
            result = compare_discovery.compare(data, BASE, [labels["main"], labels["c1"]], inventory, sh2, discover)
            self.assertEqual(result["entries"]["both"], 1)
            self.assertEqual(result["entries"]["only_upstream_by_neptune_class"], {"instruction-in-function": 1})
            self.assertEqual(result["entries"]["only_neptune"], 3)
            with self.assertRaises(ValueError):
                compare_discovery.compare(data[:-2] + b"\x00\x0b", BASE, [labels["main"]], inventory, sh2, discover)


if __name__ == "__main__":
    unittest.main()
