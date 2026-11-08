#!/usr/bin/env python3
"""Which of the game's system imports the port probably lacks: all of them at once, instead of one
STOP per run. Run from the repo root after a prepare (reads out/import_names.txt; writes
out/missing_imports.txt):

    python3 tools/missing_imports.py

An import counts as provided when its name is in a runtime table (src/*.c: {"name",fn}), its NID
is named in the runtime sources ("NID" or "NID#library"), shadPS4's HLE registers its NID, or the GPU shim
names it (gpu/shim). libc / libSceLibcInternal imports come from the linked libc.prx. This is an
estimate from the sources, not the loader's own answer: a name the runtime builds at run time is
not seen, and a provided function can still be incomplete. The STOP line remains the authority.
"""
import collections
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
names_file = root / 'out' / 'import_names.txt'
if not names_file.exists():
    sys.exit('missing_imports: out/import_names.txt not found: prepare the game first (run-msys2.sh without BB_SKIP_PREPARE)')

names, nids = set(), set()
for f in (root / 'src').glob('*.c'):
    text = f.read_text(errors='replace')
    names.update(re.findall(r'\{\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*,', text))
    nids.update(re.findall(r'"([A-Za-z0-9+\-]{11})(?:#[A-Za-z0-9_]+)?"', text))  # "NID" or "NID#library"
for f in (root / 'gpu' / 'shadps4' / 'core' / 'libraries').rglob('*.cpp'):
    nids.update(re.findall(r'LIB_FUNCTION\(\s*"([A-Za-z0-9+\-]{11})"', f.read_text(errors='replace')))
for f in (root / 'gpu' / 'shim').rglob('*.cpp'):
    names.update(re.findall(r'"(sce[A-Za-z0-9_]+)"', f.read_text(errors='replace')))
NATIVE = {'libc', 'libSceLibcInternal'}

missing = collections.defaultdict(list)
total = provided = native = 0
for line in names_file.read_text(errors='replace').splitlines():
    if not line.strip() or line.startswith('#'):
        continue
    parts = line.split()
    nid, lib, symbol = parts[0], parts[1] if len(parts) > 1 else '?', parts[2] if len(parts) > 2 else '?'
    total += 1
    if lib in NATIVE:
        native += 1
    elif symbol in names or nid in nids:
        provided += 1
    else:
        missing[lib].append((symbol, nid))

count = sum(len(v) for v in missing.values())
print(f'{total} imports: {native} from the linked libc, {provided} provided, {count} probably missing')
out = []
for lib in sorted(missing, key=lambda k: -len(missing[k])):
    print(f'  {lib:34} {len(missing[lib]):4}')
    out.append(f'[{lib}] {len(missing[lib])}')
    out += [f'  {symbol}  {nid}' for symbol, nid in sorted(missing[lib])]
target = root / 'out' / 'missing_imports.txt'
target.write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'list: {target}')
