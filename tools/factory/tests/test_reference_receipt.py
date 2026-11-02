"""Real Ed25519 operations with synthetic payloads; not original-game execution."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest

import reference_receipt as receipt


class ReferenceReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.authority = self.root / "authority"
        self.key_id = receipt.keygen(self.authority)["public_key_sha256"]
        self.output = self.root / "artifacts"
        self.output.mkdir()
        (self.output / "capture.json").write_text('{"scope":"synthetic crypto fixture"}\n')
        self.binding = {"head": "a" * 40, "base": "b" * 40, "revision": "c" * 64, "issue": 579}
        self.policy = "d" * 64
        run = {"exit": 0, "frames": 2, "identity": {"fixture": "synthetic"}, "canonical_digest": "f" * 64}
        comparison = {"command": "compare", "matched_frames": 2, "canonical_digest": "f" * 64}
        self.payload = {"schema": receipt.SCHEMA, "scope": receipt.SCOPE,
                        "task_binding": self.binding, "policy_sha256": self.policy,
                        "owner": "synthetic test", "scenario": "synthetic/receipt",
                        "identity": run["identity"],
                        "isolation": {"source_read_only": True, "authority_hidden": True, "broker_hidden": True},
                        "runs": [copy.deepcopy(run) for _ in range(3)],
                        "comparisons": [copy.deepcopy(comparison) for _ in range(2)],
                        "files": receipt.inventory(self.output), "crypto": {"scope": "synthetic test"},
                        "recorded_at": time.time()}
        self.certificate = self.output / "reference-certificate.json"

    def sign(self, payload=None):
        return receipt.seal(self.payload if payload is None else payload, self.authority / "private.pem",
                            self.authority / "public.der", self.certificate)

    def verify(self, **kwargs):
        return receipt.verify(self.certificate, kwargs.pop("public", self.authority / "public.der"),
                              kwargs.pop("key_id", self.key_id), kwargs.pop("binding", self.binding),
                              kwargs.pop("policy", self.policy), kwargs.pop("artifacts", self.output), **kwargs)

    def test_real_signature_and_public_only_verification(self):
        self.sign()
        (self.authority / "private.pem").unlink()
        result = self.verify()
        self.assertIs(result["authenticated"], True)
        self.assertEqual(result["public_key_sha256"], self.key_id)
        self.assertIn("no Godot", result["scope"])

    def test_existing_authority_and_certificate_are_preserved(self):
        old = (self.authority / "private.pem").read_bytes()
        with self.assertRaises(ValueError):
            receipt.keygen(self.authority)
        self.assertEqual((self.authority / "private.pem").read_bytes(), old)
        self.sign()
        old = self.certificate.read_bytes()
        with self.assertRaises(FileExistsError):
            self.sign()
        self.assertEqual(self.certificate.read_bytes(), old)

    def test_wrong_key_and_substituted_key_identity_are_rejected(self):
        self.sign()
        other = self.root / "other-authority"
        other_id = receipt.keygen(other)["public_key_sha256"]
        with self.assertRaises(ValueError):
            self.verify(public=other / "public.der")
        with self.assertRaises(ValueError):
            self.verify(public=other / "public.der", key_id=other_id)

    def test_forged_payload_and_signature_are_rejected(self):
        envelope = self.sign()
        original = copy.deepcopy(envelope)
        for name in ("payload", "signature"):
            envelope = copy.deepcopy(original)
            if name == "payload":
                envelope["payload"]["scenario"] = "forged"
            else:
                envelope["signature"] = "A" * 88
            self.certificate.write_text(json.dumps(envelope))
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify()

    def test_stale_head_base_revision_task_and_policy_are_rejected(self):
        self.sign()
        for name in ("head", "base", "revision", "issue"):
            binding = dict(self.binding, **{name: 580 if name == "issue" else "0" * len(self.binding[name])})
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify(binding=binding)
        with self.assertRaises(ValueError):
            self.verify(policy="0" * 64)

    def test_missing_truncated_replaced_and_additional_artifacts_are_rejected(self):
        self.sign()
        capture = self.output / "capture.json"
        original = capture.read_bytes()
        for name, content in (("truncated", b"{"), ("replaced", b"forged summary")):
            capture.write_bytes(content)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify()
        capture.unlink()
        with self.assertRaises(ValueError):
            self.verify()
        capture.write_bytes(original)
        nested = self.output / "nested"
        nested.mkdir()
        (nested / "reference-certificate.json").write_text("must not be excluded")
        with self.assertRaises(ValueError):
            self.verify()

    def test_symlinked_public_keys_and_artifacts_are_rejected(self):
        self.sign()
        alias = self.root / "key-alias"
        alias.symlink_to(self.authority / "public.der")
        with self.assertRaises(ValueError):
            self.verify(public=alias)
        (self.output / "other").symlink_to(self.authority / "public.der")
        with self.assertRaises(ValueError):
            self.verify()

    def test_world_readable_private_key_or_directory_is_refused(self):
        key = self.authority / "private.pem"
        key.chmod(0o644)
        with self.assertRaises(ValueError):
            self.sign()
        key.chmod(0o600)
        self.authority.chmod(0o755)
        with self.assertRaises(ValueError):
            self.sign()

    def test_failed_skipped_empty_and_boolean_runs_cannot_be_trusted_even_when_signed(self):
        for name in ("failed", "skipped", "empty", "boolean", "divergent", "comparison"):
            payload = copy.deepcopy(self.payload)
            if name == "failed":
                payload["runs"][0]["exit"] = 1
            elif name == "skipped":
                payload["runs"] = []
            elif name == "empty":
                payload["runs"][0]["frames"] = 0
            elif name == "boolean":
                payload["runs"][0]["exit"] = False
            elif name == "divergent":
                payload["runs"][0]["canonical_digest"] = "0" * 64
            else:
                payload["comparisons"][0]["matched_frames"] = True
            self.sign(payload)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify()
            self.certificate.unlink()

    def test_private_key_never_appears_in_receipt(self):
        key = (self.authority / "private.pem").read_text()
        self.sign()
        self.assertNotIn(key, self.certificate.read_text())
        self.assertNotIn("BEGIN PRIVATE KEY", self.certificate.read_text())

    def test_duplicate_json_and_oversized_or_truncated_certificates_fail(self):
        self.sign()
        for value in ('{"payload":{},"payload":{}}', '{"payload":', ''):
            self.certificate.write_text(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.verify()
        with self.certificate.open("wb") as stream:
            stream.truncate(receipt.MAX_JSON + 1)
        with self.assertRaises(ValueError):
            self.verify()


if __name__ == "__main__":
    unittest.main()
