"""Synthetic format and failure controls, not original-game extraction evidence."""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import state_graphics as sg
import export_vdp1 as texture


def record(name, value):
    return bytes([len(name)]) + name.encode() + struct.pack("<I", len(value)) + value


def container(sections):
    payload = b""
    for name, fields in sections:
        content = b"".join(record(k, v) for k, v in fields)
        payload += name.encode().ljust(32, b"\0") + struct.pack("<I", len(content)) + content
    return b"MDFNSVST" + bytes(8) + struct.pack("<II", sg.VERSION, 32 + len(payload)) + bytes(8) + payload


def fixture(order="little"):
    vram = bytearray(0x80000)
    words = [0, 0, 0xA8, 0, 0x20, 0x101] + [0] * 10
    vram[:32] = struct.pack(">16H", *words)
    vram[0x100:0x110] = struct.pack(">8H", *[0x801F, 0x83E0, 0xFC00, 0xFFFF] * 2)
    encode = lambda b: sg.cpu_words(b, order)  # swapping is its own inverse
    sections = {"VDP1": {"VRAM": encode(bytes(vram))},
                "VDP2": {"VRAM": bytes(0x80000), "CRAM": encode(bytes.fromhex("001f03e0") + bytes(4092)),
                         "RawRegs": bytes(0x200)}}
    for section, fields in sg.SCALARS.items():
        for key, size in fields.items():
            value = -1 if key == "RetCommandAddr" else 0
            sections[section][key] = value.to_bytes(size, order, signed=value < 0)
    return sections, bytes(vram)


def pack(sections):
    return container([(s, list(f.items())) for s, f in sections.items()])


class StateGraphicsTests(unittest.TestCase):
    def test_orders_native_data_and_existing_exporter(self):
        for order in ("little", "big"):
            sections, want = fixture(order)
            info, files = sg.graphics(pack(sections), order, synthetic=True)
            self.assertEqual(files["vram.bin"], want)
            self.assertEqual(files["vdp2-cram.bin"][:4], bytes.fromhex("001f03e0"))
            self.assertEqual(info["context"]["VDP1"]["RetCommandAddr"], -1)
            report, native = texture.decode(files["vram.bin"], 0)
            self.assertEqual((report["width"], report["height"]), (8, 1))
            self.assertEqual(native["texels.u16be"][:6], bytes.fromhex("801f83e0fc00"))
            self.assertIn("source-pattern.png", native)

    def test_word_index_conversion(self):
        sections, _ = fixture()
        sections["VDP1"]["CurCommandAddr"] = (0x120).to_bytes(4, "little")
        result, _ = sg.graphics(pack(sections), "little", synthetic=True)
        self.assertEqual(result["context"]["VDP1"]["current_command_byte_offset"], 0x240)

    def test_padding_unknown_fields_and_reordering(self):
        sections, _ = fixture()
        sections["extra"] = {"unknown": b"\0\1\2", "empty": b""}
        raw = container([(s, list(reversed(list(f.items())))) for s, f in reversed(list(sections.items()))])
        result, _ = sg.graphics(raw + bytes(29), "little", synthetic=True)
        self.assertEqual(result["padding_bytes"], 29)
        self.assertIn("unknown", result["fields"]["extra"])

    def test_bad_headers_lengths_padding_wrappers(self):
        raw = container([("A", [("x", b"abc")])])
        bad = [b"", raw[:31], b"wrapper" + raw, raw + b"x", raw[:-1],
               raw[:16] + struct.pack("<I", 0x900) + raw[20:],
               raw[:20] + struct.pack("<I", 31) + raw[24:],
               raw[:20] + struct.pack("<I", len(raw) + 1) + raw[24:],
               raw[:8] + b"x" + raw[9:], raw[:24] + b"x" + raw[25:]]
        for value in bad:
            with self.subTest(size=len(value)), self.assertRaises(ValueError):
                sg.parse(value)
        for cut in range(32, len(raw)):
            value = raw[:20] + struct.pack("<I", cut) + raw[24:cut]
            if cut == 32:  # an empty framed state parses but is not graphics
                continue
            with self.subTest(cut=cut), self.assertRaises(ValueError):
                sg.parse(value)

    def test_duplicate_and_bad_names(self):
        for sections in [ [("A", [("x", b"1"), ("x", b"2")])],
                          [("A", []), ("A", [])], [("", [])], [("A", [("", b"")])],
                          [("A", [("\n", b"")])], [("\n", [])] ]:
            with self.assertRaises(ValueError):
                sg.parse(container(sections))
        raw = bytearray(container([("A", [])])); raw[34] = 1
        with self.assertRaises(ValueError): sg.parse(bytes(raw))
        with self.assertRaises(ValueError):
            sg.parse(container([(str(n), []) for n in range(257)]))
        with patch.object(sg, "MAX_FIELDS", 1), self.assertRaises(ValueError):
            sg.parse(container([("A", [("x", b"1"), ("y", b"2")])]))

    def test_required_fields_and_sizes(self):
        sections, _ = fixture()
        for s, k in [("VDP1", "VRAM"), ("VDP2", "CRAM"), ("VDP1", "TVMR")]:
            bad = copy.deepcopy(sections); bad[s][k] = b""
            with self.assertRaises(ValueError): sg.graphics(pack(bad), "little", synthetic=True)
        with self.assertRaises(ValueError): sg.cpu_words(b"abc", "little")
        with self.assertRaises(ValueError): sg.cpu_words(b"ab", "unknown")

    def test_original_witness_mandatory_and_order_sensitive(self):
        sections, _ = fixture()
        with self.assertRaises(ValueError): sg.graphics(pack(sections), "little", synthetic=False)
        expected = bytes(range(64))
        high = bytearray(0x100000); high[0xA4B0:0xA4F0] = sg.cpu_words(expected, "little")
        sections["MAIN"] = {"WorkRAMH": bytes(high)}
        # This mock tests the adapter comparison; existing kernel probe tests own
        # actual kernel size/hash rejection. This is never a real-source receipt.
        with patch.object(sg, "kernel_bytes", return_value=bytes(0x44B0) + expected):
            info, _ = sg.graphics(pack(sections), "little", synthetic=False, kernel=Path("fixture"))
            self.assertEqual(info["byte_order_witness"]["status"], "original-code-span-matched")
            with self.assertRaises(ValueError):
                sg.graphics(pack(sections), "big", synthetic=False, kernel=Path("fixture"))

    def test_sidecar_identity_output_and_fail_closed_paths(self):
        sections, _ = fixture(); raw = pack(sections)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); state = root / "checkpoint.state"; state.write_bytes(raw)
            meta = {"schema": "neptune.libretro-checkpoint.v1", "frame": 10,
                    "state_path": state.name, "state_bytes": len(raw), "state_sha256": sg.sha(raw),
                    "identity": {k: "a" * 64 for k in ("lock_sha256", "core_sha256", "settings_sha256", "frontend_sha256", "python_sha256")}}
            sidecar = root / "checkpoint.json"; sidecar.write_bytes(sg.json_bytes(meta))
            args = dict(order="little", core_revision=sg.CORE_REVISION, capture_id="fixture", synthetic=True)
            first = sg.adapt(sidecar, root / "one", **args)
            second = sg.adapt(sidecar, root / "two", **args)
            self.assertEqual(first, second)
            vram = (root / "one/vram.bin").read_bytes()
            capture = texture.provenance((root / "one/capture.json").read_bytes(), vram)
            self.assertTrue(capture["synthetic"])
            with self.assertRaises(FileExistsError): sg.adapt(sidecar, root / "one", **args)
            for key, value in [("state_sha256", "0" * 64), ("state_bytes", True),
                               ("frame", True), ("identity", {}), ("state_path", "../outside"),
                               ("state_path", str(state))]:
                bad = copy.deepcopy(meta); bad[key] = value; sidecar.write_bytes(sg.json_bytes(bad))
                with self.assertRaises(ValueError): sg.adapt(sidecar, root / "bad", **args)
                self.assertFalse((root / "bad").exists())
            sidecar.write_bytes(b'{"schema":1,"schema":2}')
            with self.assertRaises(ValueError): sg.adapt(sidecar, root / "bad", **args)

    def test_write_failure_cleans_only_new_output(self):
        sections, _ = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "s").write_bytes(pack(sections))
            identity = {k: "a" * 64 for k in ("lock_sha256", "core_sha256", "settings_sha256", "frontend_sha256", "python_sha256")}
            (root / "c").write_bytes(sg.json_bytes({"schema": "neptune.libretro-checkpoint.v1", "frame": 1,
                "identity": identity, "state_path": "s", "state_bytes": len(pack(sections)), "state_sha256": sg.sha(pack(sections))}))
            with patch.object(Path, "write_bytes", side_effect=OSError("full")), self.assertRaises(OSError):
                sg.adapt(root / "c", root / "out", order="little", core_revision=sg.CORE_REVISION,
                         capture_id="fixture", synthetic=True)
            self.assertFalse((root / "out").exists()); self.assertTrue((root / "s").exists())


if __name__ == "__main__":
    unittest.main()
