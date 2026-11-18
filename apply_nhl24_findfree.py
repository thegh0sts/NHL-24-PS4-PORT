#!/usr/bin/env python3
r"""NHL 24: a mapping whose address hint has no room above it now looks again from the bottom of
the user range, as the PS4 kernel does. Run once from the repo root, then rebuild:

    python3 apply_nhl24_findfree.py
    bash scripts/build-msys2.sh && BB_SKIP_PREPARE=1 bash scripts/run-msys2.sh nhl24

The game maps small (16 KiB) blocks of direct memory with an address hint at the very top of the
user range (one landed at 0xFBFFFFC000). The next one asked for the same spot; the runtime only
looked upward from the hint, found no room below 0xFC00000000 and failed with "out of memory"
("mapping direct memory 0x1fc000, size=16384 failed (error 0x8002000c)") while the renderer module
was starting.

src/runtime_memory.c
    find_free(): when nothing fits at or above the hint, search again from the start of the user
    range.
    sceKernelMapDirectMemory / MapDirectMemory2 failures also print the requested address, flags
    and the game's call sites (needs apply_nhl24_memlog.py, already applied).
"""
import sys
from pathlib import Path

p = Path('src/runtime_memory.c')
if not p.exists():
    sys.exit('run this from the repo root (src/runtime_memory.c not found)')
s = p.read_text(encoding='utf-8')
if 'NHL 24: no room above the hint' in s:
    sys.exit('already applied')
if 'memory_failure' not in s:
    sys.exit('apply apply_nhl24_memlog.py first (nothing changed)')

subs = [
    ('static uintptr_t find_free(uintptr_t hint, uint64_t size, uint64_t alignment) {\n'
     '    uintptr_t at=align_up(hint<USER_MIN ? USER_MIN : hint, alignment);\n'
     '    for (size_t i=vma_index(at); at+size<=USER_MAX; ++i) {\n'
     '        if (i==vma_count || vmas[i].start>=at+size) return at;\n'
     '        at=align_up(vmas[i].end,alignment);\n'
     '    }\n'
     '    return 0;\n'
     '}',
     'static uintptr_t find_free(uintptr_t hint, uint64_t size, uint64_t alignment) {\n'
     '    uintptr_t at=align_up(hint<USER_MIN ? USER_MIN : hint, alignment);\n'
     '    for (size_t i=vma_index(at); at+size<=USER_MAX; ++i) {\n'
     '        if (i==vma_count || vmas[i].start>=at+size) return at;\n'
     '        at=align_up(vmas[i].end,alignment);\n'
     '    }\n'
     '    /* NHL 24: no room above the hint; the PS4 then searches from the bottom of the range. */\n'
     '    if (hint>USER_MIN) return find_free(USER_MIN,size,alignment);\n'
     '    return 0;\n'
     '}'),
    # sceKernelMapDirectMemory
    ('static ABI int32_t direct_map(void **out, uint64_t size, int prot, int flags, int64_t physical, uint64_t alignment) {\n'
     '    write_lock();\n',
     'static ABI int32_t direct_map(void **out, uint64_t size, int prot, int flags, int64_t physical, uint64_t alignment) {\n'
     '    const uint64_t wanted=out ? (uint64_t)(uintptr_t)*out : 0;\n'
     '    write_lock();\n'),
    ('    else printf("Runtime: mapping direct memory %#" PRIx64 ", size=%" PRIu64 " failed (error %#x)\\n", (uint64_t)physical, size, (unsigned)result);\n',
     '    else {\n'
     '        printf("Runtime: mapping direct memory %#" PRIx64 ", size=%" PRIu64 " failed (error %#x)\\n", (uint64_t)physical, size, (unsigned)result);\n'
     '        memory_failure("map direct memory at",wanted,size,flags,result);\n'
     '    }\n'),
    # sceKernelMapDirectMemory2
    ('                               uint64_t alignment) {\n'
     '    write_lock();\n',
     '                               uint64_t alignment) {\n'
     '    const uint64_t wanted=out ? (uint64_t)(uintptr_t)*out : 0;\n'
     '    write_lock();\n'),
    ('    else printf("Runtime: mapping direct memory %#" PRIx64 ", size=%" PRIu64 " failed (error %#x, MapDirectMemory2)\\n", (uint64_t)physical, size, (unsigned)result);\n',
     '    else {\n'
     '        printf("Runtime: mapping direct memory %#" PRIx64 ", size=%" PRIu64 " failed (error %#x, MapDirectMemory2)\\n", (uint64_t)physical, size, (unsigned)result);\n'
     '        memory_failure("map direct memory (2) at",wanted,size,flags,result);\n'
     '    }\n'),
]
missing = [old[:80] for old, _ in subs if s.count(old) != 1]
if missing:
    sys.exit('src/runtime_memory.c was not as expected (nothing changed); not found:\n  ' + '\n  '.join(missing))
for old, new in subs:
    s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8', newline='\n')
print('changed: src/runtime_memory.c (address search falls back to the bottom of the range; failed direct maps logged)')
