#!/usr/bin/env python3
r"""NHL 24: fixed mappings in the PS4's low "system-managed" address range (Windows). Run once from
the repo root, then rebuild:

    python3 apply_nhl24_sysmap.py
    bash scripts/build-msys2.sh

The game maps 128 KiB of GPU memory at the fixed address 0x7F0000000, below the PS4 user range
(0x1000000000-0xFC00000000) the Windows runtime reserves; the PS4 allows fixed mappings in its
system-managed range below that. On Windows only the reserved range can take guest views, so the
mapping failed ("mapping guest memory 0x44000000+0x20000 at 00000007f0000000 failed"), the game
got "out of memory" and read address -1.

src/platform/platform_win.c, platform.h
    platform_pool_reserve_extra(lo, hi): reserves a second guest range (0 or -1; not fatal),
    alongside the user range; the bounds checks cover both.
src/runtime_memory.c
    at start-up (and when the pool is created) the range 0x400000000-0x800000000 is reserved
    too (below the runtime's own low area at 0x800000000, which holds the image and stacks);
    if Windows has something there already the runtime says so and carries on.
"""
import sys
from pathlib import Path

win = Path('src/platform/platform_win.c')
hdr = Path('src/platform/platform.h')
mem = Path('src/runtime_memory.c')
for p in (win, hdr, mem):
    if not p.exists():
        sys.exit(f'run this from the repo root ({p} not found)')
w, h, m = (p.read_text(encoding='utf-8') for p in (win, hdr, mem))
if 'platform_pool_reserve_extra' in w:
    sys.exit('already applied')

w_old = '/* A view of the section over the placeholder of region r.'
w_new = ('/* NHL 24: a second guest range (the PS4 system-managed area below the user range), reserved\n'
         ' * like the user range; 0, or -1 when Windows already has something there. */\n'
         'int platform_pool_reserve_extra(uintptr_t lo, uintptr_t hi) {\n'
         '    for (size_t i = 0; i < region_count; ++i) if (regions[i].start >= lo && regions[i].end <= hi) return 0;\n'
         '    if (!VirtualAlloc2(NULL, (void *)lo, hi - lo, MEM_RESERVE | MEM_RESERVE_PLACEHOLDER, PAGE_NOACCESS, NULL, 0)) return -1;\n'
         '    if (!reserve_hi || lo < reserve_lo) reserve_lo = lo;\n'
         '    if (hi > reserve_hi) reserve_hi = hi;\n'
         '    region_insert(region_index(lo), (HostRegion){lo, hi, 0, 0});\n'
         '    return 0;\n'
         '}\n' + w_old)
w_old2 = '    if (region_count) return;\n    if (!VirtualAlloc2(NULL, (void *)lo, hi - lo, MEM_RESERVE | MEM_RESERVE_PLACEHOLDER, PAGE_NOACCESS, NULL, 0)) {'
w_new2 = ('    for (size_t i = 0; i < region_count; ++i) if (regions[i].start >= lo && regions[i].end <= hi) return;\n'
          '    if (!VirtualAlloc2(NULL, (void *)lo, hi - lo, MEM_RESERVE | MEM_RESERVE_PLACEHOLDER, PAGE_NOACCESS, NULL, 0)) {')
w_old3 = '    reserve_lo = lo; reserve_hi = hi;\n    region_insert(0, (HostRegion){lo, hi, 0, 0});'
w_new3 = ('    if (!reserve_hi || lo < reserve_lo) reserve_lo = lo;\n'
          '    if (hi > reserve_hi) reserve_hi = hi;\n'
          '    region_insert(region_index(lo), (HostRegion){lo, hi, 0, 0});')
h_old = 'void platform_pool_reserve_range(uintptr_t lo, uintptr_t hi);'
h_new = (h_old + '\n/* A second guest range (NHL 24: the PS4 system-managed area). 0, or -1 if the host uses it. */\n'
         'int platform_pool_reserve_extra(uintptr_t lo, uintptr_t hi);')
m_old = '    platform_pool_reserve_range(USER_MIN,USER_MAX);\n    return platform_pool_create(POOL_SIZE+FLEX_SPAN,&backing_base);'
m_new = ('    platform_pool_reserve_range(USER_MIN,USER_MAX);\n'
         '    reserve_system_managed();\n'
         '    return platform_pool_create(POOL_SIZE+FLEX_SPAN,&backing_base);')
m_old2 = 'static int pool(void) {\n    if (backing_base) return 0;'
m_new2 = ('/* NHL 24: the PS4 lets games map at fixed addresses in its system-managed area below the user\n'
          ' * range (NHL 24: GPU memory at 0x7F0000000). Reserved too, up to the runtime\'s own low area. */\n'
          '#define SYSTEM_MANAGED_MIN UINT64_C(0x0400000000)\n'
          '#define SYSTEM_MANAGED_MAX UINT64_C(0x0800000000)\n'
          'static void reserve_system_managed(void) {\n'
          '    static int done;\n'
          '    if (done++) return;\n'
          '    if (platform_pool_reserve_extra(SYSTEM_MANAGED_MIN,SYSTEM_MANAGED_MAX))\n'
          '        fprintf(stderr,"Runtime: the system-managed range %#" PRIx64 "-%#" PRIx64 " is in use on this PC: fixed mappings there will fail\\n",\n'
          '                SYSTEM_MANAGED_MIN,SYSTEM_MANAGED_MAX);\n'
          '}\n' + m_old2)
m_old3 = 'void runtime_memory_reserve(void) { platform_pool_reserve_range(USER_MIN,USER_MAX); }'
m_new3 = 'void runtime_memory_reserve(void) { platform_pool_reserve_range(USER_MIN,USER_MAX); reserve_system_managed(); }'

checks = [(w, w_old, 'platform_win.c view_map comment'), (w, w_old2, 'platform_win.c reserve_range start'),
          (w, w_old3, 'platform_win.c reserve_range end'), (h, h_old, 'platform.h reserve_range'),
          (m, m_old, 'runtime_memory.c pool()'), (m, m_old2, 'runtime_memory.c pool() start'),
          (m, m_old3, 'runtime_memory.c runtime_memory_reserve')]
bad = [name for text, old, name in checks if text.count(old) != 1]
if bad:
    sys.exit('not as expected (nothing changed): ' + ', '.join(bad))
w = w.replace(w_old, w_new, 1).replace(w_old2, w_new2, 1).replace(w_old3, w_new3, 1)
h = h.replace(h_old, h_new, 1)
m = m.replace(m_old2, m_new2, 1).replace(m_old, m_new, 1).replace(m_old3, m_new3, 1)
win.write_text(w, encoding='utf-8', newline='\n')
hdr.write_text(h, encoding='utf-8', newline='\n')
mem.write_text(m, encoding='utf-8', newline='\n')
print('changed: src/platform/platform_win.c, src/platform/platform.h, src/runtime_memory.c (system-managed range 0x400000000-0x800000000)')
