#!/usr/bin/env python3
"""Export the real Godot client and fail on import/compiler errors."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def source_revision(root=ROOT):
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Export requires a full source commit')
    tracked = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=root, text=True)
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=root, text=True).split('\0')
    # Godot generates import/UID sidecars on first use. Other untracked inputs
    # could change the pack without belonging to the advertised source commit.
    unknown = [name for name in untracked if name and not name.endswith(('.gd.uid', '.import'))]
    dirty = bool(tracked or unknown)
    if dirty:
        raise ValueError('Commit all source inputs before exporting an identified release')
    return revision


def metadata(revision):
    return {'schema': 'neptune.release/1', 'revision': revision,
            'configuration': 'casual-development-demo',
            'defaults': {'battle_seconds': 180, 'countdown_seconds': 3,
                         'results_seconds': 5, 'participants': 4, 'bot_profile': 'BALANCED'},
            'images': {kind: f'ghcr.io/elgansayer/neptune-bomberman-{kind}:sha-{revision}'
                       for kind in ('web', 'server')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', required=True)
    args = parser.parse_args()
    revision = source_revision()
    output = ROOT / 'build/web'
    server = ROOT / 'build/server'
    # Old exported packs must never leak into a new export or Docker context.
    for directory in (output, server):
        if directory.exists():
            shutil.rmtree(directory)
    output.mkdir(parents=True, exist_ok=True)
    server.mkdir(parents=True, exist_ok=True)
    stamp = ROOT / 'shared/build_revision.gd'
    original = stamp.read_bytes()
    stem = 'game-' + revision
    try:
        stamp.write_text('extends RefCounted\nconst REVISION := ' + json.dumps(revision) + '\n')
        for command in [
            [args.godot, '--headless', '--path', str(ROOT), '--editor', '--import'],
            [args.godot, '--headless', '--path', str(ROOT), '--export-release', 'Web', str(output / (stem + '.html'))],
            [args.godot, '--headless', '--path', str(ROOT), '--export-release', 'Linux Server', str(server / 'neptune.x86_64')],
        ]:
            result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=420)
            print(result.stdout, flush=True)
            if result.returncode or re.search(r'ERROR:|Parse Error:|Failed to load script', result.stdout):
                raise SystemExit('Godot import/export failed; refusing to publish')
    finally:
        stamp.write_bytes(original)
    (output / (stem + '.html')).replace(output / 'index.html')
    for name in ['index.html', stem + '.js', stem + '.wasm', stem + '.pck']:
        if not (output / name).is_file() or (output / name).stat().st_size == 0:
            raise SystemExit('Missing web export: ' + name)
    for directory in (output, server):
        (directory / 'release.json').write_text(json.dumps(metadata(revision), indent=2) + '\n')
    print('EXPORTED_RELEASE=' + revision, flush=True)


if __name__ == '__main__':
    main()
