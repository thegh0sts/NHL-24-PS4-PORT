#!/usr/bin/env python3
r"""Windows: the guest's red zone moved out of reach of exception frames (NHL 24 crash fix; also
protects NHL 19 and UFC 3). Run once from the repo root, then rebuild:

    python3 apply_nhl24_redzone.py
    bash scripts/build-msys2.sh && BB_SKIP_PREPARE=1 bash scripts/run-msys2.sh nhl24

The problem (confirmed with apply_nhl24_faultnote.py): PS4 code may keep data in the 128 bytes
below its stack pointer (the System V "red zone"). Windows writes its exception information right
there whenever an instruction faults, and the GPU memory tracking makes guest accesses to watched
pages fault thousands of times (handled, then the game continues). NHL 24's draw-list sort
(FUN_07660830) lost a pointer it had saved at [rsp-0x28] that way and crashed at the end of the
match loading screen.

The fix, at load time (src/runtime_fp.c, next to the deterministic FP patch it reuses): every
instruction that addresses memory below rsp ([rsp-d], [rsp+index*s-d], or lea of them) is
rewritten to address 64 KiB lower; all red-zone accesses move together, so they still meet.
Each rewritten instruction runs from a small stub (jmp there and back). Guest stacks already have
256 KiB of committed room below their size, and the main thread's stack is 16 MiB.
The log says how many were moved: "Red zone (BB_REDZONE_SHIFT): N of M accesses moved ...".

On by default on Windows; BB_REDZONE_SHIFT=0 turns it off (for comparison). Linux does not need it
(its signal frames skip the red zone).

src/runtime_fp.c   runtime_redzone_enabled(), runtime_redzone_patch_image()
src/runtime.h      their declarations
src/probe.c        the patch runs after the TLS rewrite and before the deterministic FP patch
"""
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
code_file = here / 'redzone_code.c'
fp, hdr, probe = Path('src/runtime_fp.c'), Path('src/runtime.h'), Path('src/probe.c')
for p in (fp, hdr, probe):
    if not p.exists():
        sys.exit(f'run this from the repo root ({p} not found)')
if not code_file.exists():
    sys.exit(f'{code_file.name} must be next to this script')
f, h, b = (p.read_text(encoding='utf-8') for p in (fp, hdr, probe))
if 'runtime_redzone_patch_image' in f:
    sys.exit('already applied')

h_old = '                                void *(*map_near)(size_t), RuntimeFpStats *stats);\n'
h_new = (h_old +
         '/* Windows: guest red-zone accesses moved 64 KiB lower (exception frames overwrite the red zone).\n'
         ' * RuntimeFpStats: found/patched/unpatched accesses, displaced = switch-table entries seen. */\n'
         'int runtime_redzone_enabled(void);\n'
         'uint64_t runtime_redzone_patch_image(unsigned char *image, uint64_t size, const uint64_t *seg_address, const uint64_t *seg_size,\n'
         '                                     const uint64_t *seg_flags, uint64_t segments, const uint64_t *pointers, uint64_t pointer_count,\n'
         '                                     void *(*map_near)(size_t), RuntimeFpStats *stats);\n')
b_old = '    /* ufc3 online (UFC-25): approximate reciprocals that give the same bits on every CPU. */\n'
b_new = ('    /* Windows: the guest red zone out of reach of exception frames (runtime_fp.c). */\n'
         '    if (runtime_redzone_enabled()) {\n'
         '        uint64_t *addresses = calloc(ns ? ns : 1, sizeof(uint64_t)), *sizes = calloc(ns ? ns : 1, sizeof(uint64_t)), *flags = calloc(ns ? ns : 1, sizeof(uint64_t));\n'
         '        uint64_t *pointers = calloc(nr ? nr : 1, sizeof(uint64_t)), pointer_count = 0;\n'
         '        if (!addresses || !sizes || !flags || !pointers) fail("allocation failed");\n'
         '        for (uint64_t i = 0; i < ns; ++i) { addresses[i] = segments[i].address; sizes[i] = segments[i].size; flags[i] = segments[i].flags; }\n'
         '        for (uint64_t i = 0; i < nr; ++i) if (!relocs[i].kind) pointers[pointer_count++] = relocs[i].value;\n'
         '        RuntimeFpStats rz;\n'
         '        const uint64_t start = platform_monotonic_ns();\n'
         '        runtime_redzone_patch_image(image, size, addresses, sizes, flags, ns, pointers, pointer_count, map_near_image, &rz);\n'
         '        printf("Red zone (BB_REDZONE_SHIFT): %" PRIu64 " of %" PRIu64 " accesses moved 64 KiB lower in %" PRIu64 " functions "\n'
         '               "(%" PRIu64 " kept, %" PRIu64 " switch-table entries seen), %" PRIu64 " KiB of stubs, %.0f ms\\n",\n'
         '               rz.patched, rz.found, rz.functions, rz.unpatched, rz.displaced, rz.stub_bytes / 1024,\n'
         '               (double)(platform_monotonic_ns() - start) / 1e6);\n'
         '        free(addresses); free(sizes); free(flags); free(pointers);\n'
         '    }\n' + b_old)
bad = [n for t, o, n in ((h, h_old, 'runtime.h'), (b, b_old, 'probe.c')) if t.count(o) != 1]
if bad:
    sys.exit('not as expected (nothing changed): ' + ', '.join(bad))
f = f.rstrip('\n') + '\n' + code_file.read_text(encoding='utf-8')
fp.write_text(f, encoding='utf-8', newline='\n')
hdr.write_text(h.replace(h_old, h_new, 1), encoding='utf-8', newline='\n')
probe.write_text(b.replace(b_old, b_new, 1), encoding='utf-8', newline='\n')
print('changed: src/runtime_fp.c, src/runtime.h, src/probe.c (red-zone accesses moved below exception frames on Windows)')
