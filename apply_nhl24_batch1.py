#!/usr/bin/env python3
r"""NHL 24, batch 1: kernel, memory and system-service functions the game uses at start-up that the
runtime lacked. Run once from the repo root, then rebuild:

    python3 apply_nhl24_batch1.py
    bash scripts/build-msys2.sh

src/runtime_memory.c
  sceKernelAvailableFlexibleMemorySize   flexible memory not yet mapped (the runtime's 1 GiB span)
  sceKernelConfiguredFlexibleMemorySize  the whole span
  sceKernelMtypeprotect                  sceKernelMprotect that also records the memory type
src/runtime_kernel.c
  sceKernelSleep                         seconds
  sceKernelIsProspero                    0: a PS4, not a PS5
src/runtime_services.c
  sceUserServiceInitialize2              sceUserServiceInitialize with a thread priority/affinity
  sceSystemServiceGetDisplaySafeAreaInfo the whole screen is safe (ratio 1.0)
  scePlayGoGetLanguageMask / SetLanguageMask   every language installed
  sceAppContentGetPftFlag                0 (no PFT)
  sceAppContentDownloadDataGetAvailableSpaceKb 1 GiB free
Each part is applied only if its file still has the expected anchor; nothing changes otherwise.
"""
import sys
from pathlib import Path

edits = {
    'src/runtime_memory.c': (
        'static const RuntimeExport exports[]={',
        '/* NHL 24: flexible memory sizes (the 1 GiB span the runtime gives flexible memory) and\n'
        ' * sceKernelMtypeprotect (sceKernelMprotect plus the memory type). */\n'
        'static ABI int32_t flexible_available(uint64_t *out) {\n'
        '    if (!out) return INVALID;\n'
        '    write_lock(); *out=FLEX_SPAN>flexible_bytes ? FLEX_SPAN-flexible_bytes : 0; write_unlock();\n'
        '    return 0;\n'
        '}\n'
        'static ABI int32_t flexible_configured(uint64_t *out) { if (!out) return INVALID; *out=FLEX_SPAN; return 0; }\n'
        'static ABI int32_t kernel_mtypeprotect(const void *address, uint64_t size, int type, int prot) {\n'
        '    write_lock();\n'
        '    int32_t result=protect_locked((uintptr_t)address,size,prot,type);\n'
        '    write_unlock();\n'
        '    flush_hooks();\n'
        '    return result;\n'
        '}\n',
        '    {"sceKernelMprotect",kernel_mprotect},',
        '    {"sceKernelAvailableFlexibleMemorySize",flexible_available}, {"sceKernelConfiguredFlexibleMemorySize",flexible_configured},\n'
        '    {"sceKernelMtypeprotect",kernel_mtypeprotect},\n'
        '    {"sceKernelMprotect",kernel_mprotect},'),
    'src/runtime_kernel.c': (
        'static const RuntimeExport exports[]={',
        '/* NHL 24: sceKernelSleep (seconds) and sceKernelIsProspero (0: this is a PS4). */\n'
        'static ABI int32_t kernel_sleep_seconds(uint32_t seconds) { sleep_ns((uint64_t)seconds*1000000000u); return 0; }\n'
        'static ABI int32_t kernel_is_prospero(void) { return 0; }\n',
        '    {"sceKernelUsleep",kernel_usleep},',
        '    {"sceKernelSleep",kernel_sleep_seconds}, {"sceKernelIsProspero",kernel_is_prospero},\n'
        '    {"sceKernelUsleep",kernel_usleep},'),
    'src/runtime_services.c': (
        'static const RuntimeExport exports[]={',
        '/* NHL 24 (SDK 10.50) start-up services. */\n'
        'static ABI int32_t user_initialize2(int32_t priority, uint64_t affinity) {\n'
        '    (void)priority; (void)affinity; return user_initialize(NULL);\n'
        '}\n'
        'static ABI int32_t display_safe_area(float *info) { if (!info) return -1; memset(info,0,4+128); *info=1.0f; return 0; }\n'
        'static ABI int32_t playgo_language_mask_get(int32_t handle, uint64_t *mask) { (void)handle; if (!mask) return -1; *mask=~UINT64_C(0); return 0; }\n'
        'static ABI int32_t playgo_language_mask_set(int32_t handle, uint64_t mask) { (void)handle; (void)mask; return 0; }\n'
        'static ABI int32_t appcontent_pft_flag(int32_t *flag) { if (flag) *flag=0; return 0; }\n'
        'static ABI int32_t appcontent_download_space(const void *mount, uint64_t *kb) { (void)mount; if (kb) *kb=1024*1024; return 0; }\n',
        '    {"sceUserServiceInitialize",user_initialize},',
        '    {"sceUserServiceInitialize2",user_initialize2}, {"sceSystemServiceGetDisplaySafeAreaInfo",display_safe_area},\n'
        '    {"scePlayGoGetLanguageMask",playgo_language_mask_get}, {"scePlayGoSetLanguageMask",playgo_language_mask_set},\n'
        '    {"sceAppContentGetPftFlag",appcontent_pft_flag}, {"sceAppContentDownloadDataGetAvailableSpaceKb",appcontent_download_space},\n'
        '    {"sceUserServiceInitialize",user_initialize},'),
}

for name in edits:
    if not Path(name).exists():
        sys.exit(f'run this from the repo root ({name} not found)')
done = 0
for name, (fn_anchor, fn, tab_anchor, tab) in edits.items():
    p = Path(name)
    s = p.read_text(encoding='utf-8')
    marker = tab.split('"')[1]
    if f'"{marker}"' in s:
        print(f'{name}: already applied')
        continue
    if s.count(fn_anchor) != 1 or s.count(tab_anchor) != 1:
        print(f'{name}: anchors not found as expected, skipped (nothing changed in it)')
        continue
    s = s.replace(fn_anchor, fn + '\n' + fn_anchor, 1).replace(tab_anchor, tab, 1)
    p.write_text(s, encoding='utf-8', newline='\n')
    print(f'changed: {name}')
    done += 1
print(f'{done} file(s) changed')
