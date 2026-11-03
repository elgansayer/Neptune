#!/usr/bin/env python3
"""Wait for public release metadata; gameplay still requires the browser gate."""
import argparse
import json
import re
import time
import urllib.error
import urllib.request


def validate_release(value, expected):
    if not isinstance(value, dict) or value.get('schema') != 'neptune.release/1':
        raise ValueError('Missing or unsupported release metadata')
    if value.get('revision') != expected:
        raise ValueError('Public client revision has not reached the intended release')
    images = value.get('images')
    if not isinstance(images, dict) or any(images.get(kind) != f'ghcr.io/elgansayer/neptune-bomberman-{kind}:sha-{expected}' for kind in ('web', 'server')):
        raise ValueError('Release does not describe a matching immutable image pair')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--origin', default='https://bomberman.elgansayer.com')
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.revision) or not 1 <= args.timeout <= 300:
        parser.error('Use a full release commit and a timeout of 1..300 seconds')
    deadline = time.monotonic() + args.timeout
    last_error = 'No response'
    while time.monotonic() < deadline:
        request = urllib.request.Request(args.origin.rstrip('/') + '/release.json?revision=' + args.revision,
                                         headers={'Cache-Control': 'no-cache', 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=min(10, max(0.1, deadline - time.monotonic()))) as response:
                if response.headers.get_content_type() != 'application/json':
                    raise ValueError('Release metadata has the wrong MIME type')
                value = json.loads(response.read(16385))
            validate_release(value, args.revision)
            print(json.dumps({'schema': 'neptune.public-client-observed/1', 'revision': args.revision,
                              'coverage': 'metadata-only; authoritative browser verification follows'}), flush=True)
            return
        except (urllib.error.URLError, ValueError, OSError) as error:
            last_error = str(error)
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    raise SystemExit('Public release did not become ready: ' + last_error)


if __name__ == '__main__':
    main()
