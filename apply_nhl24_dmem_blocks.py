#!/usr/bin/env python3
r"""NHL 24: room for many more direct-memory allocations. Run once from the repo root, rebuild:

    python3 apply_nhl24_dmem_blocks.py
    bash scripts/build-msys2.sh && BB_SKIP_PREPARE=1 bash scripts/run-msys2.sh nhl24

Going into a match, NHL 24 makes thousands of small (16-64 KiB) direct-memory allocations. The
runtime's table held 4096 of them; when it was full every allocation failed ("direct allocation
0, size=65536 ... failed (0x80020023)") although only ~3.7 GB of the 4.9 GB pool was in use. The
game fell back to flexible memory until that ran out too, then crashed on purpose in its
allocator (guest fault: write to address 0 at +0xdcbbce, Frostbite's VirtualAlloc_Sony).

src/runtime_memory.c
    - the table holds 65536 allocations (LIMIT 4096 -> 65536, ~1.5 MB);
    - a free entry is looked for from the last one used (not from 0 each time);
    - a free range is tried first where the previous allocation (same lower bound) ended; if it
      is taken, the lowest gap that fits is found over the blocks sorted by start (freed holes
      are still reused). Before, each allocation re-scanned every block for each block passed,
      which would be far too slow with 65536.
    - a full table is reported as such ("direct allocation (table full)").
"""
import sys
from pathlib import Path

p = Path('src/runtime_memory.c')
if not p.exists():
    sys.exit('run this from the repo root (src/runtime_memory.c not found)')
s = p.read_text(encoding='utf-8')
if 'NHL 24: thousands of small allocations' in s:
    sys.exit('already applied')

subs = [
    ('#define LIMIT 4096\n',
     '/* NHL 24: thousands of small allocations going into a match (4096 were not enough). */\n'
     '#define LIMIT 65536\n'),
    ('    uint64_t start = align_up((uint64_t)low, alignment);\n'
     '    int slot = -1;\n'
     '    for (int i=0; i<LIMIT; ++i) if (!blocks[i].used) { slot=i; break; }\n'
     '    for (;;) {\n'
     '        if (slot<0 || start > end || size > end-start) {\n'
     '            write_unlock(); memory_failure("direct allocation",(uint64_t)low,size,type,NO_SPACE); return NO_SPACE;\n'
     '        }\n'
     '        int overlap = 0;\n'
     '        for (int i=0; i<LIMIT; ++i) {\n'
     '            Block b = blocks[i];\n'
     '            if (b.used && start < b.start+b.size && b.start < start+size) {\n'
     '                start = align_up(b.start+b.size, alignment); overlap = 1; break;\n'
     '            }\n'
     '        }\n'
     '        if (!overlap) break;\n'
     '    }\n',
     '    /* Free entry: from the last one handed out. Free range: first where the previous allocation\n'
     '     * with the same lower bound ended; else the lowest gap that fits, over the blocks sorted. */\n'
     '    static int slot_hint;\n'
     '    static uint64_t cursor_low = UINT64_MAX, cursor;\n'
     '    int slot = -1;\n'
     '    for (int n=0; n<LIMIT; ++n) {\n'
     '        const int i = (slot_hint + n) % LIMIT;\n'
     '        if (!blocks[i].used) { slot=i; break; }\n'
     '    }\n'
     '    uint64_t start = UINT64_MAX;\n'
     '    if (slot>=0 && cursor_low==(uint64_t)low) {\n'
     '        const uint64_t at = align_up(cursor, alignment);\n'
     '        int clear = at>=(uint64_t)low && at<=end && size<=end-at;\n'
     '        for (int i=0; clear && i<LIMIT; ++i)\n'
     '            if (blocks[i].used && at < blocks[i].start+blocks[i].size && blocks[i].start < at+size) clear = 0;\n'
     '        if (clear) start = at;\n'
     '    }\n'
     '    if (slot>=0 && start==UINT64_MAX) start = lowest_gap((uint64_t)low,end,size,alignment);\n'
     '    if (slot<0 || start==UINT64_MAX) {\n'
     '        write_unlock(); memory_failure(slot<0 ? "direct allocation (table full)" : "direct allocation",\n'
     '                                       (uint64_t)low,size,type,NO_SPACE); return NO_SPACE;\n'
     '    }\n'),
    ('static ABI uint64_t direct_size(void) { return POOL_SIZE; }\n',
     '/* NHL 24: the lowest free range of [low,end) that fits, over the used blocks sorted by start. */\n'
     'static Block sorted_blocks[LIMIT];\n'
     'static int block_order(const void *a, const void *b) {\n'
     '    const uint64_t x=((const Block *)a)->start, y=((const Block *)b)->start;\n'
     '    return x<y ? -1 : x>y;\n'
     '}\n'
     'static uint64_t lowest_gap(uint64_t low, uint64_t end, uint64_t size, uint64_t alignment) {\n'
     '    int n=0;\n'
     '    for (int i=0;i<LIMIT;++i) if (blocks[i].used) sorted_blocks[n++]=blocks[i];\n'
     '    qsort(sorted_blocks,(size_t)n,sizeof *sorted_blocks,block_order);\n'
     '    uint64_t at=align_up(low,alignment);\n'
     '    for (int i=0;i<n;++i) {\n'
     '        const Block *b=&sorted_blocks[i];\n'
     '        if (b->start+b->size<=at) continue;\n'
     '        if (at>end || size>end-at) return UINT64_MAX;\n'
     '        if (at+size<=b->start) return at;\n'
     '        at=align_up(b->start+b->size,alignment);\n'
     '    }\n'
     '    return at<=end && size<=end-at ? at : UINT64_MAX;\n'
     '}\n'
     'static ABI uint64_t direct_size(void) { return POOL_SIZE; }\n'),
    ('    blocks[slot] = (Block){start, size, type, 1}; *out = (int64_t)start;\n',
     '    blocks[slot] = (Block){start, size, type, 1}; *out = (int64_t)start;\n'
     '    slot_hint = (slot + 1) % LIMIT; cursor_low = (uint64_t)low; cursor = start + size;\n'),
]
missing = [old[:70] for old, _ in subs if s.count(old) != 1]
if missing:
    sys.exit('src/runtime_memory.c was not as expected (nothing changed); not found:\n  ' + '\n  '.join(missing))
for old, new in subs:
    s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8', newline='\n')
print('changed: src/runtime_memory.c (65536 direct allocations; faster free-range search)')
