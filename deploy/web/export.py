#!/usr/bin/env python3
"""Export the real Godot client and fail on import/compiler errors."""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', required=True)
    args = parser.parse_args()
    output = ROOT / 'build/web'
    output.mkdir(parents=True, exist_ok=True)
    for command in [
        [args.godot, '--headless', '--path', str(ROOT), '--editor', '--import'],
        [args.godot, '--headless', '--path', str(ROOT), '--export-release', 'Web', str(output / 'index.html')],
    ]:
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=420)
        print(result.stdout, flush=True)
        if result.returncode or re.search(r'SCRIPT ERROR:|Parse Error:|Failed to load script', result.stdout):
            raise SystemExit('Godot import/export failed; refusing to publish')
    for name in ['index.html', 'index.js', 'index.wasm', 'index.pck']:
        if not (output / name).is_file() or (output / name).stat().st_size == 0:
            raise SystemExit('Missing web export: ' + name)


if __name__ == '__main__':
    main()
