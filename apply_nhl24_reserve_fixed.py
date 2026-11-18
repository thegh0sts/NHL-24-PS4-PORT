#!/usr/bin/env python3
r"""NHL 24: sceKernelReserveVirtualRange with MAP_FIXED over memory that is in use replaces it, as
on the PS4. Run once from the repo root (after apply_nhl24_memlog.py), then rebuild:

    python3 apply_nhl24_reserve_fixed.py
    bash scripts/build-msys2.sh

The game's memory manager gives a 2 MiB block back by reserving the same range again with
MAP_FIXED (flags 0x400010: MAP_FIXED | MAP_NO_COALESCE), which on the PS4 unmaps what was there and
leaves the range reserved (shadPS4's MemoryManager::Reserve does the same). The runtime refused any
fixed reservation over a range in use, with "out of memory"; the game did not expect that and read
address -1 (guest fault at +0xdcbce0, Job thread). Now a fixed reservation unmaps the range first
(the GPU is told, as for sceKernelMunmap), and only MAP_NO_OVERWRITE (0x80) still refuses.
"""
import sys
from pathlib import Path

p = Path('src/runtime_memory.c')
if not p.exists():
    sys.exit('run this from the repo root (src/runtime_memory.c not found)')
s = p.read_text(encoding='utf-8')
if 'reserve over a range in use' in s:
    sys.exit('already applied')

old = ('    if ((flags & MAP_FIXED_FLAG) && overlaps((uintptr_t)*inout,(uintptr_t)*inout+size,0)) {\n'
       '        write_unlock(); memory_failure("reserve (fixed, in use)",(uint64_t)(uintptr_t)*inout,size,flags,NO_MEMORY); return NO_MEMORY;\n'
       '    }\n'
       '    int32_t result=place(inout,size,0,flags,alignment,KIND_RESERVED,0,0);\n'
       '    write_unlock();\n')
new = ('    if ((flags & MAP_FIXED_FLAG) && overlaps((uintptr_t)*inout,(uintptr_t)*inout+size,0)) {\n'
       '        /* NHL 24: reserve over a range in use. As on the PS4 (and shadPS4\'s Reserve), MAP_FIXED\n'
       '         * replaces what is there; only MAP_NO_OVERWRITE refuses. */\n'
       '        int32_t cleared=(flags & MAP_NO_OVERWRITE) ? NO_MEMORY : unmap_locked((uintptr_t)*inout,size);\n'
       '        if (cleared) {\n'
       '            write_unlock(); flush_hooks();\n'
       '            memory_failure("reserve (fixed, in use)",(uint64_t)(uintptr_t)*inout,size,flags,cleared); return cleared;\n'
       '        }\n'
       '    }\n'
       '    int32_t result=place(inout,size,0,flags,alignment,KIND_RESERVED,0,0);\n'
       '    write_unlock();\n'
       '    flush_hooks();\n')
if s.count(old) != 1:
    sys.exit('src/runtime_memory.c: reserve_range was not as expected (apply apply_nhl24_memlog.py first; nothing changed)')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8', newline='\n')
print('changed: src/runtime_memory.c (fixed reservations replace what is mapped there)')
