#!/usr/bin/env python3
"""Provenance and immutable-pair rejection checks; these do not certify gameplay."""
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import unittest

HERE = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


export = module('export')
wait_release = module('wait_release')


class ReleaseContracts(unittest.TestCase):
    def test_public_readiness_identifies_its_http_client(self):
        revision = 'a' * 40
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(dict(self.headers))
                if self.headers.get('User-Agent') != 'NeptuneRelease/1.0':
                    self.send_error(403)
                    return
                body = json.dumps(export.metadata(revision)).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run([sys.executable, str(HERE / 'wait_release.py'),
                                     '--revision', revision, '--timeout', '1',
                                     '--origin', f'http://127.0.0.1:{server.server_port}'],
                                    text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(received[0]['Cache-Control'], 'no-cache')
            self.assertEqual(received[0]['Accept'], 'application/json')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_source_must_be_committed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
            git('init')
            (root / 'game.gd').write_text('original')
            git('add', 'game.gd')
            git('-c', 'user.name=Release Test', '-c', 'user.email=release-test@example.invalid', 'commit', '-m', 'fixture')
            revision = git('rev-parse', 'HEAD')
            self.assertEqual(export.source_revision(root), revision)
            (root / 'game.gd').write_text('changed')
            with self.assertRaises(ValueError):
                export.source_revision(root)
            git('checkout', '--', 'game.gd')
            (root / 'uncommitted-map.json').write_text('{}')
            with self.assertRaises(ValueError):
                export.source_revision(root)

    def test_only_expected_generated_sidecars_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init'], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(['git', '-c', 'user.name=Release Test', '-c', 'user.email=release-test@example.invalid', 'commit', '--allow-empty', '-m', 'fixture'], cwd=root, stdout=subprocess.DEVNULL, check=True)
            (root / 'game.gd.uid').write_text('uid://fixture')
            (root / 'texture.png.import').write_text('generated fixture')
            self.assertEqual(len(export.source_revision(root)), 40)

    def test_public_metadata_rejects_missing_stale_and_unmatched_pair(self):
        revision = 'a' * 40
        valid = export.metadata(revision)
        self.assertEqual(wait_release.validate_release(valid, revision), valid)
        for invalid in [None, {}, export.metadata('b' * 40), {**valid, 'images': {}}, {**valid, 'images': {'web': valid['images']['web'], 'server': 'latest'}}]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                wait_release.validate_release(invalid, revision)

    def test_initial_transition_preserves_known_accepted_immutable_pair(self):
        previous = json.loads((HERE / 'initial-rollback.json').read_text())
        self.assertEqual(previous['revision'], 'e6bc43980e197e1b14db6be3ff12b29c1b9a4438')
        wait_release.validate_release(previous, previous['revision'])
        self.assertIn('/actions/runs/41605380884', previous['publication_run'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
