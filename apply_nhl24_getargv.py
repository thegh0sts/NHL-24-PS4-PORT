#!/usr/bin/env python3
r"""NHL 24: getargc / getargv (libkernel). Run once from the repo root:

    python3 apply_nhl24_getargv.py

NHL 24 reads its command line at start-up (after looking for /app0/commandline.txt) through
libkernel's getargv ("STOP: first unsupported PS4 import: FJmglmTMdr4#libkernel ... getargv").
On a PS4 these return the process arguments: one, the executable. This answers the same
(argc 1, argv {"eboot.bin", NULL}). Then rebuild: bash scripts/build-msys2.sh
"""
import sys
from pathlib import Path

p = Path('src/runtime_kernel.c')
if not p.exists():
    sys.exit('run this from the repo root (src/runtime_kernel.c not found)')
s = p.read_text(encoding='utf-8')
if 'kernel_getargv' in s:
    sys.exit('already applied')
anchor = 'static const RuntimeExport exports[]={'
if s.count(anchor) != 1:
    sys.exit('src/runtime_kernel.c: the exports table was not found as expected (nothing changed)')
fn = ('/* getargc / getargv (libkernel): the process arguments, as a PS4 starts a game: the executable alone. */\n'
      'static char kernel_arg0[]="eboot.bin";\n'
      'static char *kernel_argv[]={kernel_arg0,NULL};\n'
      'static ABI int32_t kernel_getargc(void) { return 1; }\n'
      'static ABI char **kernel_getargv(void) { return kernel_argv; }\n\n')
s = s.replace(anchor, fn + anchor + '\n    {"getargc",kernel_getargc}, {"getargv",kernel_getargv},', 1)
p.write_text(s, encoding='utf-8', newline='\n')
print('changed: src/runtime_kernel.c (getargc, getargv)')
