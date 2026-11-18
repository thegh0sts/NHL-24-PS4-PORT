#!/usr/bin/env python3
r"""NHL 24: sceKernelMapDirectMemory2 (libkernel, newer SDKs). Run once from the repo root:

    python3 apply_nhl24_mapdirect2.py

NHL 24 (SDK 10.50) maps its direct memory with sceKernelMapDirectMemory2, which the runtime did
not have ("STOP: first unsupported PS4 import: BQQniolj9tQ#libkernel ... sceKernelMapDirectMemory2").
It is sceKernelMapDirectMemory with the memory type as an extra argument (after the size):
    int32_t sceKernelMapDirectMemory2(void **addr, size_t len, int type, int prot, int flags,
                                      off_t directMemoryStart, size_t alignment)
This maps as sceKernelMapDirectMemory does, then records the type on the mapping (as
sceKernelMtypeprotect does), so memory-type queries answer what the game set.
Then rebuild: bash scripts/build-msys2.sh
"""
import sys
from pathlib import Path

p = Path('src/runtime_memory.c')
if not p.exists():
    sys.exit('run this from the repo root (src/runtime_memory.c not found)')
s = p.read_text(encoding='utf-8')
if 'direct_map2' in s:
    sys.exit('already applied')

anchor_fn = 'static int32_t unmap_locked(uintptr_t start, uint64_t size) {'
anchor_tab = '{"sceKernelMapDirectMemory",direct_map},'
anchor_protect = 'static int32_t protect_locked(uintptr_t start, uint64_t size, int prot, int type) {'
for a in (anchor_fn, anchor_tab, anchor_protect):
    if s.count(a) != 1:
        sys.exit(f'src/runtime_memory.c: {a[:60]!r} was not found as expected (nothing changed)')

# protect_locked is defined after direct_map: declare it before the new function.
fn = ('/* sceKernelMapDirectMemory2 (newer SDKs, NHL 24): sceKernelMapDirectMemory with the memory type\n'
      ' * after the size; the type is recorded on the mapping as sceKernelMtypeprotect does. */\n'
      'static int32_t protect_locked(uintptr_t start, uint64_t size, int prot, int type);\n'
      'static ABI int32_t direct_map2(void **out, uint64_t size, int type, int prot, int flags, int64_t physical,\n'
      '                               uint64_t alignment) {\n'
      '    write_lock();\n'
      '    int32_t result=map_direct_locked(out,size,prot,flags,physical,alignment);\n'
      '    if (!result && type>=0) protect_locked((uintptr_t)*out,size,prot,type);\n'
      '    write_unlock();\n'
      '    flush_hooks();\n'
      '    if (!result) printf("Runtime: mapped direct memory %p, size=%" PRIu64 ", prot=0x%x, type=%d (MapDirectMemory2)\\n", *out, size, prot, type);\n'
      '    else printf("Runtime: mapping direct memory %#" PRIx64 ", size=%" PRIu64 " failed (error %#x, MapDirectMemory2)\\n", (uint64_t)physical, size, (unsigned)result);\n'
      '    return result;\n'
      '}\n')
s = s.replace(anchor_fn, fn + anchor_fn, 1)
s = s.replace(anchor_tab, anchor_tab + ' {"sceKernelMapDirectMemory2",direct_map2},', 1)
p.write_text(s, encoding='utf-8', newline='\n')
print('changed: src/runtime_memory.c (sceKernelMapDirectMemory2)')
