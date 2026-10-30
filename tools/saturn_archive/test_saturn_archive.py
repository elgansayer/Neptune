"""Synthetic, zero-copyrighted-byte unit tests for tools/saturn_archive."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from saturn_archive import (  # noqa: E402
    BANK_DECODE_SCHEMA,
    KERNEL_BANK_DIRECTORY_SCHEMA,
    RESIDENT_COMPARISON_SCHEMA,
    ArchiveError,
)
from saturn_archive.banks import (  # noqa: E402
    SECTOR_BYTES,
    audit_program_bin_directory,
    discover_kernel_bank_directory,
    parse_and_decode_bank,
)
from saturn_archive.cli import (  # noqa: E402
    assert_public_safe_text,
    verify_bank_decode_receipt,
    verify_kernel_directory_receipt,
    verify_resident_comparison_receipt,
    write_json_atomic,
)
from saturn_archive.codec import (  # noqa: E402
    hudson_decompress,
    hudson_encode_synthetic,
)
from saturn_archive.compare import compare_bank_to_checkpoint  # noqa: E402


def _build_synthetic_bank(load_base: int = 0x00254000, name: str = "synbank", sectors: int = 4) -> tuple[bytes, dict[str, bytes]]:
    """Build a valid sector-aligned synthetic 0x34 bank with Slots 0, 1, 2, 7, and 8."""
    total_len = sectors * SECTOR_BYTES
    buf = bytearray(total_len)

    # Payloads we expect to recover
    s0_raw_expected = bytes((i * 7) & 0xFF for i in range(64))
    s0_stream = hudson_encode_synthetic(
        2,
        0,
        [0, 1, 2, 8],
        [(0, b) for b in s0_raw_expected],
    )
    pal_expected = struct.pack(">4H", 0x0000, 0x7FFF, 0x03E0, 0x001F)
    tilemap_expected = struct.pack(">4H", 0x0100, 0x0101, 0x0102, 0x0101)
    tilemap_stream = hudson_encode_synthetic(
        2,
        2,
        [0, 2, 8, 14],
        [(0, 0x0100), (1, None), (1, None), (2, None)],
    )
    # Slot 7: dims=0x11 -> cols=16, rows=16 -> 512 bytes, sm=1 dual ring
    grid_stream = hudson_encode_synthetic(
        1,
        1,
        [0, 1],
        [(0, 0x42), (0, 0x99)] + [(1, None)] * 510,
    )
    grid_expected = bytes([0x42, 0x99] * 256)

    # Slot 8: one sb=3 planar compressed 32-byte sprite + one fmt=5 raw 32-byte sprite
    spr_comp_expected = bytes([0x10, 0x11, 0x13, 0x17, 0x16, 0x14, 0x10, 0x10] * 4)
    spr_comp_stream = hudson_encode_synthetic(
        3,
        0,
        [0, 2, 3, 4, 8, 9, 10, 1],
        [(0, 0x10), (1, None), (2, None), (3, None), (4, None), (5, None), (6, None), (7, None)] * 4,
    )
    spr_raw_expected = bytes((0xA0 + i) & 0xFF for i in range(32))

    # Layout offsets inside bank:
    # 0x0034: Slot 0 table (1 entry)
    # 0x0038: Slot 1 table (1 entry)
    # 0x003C: Slot 2 table (2 entries: null + valid)
    # 0x0044: Slot 7 table (1 entry)
    # 0x0048: Slot 8 two-table header [chr_tbl_ptr, meta_tbl_ptr]
    s0_rec_off = 0x0100
    s1_rec_off = 0x0200
    s2_rec_off = 0x0240
    s7_rec_off = 0x0280
    s8_chr_tbl_off = 0x0400
    s8_meta_tbl_off = 0x040C
    s8_desc1_off = 0x0420
    s8_desc2_off = 0x0440
    s8_desc3_off = 0x0460
    s8_pix1_off = 0x0480
    s8_pix2_off = 0x0500

    slot_ptrs = [0] * 11
    slot_ptrs[0] = load_base + 0x0034
    slot_ptrs[1] = load_base + 0x0038
    slot_ptrs[2] = load_base + 0x003C
    slot_ptrs[7] = load_base + 0x0044
    slot_ptrs[8] = load_base + 0x0048

    struct.pack_into(">11I", buf, 0, *slot_ptrs)
    tag = name.encode("ascii")[:8].ljust(8, b"\xff")
    buf[0x2C:0x34] = tag

    struct.pack_into(">I", buf, 0x0034, load_base + s0_rec_off)
    struct.pack_into(">I", buf, 0x0038, load_base + s1_rec_off)
    struct.pack_into(">II", buf, 0x003C, 0, load_base + s2_rec_off)
    struct.pack_into(">I", buf, 0x0044, load_base + s7_rec_off)
    struct.pack_into(">II", buf, 0x0048, load_base + s8_chr_tbl_off, load_base + s8_meta_tbl_off)

    # Slot 0 record: default_dest = 0x25E10000 (VDP2.VRAM + 0x10000), compressed len = 64
    struct.pack_into(">II", buf, s0_rec_off, 0x25E10000, 0x80000000 | len(s0_raw_expected))
    buf[s0_rec_off + 8 : s0_rec_off + 8 + len(s0_stream)] = s0_stream

    # Slot 1 record: cram_byte_offset = 0x0020, color_count = 4
    struct.pack_into(">HH", buf, s1_rec_off, 0x0020, 4)
    buf[s1_rec_off + 4 : s1_rec_off + 4 + len(pal_expected)] = pal_expected

    # Slot 2 record: w=2, h=2, x=0, y=0, flags=1 (compressed)
    struct.pack_into(">HHH", buf, s2_rec_off, 0x0202, 0x0000, 0x0001)
    buf[s2_rec_off + 6 : s2_rec_off + 6 + len(tilemap_stream)] = tilemap_stream

    # Slot 7 record: dims=0x11 (16x16 u16 = 512 bytes)
    buf[s7_rec_off] = 0x11
    buf[s7_rec_off + 1 : s7_rec_off + 1 + len(grid_stream)] = grid_stream

    # Slot 8 chr table: 3 descriptors (desc1 & desc3 share pix1; desc2 uses raw fmt=5 pix2)
    struct.pack_into(
        ">III",
        buf,
        s8_chr_tbl_off,
        load_base + s8_desc1_off,
        load_base + s8_desc2_off,
        load_base + s8_desc3_off,
    )
    struct.pack_into(">I", buf, s8_meta_tbl_off, 0xFFFFFFFF)
    struct.pack_into(">I", buf, s8_desc1_off + 16, load_base + s8_pix1_off)
    struct.pack_into(">I", buf, s8_desc2_off + 16, load_base + s8_pix2_off)
    struct.pack_into(">I", buf, s8_desc3_off + 16, load_base + s8_pix1_off)

    struct.pack_into(">HH", buf, s8_pix1_off, len(spr_comp_expected), 0)
    buf[s8_pix1_off + 4 : s8_pix1_off + 4 + len(spr_comp_stream)] = spr_comp_stream

    struct.pack_into(">HH", buf, s8_pix2_off, len(spr_raw_expected), 5)
    buf[s8_pix2_off + 4 : s8_pix2_off + 4 + len(spr_raw_expected)] = spr_raw_expected

    return bytes(buf), {
        "slot0": s0_raw_expected,
        "slot1": pal_expected,
        "slot2": tilemap_expected,
        "slot7": grid_expected,
        "slot8_comp": spr_comp_expected,
        "slot8_raw": spr_raw_expected,
    }


class CodecUnitTests(unittest.TestCase):
    def test_raw_selector_bits_zero(self) -> None:
        payload = b"\x01\x02\x03\x04\x05"
        encoded = hudson_encode_synthetic(0, 0, [0], [(0, b) for b in payload] + [(0, 0), (0, 0), (0, 0)])
        dec_stream, consumed_stream, meta = hudson_decompress(encoded, 0, 5, streaming_4byte=True)
        self.assertEqual(dec_stream, payload)
        self.assertEqual(consumed_stream, 9)  # 1 header + 8 padded
        self.assertEqual(meta["selector_bits"], 0)
        dec_direct, consumed_direct, _ = hudson_decompress(encoded, 0, 5, streaming_4byte=False)
        self.assertEqual(dec_direct, payload)
        self.assertEqual(consumed_direct, 6)

    def test_all_selector_widths_and_stream_modes(self) -> None:
        # sb=1, sm=0 (u8 single)
        s = hudson_encode_synthetic(1, 0, [0, 3], [(0, 10), (1, None), (1, None), (1, None)])
        out, _, _ = hudson_decompress(s, 0, 4, streaming_4byte=False)
        self.assertEqual(out, bytes([10, 12, 14, 16]))

        # sb=2, sm=3 (u16 dual interleaved rings)
        s_dual16 = hudson_encode_synthetic(
            2,
            3,
            [0, 2, 13, 14],
            [(0, 0x1000), (0, 0x2000), (1, None), (2, None), (0, 0x3000), (0, 0x4000), (3, None), (3, None)],
        )
        out16, _, _ = hudson_decompress(s_dual16, 0, 16, streaming_4byte=False)
        self.assertEqual(
            struct.unpack(">8H", out16),
            (0x1000, 0x2000, 0x1001, 0x1FE0, 0x3000, 0x4000, 0x1001, 0x1FE0),
        )
        # Verify falsification flags diverge on dual-ring stream
        wrong_single, _, _ = hudson_decompress(s_dual16, 0, 16, streaming_4byte=False, dual_ring_enabled=False)
        wrong_pair, _, _ = hudson_decompress(
            s_dual16, 0, 16, streaming_4byte=False, pair_interleave_falsification=True
        )
        self.assertNotEqual(out16, wrong_single)
        self.assertNotEqual(out16, wrong_pair)

        # sb=3 planar vs non-planar on sm=4 (u32 single)
        s_u32 = hudson_encode_synthetic(
            3,
            4,
            [0, 1, 7, 13, 14, 15, 16, 17],
            [(0, 0xAABBCC00), (2, None), (3, None), (4, None), (1, None), (5, None), (0, 1), (1, None)],
        )
        out32, _, _ = hudson_decompress(s_u32, 0, 32, streaming_4byte=True, planar_3bit=True)
        wrong32, _, _ = hudson_decompress(s_u32, 0, 32, streaming_4byte=True, planar_3bit=False)
        self.assertEqual(
            struct.unpack(">8I", out32),
            (0xAABBCC00, 0xAABBCC20, 0xAABBCC00, 0xAABBCC20, 0xAABBCC20, 0xAABBCC20, 1, 1),
        )
        self.assertNotEqual(out32, wrong32)

        # sb=4 (16 methods), sm=2 (u16 single)
        methods16 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 18, 19]
        s_sb4 = hudson_encode_synthetic(4, 2, methods16, [(0, 100), (7, None), (12, None), (13, None)])
        out_sb4, _, _ = hudson_decompress(s_sb4, 0, 8, streaming_4byte=True)
        self.assertEqual(struct.unpack(">4H", out_sb4), (100, 132, 116, 132))

    def test_codec_rejects_malformed_inputs(self) -> None:
        with self.assertRaises(ArchiveError):
            hudson_decompress(b"\x05\x00", 0, 4)  # invalid selector_bits=5
        with self.assertRaises(ArchiveError):
            hudson_decompress(b"\x01\x05\x01\x00", 0, 4)  # invalid stream_mode=5
        with self.assertRaises(ArchiveError):
            hudson_decompress(b"\x01\x00\x14\x00", 0, 4)  # invalid method=20 > 19
        with self.assertRaises(ArchiveError):
            hudson_decompress(b"\x01\x00\x01", 0, 4)  # truncated selector byte
        with self.assertRaises(ArchiveError):
            hudson_decompress(b"\x00\xAA\xBB", 0, 4)  # truncated raw payload


class BankAndDirectoryUnitTests(unittest.TestCase):
    def test_synthetic_bank_decode_and_resident_compare(self) -> None:
        bank_bytes, expected = _build_synthetic_bank(0x00254000, "synbank", sectors=4)
        decoded = parse_and_decode_bank(
            bank_bytes,
            bank_id=5,
            expected_load_base=0x00254000,
            source_sector_offset=12,
        )
        verify_bank_decode_receipt(decoded)
        self.assertEqual(decoded["bank"]["header_name"], "synbank")
        self.assertEqual(
            decoded["decoded_slots"]["slot0_vdp2_patterns"][0]["decoded_sha256"],
            hashlib.sha256(expected["slot0"]).hexdigest(),
        )
        self.assertEqual(
            decoded["decoded_slots"]["slot1_cram_palettes"][0]["decoded_sha256"],
            hashlib.sha256(expected["slot1"]).hexdigest(),
        )
        self.assertEqual(
            decoded["decoded_slots"]["slot2_vdp2_tilemaps"][0]["decoded_sha256"],
            hashlib.sha256(expected["slot2"]).hexdigest(),
        )
        self.assertEqual(
            decoded["decoded_slots"]["slot7_stage_grids"][0]["decoded_sha256"],
            hashlib.sha256(expected["slot7"]).hexdigest(),
        )
        s8 = decoded["decoded_slots"]["slot8_vdp1_sprites"]
        self.assertEqual(s8["descriptor_count"], 3)
        self.assertEqual(s8["unique_pixel_block_count"], 2)
        self.assertEqual(s8["compressed_block_count"], 1)
        self.assertEqual(s8["raw_fmt5_block_count"], 1)

        # Build synthetic resident checkpoint matching both WorkRAML and unpacked VDP1/VDP2/CRAM/WorkRAMH
        wram_l = bytearray(0x100000)
        wram_l[0x54000 : 0x54000 + len(bank_bytes)] = bank_bytes
        wram_h = bytearray(0x100000)
        struct.pack_into(">I", wram_h, 0x0D7E94, 0x060E0000)
        wram_h[0x0E0000 : 0x0E0000 + len(expected["slot7"])] = expected["slot7"]
        vdp1 = bytearray(0x80000)
        vdp1[0x1200 : 0x1200 + 32] = expected["slot8_comp"]
        vdp1[0x1400 : 0x1400 + 32] = expected["slot8_raw"]
        vdp2 = bytearray(0x80000)
        vdp2[0x10000 : 0x10000 + len(expected["slot0"])] = expected["slot0"]
        cram = bytearray(0x1000)
        cram[0x20 : 0x20 + len(expected["slot1"])] = expected["slot1"]

        ckpt = {
            "label": "synthetic-ckpt",
            "frame": 100,
            "checkpoint_json_sha256": "a" * 64,
            "state_bytes": 1234,
            "state_sha256": "b" * 64,
            "identity": {"product": "SYN-000"},
            "kernel_vars": {"bank_mode_0x26006158": 2},
            "regions": {
                "WorkRAML": (0x00200000, bytes(wram_l)),
                "WorkRAMH": (0x06000000, bytes(wram_h)),
                "VDP1.VRAM": (0x05C00000, bytes(vdp1)),
                "VDP2.VRAM": (0x05E00000, bytes(vdp2)),
                "VDP2.CRAM": (0x05F00000, bytes(cram)),
                "SCSP.RAM": (0x05A00000, bytes(0x80000)),
            },
        }
        cmp_res = compare_bank_to_checkpoint(
            bank_bytes,
            bank_id=5,
            source_sector_offset=12,
            expected_load_base=0x00254000,
            checkpoint=ckpt,
        )
        self.assertTrue(cmp_res["raw_workram_l_comparison"]["exact_match"])
        self.assertTrue(cmp_res["decoded_subresource_comparisons"]["slot0_vdp2_patterns"][0]["exact_match"])
        self.assertEqual(
            cmp_res["decoded_subresource_comparisons"]["slot8_vdp1_sprites"]["exact_vdp1_vram_block_matches"],
            2,
        )

    def test_synthetic_kernel_directory_discovery_and_audit(self) -> None:
        # Build 32-entry synthetic kernel bank table at load base 0x06006000
        krnl = bytearray(0x4000)
        krnl_base = 0x06006000
        n = 32
        off_a = 0x2000
        off_b = off_a + n * 2
        off_c = off_b + n * 2
        # Literal pool at +0x0400
        struct.pack_into(">III", krnl, 0x0400, krnl_base + off_a, krnl_base + off_b, krnl_base + off_c)

        prog = bytearray(220 * SECTOR_BYTES + 128)  # include trailing sub-sector bytes
        for idx in range(n):
            if idx == 0:
                sec_off, sec_cnt, dst, bname = 0, 16, 0x00200000, "base0"
            elif idx == 1:
                sec_off, sec_cnt, dst, bname = 16, 16, 0x00200000, "base1"
            else:
                sec_off = 32 + (idx - 2) * 4
                sec_cnt = 4
                dst = 0x002FB000 if idx == n - 1 else 0x00254000
                bname = f"bnk{idx:02d}"
            struct.pack_into(">H", krnl, off_a + idx * 2, sec_off)
            struct.pack_into(">H", krnl, off_b + idx * 2, sec_cnt)
            struct.pack_into(">I", krnl, off_c + idx * 4, dst)
            b_slice, _ = _build_synthetic_bank(dst, bname, sectors=sec_cnt)
            prog[sec_off * SECTOR_BYTES : (sec_off + sec_cnt) * SECTOR_BYTES] = b_slice

        # Plant one unreferenced residual header in the tail at sector 200
        tail_hdr, _ = _build_synthetic_bank(0x00254000, "tailres", sectors=4)
        prog[200 * SECTOR_BYTES : 204 * SECTOR_BYTES] = tail_hdr

        doc = audit_program_bin_directory(
            bytes(krnl),
            bytes(prog),
            release_id="synthetic-test",
            krnl_iso_path="0KRNL.BIN",
            program_iso_path="PROGRAM.BIN",
        )
        verify_kernel_directory_receipt(doc)
        self.assertEqual(doc["kernel_directory"]["entry_count"], 32)
        self.assertTrue(doc["kernel_directory"]["all_entries_fit_workram_l"])
        self.assertEqual(doc["program_bin_accounting"]["unreferenced_headers_count"], 1)
        self.assertEqual(doc["program_bin_accounting"]["trailing_subsector_bytes"], 128)


class CliAndSafetyUnitTests(unittest.TestCase):
    def test_public_safe_path_leak_guard(self) -> None:
        assert_public_safe_text('{"iso_path": "BOMSS/PROGRAM.BIN"}')
        for bad in ('{"p": "/home/dev/secret"}', '{"p": "/tmp/x"}', '{"p": "/var/lib/gate"}'):
            with self.assertRaises(ArchiveError):
                assert_public_safe_text(bad)

    def test_cli_help_and_verify_subcommand(self) -> None:
        cli_path = Path(__file__).resolve().parent / "cli.py"
        for subcmd in ([], ["audit-directory"], ["decode-bank"], ["compare-resident"], ["verify"]):
            proc = subprocess.run(
                [sys.executable, str(cli_path), *subcmd, "--help"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)

        bank_bytes, _ = _build_synthetic_bank(0x00254000, "synbank", sectors=4)
        decoded = parse_and_decode_bank(bank_bytes, bank_id=0, expected_load_base=0x00254000, source_sector_offset=0)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bank.json"
            # Note: tmp is under /tmp, write manually to avoid /tmp path inside payload (payload itself is clean)
            p.write_text(json.dumps(decoded, indent=2) + "\n", encoding="utf-8")
            ok_proc = subprocess.run(
                [sys.executable, str(cli_path), "verify", "--bank", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ok_proc.returncode, 0, msg=ok_proc.stderr)

            # Tamper schema -> verify must fail
            bad = dict(decoded, schema="wrong")
            p.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            bad_proc = subprocess.run(
                [sys.executable, str(cli_path), "verify", "--bank", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(bad_proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
