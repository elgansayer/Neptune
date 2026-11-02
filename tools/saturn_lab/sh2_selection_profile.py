"""Separate1024-instruction selection profile derived from the accepted guard.

The accepted128-instruction module and every permission/CPU guard stay unchanged.
Only the bound is changed in a fresh private namespace; no vendor code is edited.
"""
from pathlib import Path

import probe_kernel as pinned

GUARD_SHA256='9d73ab349e27bc476700e111cf454f70b3ee2305ff354c82040ff0d39c5f4169'
MAX_STEPS=1024
source=Path(__file__).with_name('sh2_handoff_profile.py').read_bytes()
if pinned.digest(source)!=GUARD_SHA256 or source.count(b'MAX_STEPS=128\n')!=1:
    raise ValueError('Accepted handoff guard source changed')
derived=source.replace(b'MAX_STEPS=128\n',b'MAX_STEPS=1024\n')
DERIVED_SHA256=pinned.digest(derived)
namespace={'__name__':'_neptune_selection_guard'}
exec(compile(derived,'owned-selection-guard.py','exec'),namespace)
observe=namespace['observe']
