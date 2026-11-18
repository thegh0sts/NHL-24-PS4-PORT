#!/usr/bin/env python3
r"""NHL 24: report memory calls that fail, and fix the flexible-memory size answer. Run once from
the repo root (after batch 1), then rebuild:

    python3 apply_nhl24_memlog.py
    bash scripts/build-msys2.sh

The last run ended in a guest fault in the game's memory allocator (a Job thread read address -1
with rax = 0x8002000C, "out of memory", the answer of a memory call just before). The calls that
can give that answer without a log line are logged now, with the game's call sites:
  sceKernelReserveVirtualRange  (a fixed address that is already in use answers "out of memory")
  sceKernelAllocateDirectMemory (no room in the direct-memory pool)
  sceKernelMtypeprotect
Also: sceKernelAvailableFlexibleMemorySize (batch 1) answered the 1 GiB span, but the runtime
allows 448 MiB of flexible memory (FLEXIBLE_SIZE): it answers what can really be mapped now.
"""
import sys
from pathlib import Path

p = Path('src/runtime_memory.c')
if not p.exists():
    sys.exit('run this from the repo root (src/runtime_memory.c not found)')
s = p.read_text(encoding='utf-8')
if 'memory_failure' in s:
    sys.exit('already applied')

subs = [
    # a logging helper, before direct_size (the first exported function)
    ('static ABI uint64_t direct_size(void) { return POOL_SIZE; }',
     '/* NHL 24: memory calls that fail are reported with the game\'s call sites. */\n'
     'static void memory_failure(const char *call, uint64_t address, uint64_t size, int flags, int32_t result) {\n'
     '    uint64_t sites[3];\n'
     '    runtime_guest_call_sites(sites);\n'
     '    fprintf(stderr,"Runtime: %s %#" PRIx64 ", size=%" PRIu64 ", flags=0x%x failed (0x%x) from +%#" PRIx64 " < +%#" PRIx64 " < +%#" PRIx64 "\\n",\n'
     '            call,address,size,flags,(unsigned)result,sites[0],sites[1],sites[2]);\n'
     '}\n'
     'static ABI uint64_t direct_size(void) { return POOL_SIZE; }'),
    # direct_allocate: its two failure exits inside the search
    ('        if (slot<0 || start > end || size > end-start) { write_unlock(); return NO_SPACE; }',
     '        if (slot<0 || start > end || size > end-start) {\n'
     '            write_unlock(); memory_failure("direct allocation",(uint64_t)low,size,type,NO_SPACE); return NO_SPACE;\n'
     '        }'),
    # reserve_range: fixed address in use, and place() failures
    ('    if ((flags & MAP_FIXED_FLAG) && overlaps((uintptr_t)*inout,(uintptr_t)*inout+size,0)) {\n'
     '        write_unlock(); return NO_MEMORY;\n'
     '    }',
     '    if ((flags & MAP_FIXED_FLAG) && overlaps((uintptr_t)*inout,(uintptr_t)*inout+size,0)) {\n'
     '        write_unlock(); memory_failure("reserve (fixed, in use)",(uint64_t)(uintptr_t)*inout,size,flags,NO_MEMORY); return NO_MEMORY;\n'
     '    }'),
    ('    if (!result) printf("Runtime: reserved virtual range %p, size=%" PRIu64 "\\n", *inout, size);',
     '    if (!result) printf("Runtime: reserved virtual range %p, size=%" PRIu64 "\\n", *inout, size);\n'
     '    else memory_failure("reserve",(uint64_t)(uintptr_t)*inout,size,flags,result);'),
    # flexible available: the real limit
    ('    write_lock(); *out=FLEX_SPAN>flexible_bytes ? FLEX_SPAN-flexible_bytes : 0; write_unlock();',
     '    write_lock(); *out=FLEXIBLE_SIZE>flexible_bytes ? FLEXIBLE_SIZE-flexible_bytes : 0; write_unlock();'),
    ('static ABI int32_t flexible_configured(uint64_t *out) { if (!out) return INVALID; *out=FLEX_SPAN; return 0; }',
     'static ABI int32_t flexible_configured(uint64_t *out) { if (!out) return INVALID; *out=FLEXIBLE_SIZE; return 0; }'),
    # mtypeprotect failures
    ('    int32_t result=protect_locked((uintptr_t)address,size,prot,type);\n    write_unlock();\n    flush_hooks();\n    return result;\n}',
     '    int32_t result=protect_locked((uintptr_t)address,size,prot,type);\n    write_unlock();\n    flush_hooks();\n'
     '    if (result) memory_failure("mtypeprotect",(uint64_t)(uintptr_t)address,size,prot,result);\n    return result;\n}'),
]
missing = [old[:70] for old, _ in subs if s.count(old) != 1]
if missing:
    sys.exit('src/runtime_memory.c was not as expected (nothing changed); not found:\n  ' + '\n  '.join(missing))
for old, new in subs:
    s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8', newline='\n')
print('changed: src/runtime_memory.c (failing memory calls logged; flexible memory sizes = FLEXIBLE_SIZE)')
