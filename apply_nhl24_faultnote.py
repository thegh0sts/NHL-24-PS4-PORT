#!/usr/bin/env python3
r"""NHL 24 diagnostic: a guest crash report also names the last memory-tracking fault the same thread
took (Windows). Run once from the repo root, then rebuild:

    python3 apply_nhl24_faultnote.py
    bash scripts/build-msys2.sh && BB_SKIP_PREPARE=1 bash scripts/run-msys2.sh nhl24

Why: the crash at guest offset 0x666096a (Ghidra 0x766096a, FUN_07660830, the renderer's draw-list
sort) read a value the function itself had saved 0x28 bytes below the stack pointer (the SysV
"red zone"), with no call in between, and found 0. Windows writes its exception information
right below the stack pointer whenever an instruction faults, and the GPU memory tracking makes
guest stores to watched pages fault (handled, then the game continues). If such a fault hit this
loop, it wiped the saved value. This patch shows whether that happened.

src/platform/platform_win.c
    - every access fault the GPU tracking handles on a thread is counted, with the last one's
      instruction and stack pointer kept per thread;
    - a crash report adds: "last handled tracking fault on this thread: <where>, rsp=..., N in
      total". If <where> is in the crashing function and rsp matches, the red zone was overwritten.
"""
import sys
from pathlib import Path

p = Path('src/platform/platform_win.c')
if not p.exists():
    sys.exit(f'run this from the repo root ({p} not found)')
s = p.read_text(encoding='utf-8')
if 'last handled tracking fault' in s:
    sys.exit('already applied')

subs = [
    ('static LONG fatal_exception(EXCEPTION_POINTERS *info) {\n',
     '/* NHL 24 diagnostic: the last access fault the GPU tracking handled on this thread. */\n'
     'static __thread uintptr_t tracked_fault_rip, tracked_fault_rsp;\n'
     'static __thread unsigned long long tracked_faults;\n'
     'static LONG fatal_exception(EXCEPTION_POINTERS *info) {\n'),
    ('    report_appearance_pool(c);\n',
     '    if (tracked_faults) {\n'
     '        char last[MAX_PATH + 64];\n'
     '        describe_rip(last, sizeof(last), tracked_fault_rip);\n'
     '        fprintf(stderr, "  last handled tracking fault on this thread: %s, rsp=%016llx, %llu in total\\n",\n'
     '                last, (unsigned long long)tracked_fault_rsp, tracked_faults);\n'
     '    } else fprintf(stderr, "  no tracking fault was handled on this thread\\n");\n'
     '    report_appearance_pool(c);\n'),
    ('        if (gpu_fault && gpu_fault(info, (void *)record->ExceptionInformation[1])) return EXCEPTION_CONTINUE_EXECUTION;\n',
     '        if (gpu_fault && gpu_fault(info, (void *)record->ExceptionInformation[1])) {\n'
     '            tracked_fault_rip = (uintptr_t)info->ContextRecord->Rip;\n'
     '            tracked_fault_rsp = (uintptr_t)info->ContextRecord->Rsp;\n'
     '            ++tracked_faults;\n'
     '            return EXCEPTION_CONTINUE_EXECUTION;\n'
     '        }\n'),
]
missing = [old[:70] for old, _ in subs if s.count(old) != 1]
if missing:
    sys.exit(f'{p} was not as expected (nothing changed); not found:\n  ' + '\n  '.join(missing))
for old, new in subs:
    s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8', newline='\n')
print(f'changed: {p} (crash reports name the last handled tracking fault)')
