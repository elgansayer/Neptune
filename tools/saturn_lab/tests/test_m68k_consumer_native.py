"""Owned profile/ABI/source checks, no third-party CPU or original execution."""
import ctypes
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import m68k_consumer_native as long
import m68k_probe as short


class ConsumerNativeTests(unittest.TestCase):
    def test_generated_adapter_changes_only_two_caps_and_abi_tag(self):
        original=short.BACKEND.read_bytes()
        changed=long.generated_source()
        restored=changed.replace(b'#define MAX_STEPS 2048',b'#define MAX_STEPS 256').replace(
            b'#define MAX_EVENTS 1024',b'#define MAX_EVENTS 128').replace(
            b'uint32_t neptune_m68k_abi(void) { return 2; }',b'uint32_t neptune_m68k_abi(void) { return 1; }')
        self.assertEqual(restored,original)
        self.assertEqual(short.BACKEND.read_bytes(),original)
        self.assertNotEqual(short.pinned.digest(changed),long.BASE_SHA256)

    def test_layouts_and_identities_are_explicitly_distinct(self):
        self.assertGreater(ctypes.sizeof(long.Result),ctypes.sizeof(short.Result))
        self.assertEqual(long.identity()['abi'],2)
        self.assertEqual(long.identity()['max_steps'],2048)
        self.assertEqual(long.identity()['max_events'],1024)
        self.assertEqual(short.MAX_STEPS,256)
        self.assertEqual(short.MAX_EVENTS,128)

    def test_changed_base_is_rejected_instead_of_silently_rebased(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'changed.c';path.write_text('changed')
            with patch.object(short,'BACKEND',path),self.assertRaises(ValueError):long.generated_source()

    def test_wrong_prepared_identity_cannot_load_native_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'receipt.json').write_text(json.dumps({'status':'ready','identity':short.identity()}))
            with patch.object(long.c,'CDLL') as load,self.assertRaises(ValueError):long.Library(root)
            load.assert_not_called()


if __name__=='__main__':unittest.main()
