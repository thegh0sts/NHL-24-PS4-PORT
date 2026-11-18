#!/usr/bin/env python3
r"""NHL 24: the game's own flexible-memory size (its SceKernelMemParam), and more memory logging.
Run once from the repo root (after apply_nhl24_memlog.py), then rebuild:

    python3 apply_nhl24_memparam.py
    bash scripts/build-msys2.sh

Last run: the game took all of direct memory in 2 MiB pieces (as PS4 games do: the failure ends its
loop), then asked for 11,776,311,296 bytes of flexible memory, failed, and crashed in its allocator.
A PS4 game can set how much flexible memory it gets in its process parameters (SceProcParam ->
SceKernelMemParam -> flexible_memory_size); the runtime always allowed 448 MiB.

src/runtime.c   prints the process parameters at start-up (size, the memory parameter and the
                flexible size the game asks for) and keeps that size for the memory code.
src/runtime_memory.c
                flexible memory = the game's size when it sets one (at most the 1 GiB the runtime
                has room for; above that it says so), else 448 MiB as before;
                a failing flexible map, and the first answers of the flexible-size queries, are
                printed with the game's call sites.
"""
import sys
from pathlib import Path

rt = Path('src/runtime.c')
mem = Path('src/runtime_memory.c')
for p in (rt, mem):
    if not p.exists():
        sys.exit(f'run this from the repo root ({p} not found)')
r = rt.read_text(encoding='utf-8')
m = mem.read_text(encoding='utf-8')
if 'runtime_flexible_param' in r or 'runtime_flexible_param' in m:
    sys.exit('already applied')

r_old = 'void runtime_set_procparam(void *param) {\n    process_param=param;\n'
r_new = ('uint64_t runtime_flexible_param; /* NHL 24: SceKernelMemParam flexible_memory_size, 0 when unset */\n'
         'void runtime_set_procparam(void *param) {\n    process_param=param;\n'
         '    {   /* SceProcParam: +0x00 size, +0x08 magic/entries, +0x10 SDK, ... +0x38 SceKernelMemParam *. */\n'
         '        const uint64_t *q=(const uint64_t *)param;\n'
         '        if (q) {\n'
         '            printf("Runtime: process parameters: size %#llx, SDK %#llx",(unsigned long long)q[0],(unsigned long long)(q[0]>=0x18 ? q[2] : 0));\n'
         '            const uint64_t *mp=q[0]>=0x40 ? (const uint64_t *)q[7] : NULL;\n'
         '            if (mp) {\n'
         '                printf(", memory parameter size %#llx",(unsigned long long)mp[0]);\n'
         '                const uint64_t *flex=mp[0]>=0x18 ? (const uint64_t *)mp[2] : NULL;\n'
         '                if (flex) { runtime_flexible_param=*flex; printf(", flexible memory %llu MiB",(unsigned long long)(*flex>>20)); }\n'
         '                else printf(", flexible memory not set (448 MiB)");\n'
         '            } else printf(", no memory parameter");\n'
         '            printf("\\n");\n'
         '        }\n'
         '    }\n')
m_subs = [
    ('#define FLEXIBLE_SIZE (UINT64_C(448) * 1024 * 1024)',
     '/* NHL 24: flexible memory = the game\'s SceKernelMemParam size (runtime.c), at most the 1 GiB span\n'
     ' * the runtime keeps for it (FLEX_SPAN); 448 MiB when the game sets none. */\n'
     'extern uint64_t runtime_flexible_param;\n'
     'static uint64_t flexible_size_bytes(void) {\n'
     '    static uint64_t size;\n'
     '    if (!size) {\n'
     '        uint64_t want=runtime_flexible_param ? runtime_flexible_param : UINT64_C(448)*1024*1024;\n'
     '        size=want>(UINT64_C(1)<<30) ? (UINT64_C(1)<<30) : want;\n'
     '        printf("Runtime: flexible memory %llu MiB%s\\n",(unsigned long long)(size>>20),\n'
     '               want>size ? " (the game asks for more; the runtime has room for 1 GiB)" : "");\n'
     '    }\n'
     '    return size;\n'
     '}\n'
     '#define FLEXIBLE_SIZE flexible_size_bytes()'),
    ('    else fprintf(stderr,"Runtime: flexible map of %" PRIu64 " bytes failed (0x%x), in use=%" PRIu64 "\\n",\n'
     '                 size, (unsigned)result, flexible_bytes);',
     '    else {\n'
     '        uint64_t sites[3];\n'
     '        runtime_guest_call_sites(sites);\n'
     '        fprintf(stderr,"Runtime: flexible map of %" PRIu64 " bytes failed (0x%x), in use=%" PRIu64 " from +%#" PRIx64 " < +%#" PRIx64 " < +%#" PRIx64 "\\n",\n'
     '                size, (unsigned)result, flexible_bytes, sites[0], sites[1], sites[2]);\n'
     '    }'),
    ('    write_lock(); *out=FLEXIBLE_SIZE>flexible_bytes ? FLEXIBLE_SIZE-flexible_bytes : 0; write_unlock();\n    return 0;',
     '    write_lock(); *out=FLEXIBLE_SIZE>flexible_bytes ? FLEXIBLE_SIZE-flexible_bytes : 0; write_unlock();\n'
     '    static int told; if (told++<4) { uint64_t s[3]; runtime_guest_call_sites(s);\n'
     '        printf("Runtime: available flexible memory -> %" PRIu64 " from +%#" PRIx64 " < +%#" PRIx64 "\\n",*out,s[0],s[1]); }\n'
     '    return 0;'),
]
if r.count(r_old) != 1:
    sys.exit('src/runtime.c: runtime_set_procparam was not as expected (nothing changed)')
missing = [o[:60] for o, _ in m_subs if m.count(o) != 1]
if missing:
    sys.exit('src/runtime_memory.c was not as expected (apply apply_nhl24_memlog.py first; nothing changed):\n  ' + '\n  '.join(missing))
r = r.replace(r_old, r_new, 1)
for o, n in m_subs:
    m = m.replace(o, n, 1)
rt.write_text(r, encoding='utf-8', newline='\n')
mem.write_text(m, encoding='utf-8', newline='\n')
print('changed: src/runtime.c (process parameters printed, flexible size kept), src/runtime_memory.c (flexible size from the game, logging)')
