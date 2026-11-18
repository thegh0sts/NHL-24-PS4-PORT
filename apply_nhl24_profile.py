#!/usr/bin/env python3
r"""NHL 24 port: teach scripts/game_check.py the NHL 24 executable and make it run-msys2.sh's default
game. Run once from the repo root (the NHL 24 repo, started from the NHL 19 one):

    python3 apply_nhl24_profile.py

  * SUPPORTED gains NHL 24 CUSA37933 1.60 (US, UP0006, SDK 10.50), keyed on its loaded image's
    sha256, profile name "nhl24" (BB_GAME_PROFILE). Modules linked: libc.prx, libSceFios2.prx and
    libSceNpToolkit2.prx (Sony's PSN helper library, which the game calls into directly). The
    camera (libSceFace, libSceHand) and stereo-3D (libSceS3DConversion) modules are left out
    until the game shows it needs them.
  * scripts/run-msys2.sh: the default game folder is nhl24 (was nhl19). NHL 19's settings stay
    keyed on the nhl19 profile, so NHL 24 starts with the runtime's own defaults.
"""
import sys
from pathlib import Path

gc = Path('scripts/game_check.py')
run = Path('scripts/run-msys2.sh')
if not gc.exists() or not run.exists():
    sys.exit('run this from the repo root (scripts/game_check.py and scripts/run-msys2.sh are needed)')
s = gc.read_text(encoding='utf-8')
if "name='nhl24'" in s:
    sys.exit('already applied')

old = """        modules=('libc.prx', 'libSceFios2.prx'), patches=False),
}
BY_TITLE"""
new = """        modules=('libc.prx', 'libSceFios2.prx'), patches=False),
    # NHL 24 CUSA37933 (US, UP0006) 1.60, SDK 10.50: Frostbite engine.
    '2826e477972fa61d626cc02fde81e4c84a79c8d1cb5711a959563fb86920fc67': dict(
        name='nhl24', title='CUSA37933', version='01.60', game='NHL 24', update='CUSA37933-patch',
        modules=('libc.prx', 'libSceFios2.prx', 'libSceNpToolkit2.prx'), patches=False),
}
BY_TITLE"""
if s.count(old) != 1:
    sys.exit('scripts/game_check.py: the end of SUPPORTED was not found as expected (nothing changed)')
s = s.replace(old, new, 1)

r = run.read_text(encoding='utf-8')
fixes = [('game=${BB_GAME_DIR:-nhl19}', 'game=${BB_GAME_DIR:-nhl24}'),
         ('(default: $BB_GAME_DIR, else ./nhl19)', '(default: $BB_GAME_DIR, else ./nhl24)')]
for a, b in fixes:
    if r.count(a) != 1:
        sys.exit(f'scripts/run-msys2.sh: {a!r} was not found as expected (nothing changed)')
    r = r.replace(a, b, 1)

gc.write_text(s, encoding='utf-8', newline='\n')
run.write_text(r, encoding='utf-8', newline='\n')
print('changed: scripts/game_check.py (NHL 24 CUSA37933 1.60 profile), scripts/run-msys2.sh (default game folder nhl24)')
