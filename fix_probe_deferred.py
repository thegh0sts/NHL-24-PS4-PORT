#!/usr/bin/env python3
r"""Fix for apply_nhl24_dynmodules.py: the probe's module check ("invalid linked module metadata")
compared the start address with its "deferred" mark still set. Run once from the repo root:

    python3 fix_probe_deferred.py
    bash scripts/build-msys2.sh && BB_SKIP_PREPARE=1 bash scripts/run-msys2.sh nhl24
"""
import sys
from pathlib import Path

p = Path('src/probe.c')
if not p.exists():
    sys.exit('run this from the repo root (src/probe.c not found)')
s = p.read_text(encoding='utf-8')
old = 'x->init<x->base || x->init-x->base>=x->size ||'
new = '(x->init&~DEFERRED_INIT)<x->base || (x->init&~DEFERRED_INIT)-x->base>=x->size ||'
if new in s:
    sys.exit('already applied')
if s.count(old) != 1 or 'DEFERRED_INIT' not in s:
    sys.exit('src/probe.c was not as expected (apply apply_nhl24_dynmodules.py first; nothing changed)')
p.write_text(s.replace(old, new, 1), encoding='utf-8', newline='\n')
print('changed: src/probe.c (module check ignores the deferred mark)')
