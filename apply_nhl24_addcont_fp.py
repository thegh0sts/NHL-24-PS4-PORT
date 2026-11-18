#!/usr/bin/env python3
r"""NHL 24: add-on lists for any service label, and the PS4 floating-point mode by default.
Run once from the repo root, then rebuild:

    python3 apply_nhl24_addcont_fp.py
    bash scripts/build-msys2.sh && BB_SKIP_PREPARE=1 bash scripts/run-msys2.sh nhl24

src/runtime_content.c
    sceAppContentGetAddcontInfoList with a nonzero service label stopped the runtime ("STOP:
    nonzero AppContent service label unsupported"). NHL 24 asks with its own label; the answer
    is the same as for label 0: no add-ons installed.
scripts/run-msys2.sh
    nhl24: BB_DETERMINISTIC_FP=1 by default. Without it the game's threads keep the PC's
    floating-point mode instead of the PS4's (denormals flushed to zero) and the GPU was lost
    (device lost) at the first screens; NHL 19 always runs with it on. BB_DETERMINISTIC_FP=0
    still turns it off.
"""
import sys
from pathlib import Path

c = Path('src/runtime_content.c')
r = Path('scripts/run-msys2.sh')
for p in (c, r):
    if not p.exists():
        sys.exit(f'run this from the repo root ({p} not found)')
cs, rs = c.read_text(encoding='utf-8'), r.read_text(encoding='utf-8')
if 'NHL 24 asks with its own service label' in cs:
    sys.exit('already applied')

c_old = '    if (service) { fputs("STOP: nonzero AppContent service label unsupported\\n",stderr); exit(21); }\n'
c_new = ('    /* NHL 24 asks with its own service label; no add-ons are installed under any label. */\n'
         '    if (service) { static int shown; if (!shown++) printf("Runtime: AppContent add-on list for service label %u: none\\n",service); }\n')
r_old = '# Ignite games (UFC 3, NHL 19): the 3D scene'
r_new = ('# NHL 24: the PS4\'s floating-point mode in the game\'s threads (BB_DETERMINISTIC_FP, as NHL 19 has\n'
         '# through its network mode). Without it the GPU is lost (device lost) at the first screens.\n'
         'if [[ $profile == nhl24 ]]; then\n'
         '    export BB_DETERMINISTIC_FP=${BB_DETERMINISTIC_FP:-1}\n'
         '    echo "run-msys2: NHL 24: PS4 floating-point mode (BB_DETERMINISTIC_FP=$BB_DETERMINISTIC_FP)"\n'
         'fi\n' + r_old)
bad = [n for t, o, n in ((cs, c_old, 'runtime_content.c addon_list'), (rs, r_old, 'run-msys2.sh Ignite block')) if t.count(o) != 1]
if bad:
    sys.exit('not as expected (nothing changed): ' + ', '.join(bad))
c.write_text(cs.replace(c_old, c_new, 1), encoding='utf-8', newline='\n')
r.write_text(rs.replace(r_old, r_new, 1), encoding='utf-8', newline='\n')
print('changed: src/runtime_content.c (add-on lists for any service label), scripts/run-msys2.sh (nhl24: BB_DETERMINISTIC_FP=1)')
