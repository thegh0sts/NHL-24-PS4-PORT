#!/usr/bin/env python3
r"""NHL 24: game modules loaded at run time (sceKernelLoadStartModule + sceKernelDlsym).
Run once from the repo root of the NHL 24 port, then prepare again (not BB_SKIP_PREPARE):

    python3 apply_nhl24_dynmodules.py
    bash scripts/build-msys2.sh && bash scripts/run-msys2.sh nhl24

NHL 24 keeps its renderer in a module of its own in the game folder,
/app0/Engine.Render.Core2.PlatformPs4.prx, which it loads with sceKernelLoadStartModule and then
looks into with sceKernelDlsym. The port only linked modules from sce_module/ at start-up and
answered every load "not found".

scripts/link_modules.py
    a module named in the profile is taken from the game folder's root when it is there (else
    from sce_module/ as before; a root module that is missing is skipped with a note). Root
    modules are linked like the others but marked "deferred": their start code does not run at
    boot. out/dynamic_modules.txt lists each one (file, start, base, size) and its exports (NID,
    image offset) for the runtime.
src/probe.c
    deferred modules are skipped at boot ("deferred until sceKernelLoadStartModule"); the runtime
    is told where the guest image is.
src/runtime.h, src/runtime_kernel.c
    sceKernelLoadStartModule(path): a deferred module with that file name runs its start code
    (once) and gets a handle; anything else is "not found" as before.
    sceKernelDlsym(handle, name, &address): the name's NID (SHA-1 with the PS4 salt, as
    prepare.py computes it) looked up in that module's exports.
    The call-site helper (failure logs) uses the real guest image range (it assumed UFC 3's).
scripts/game_check.py
    NHL 24's modules: + Engine.Render.Core2.PlatformPs4.prx, Engine.BuildInfo.prx (game folder).
scripts/run-msys2.sh
    BB_DYNAMIC_MODULES=out/dynamic_modules.txt for the game.
"""
import sys
from pathlib import Path

files = {k: Path(v) for k, v in dict(link='scripts/link_modules.py', probe='src/probe.c', hdr='src/runtime.h',
                                     kernel='src/runtime_kernel.c', check='scripts/game_check.py',
                                     run='scripts/run-msys2.sh').items()}
for p in files.values():
    if not p.exists():
        sys.exit(f'run this from the repo root ({p} not found)')
text = {k: p.read_text(encoding='utf-8') for k, p in files.items()}
if 'dynamic_modules.txt' in text['link']:
    sys.exit('already applied')

edits = {k: [] for k in files}

# ---------- link_modules.py ----------
edits['link'] += [
    ("DEFAULT_MODULES = ('libc.prx', 'libSceFios2.prx')",
     "DEFAULT_MODULES = ('libc.prx', 'libSceFios2.prx')\n"
     "DEFERRED_INIT = 1 << 62  # NHL 24: start code runs at sceKernelLoadStartModule, not at boot\n\n\n"
     "def module_path(game, filename):\n"
     "    \"\"\"NHL 24: a module in the game folder's root (loaded by the game at run time), else sce_module/.\"\"\"\n"
     "    root = game / filename\n"
     "    if root.is_file():\n"
     "        return root, True\n"
     "    return game / 'sce_module' / filename, False"),
    ("    for filename in module_names:\n        m = module(game / 'sce_module' / filename)\n",
     "    dynamic = []\n"
     "    for filename in module_names:\n"
     "        path, deferred = module_path(game, filename)\n"
     "        if not path.is_file() and filename not in DEFAULT_MODULES:\n"
     "            print(f'link_modules: {filename} is not in the game folder or sce_module/: skipped')\n"
     "            continue\n"
     "        m = module(path)\n"),
    ("        count = 0\n        for s in m['symbols']:\n",
     "        count = 0\n        module_exports = []\n        for s in m['symbols']:\n"),
    ("                by_nid[(s['identity'][0], s['identity'][1][0])].append(entry_value)\n                count += 1\n",
     "                by_nid[(s['identity'][0], s['identity'][1][0])].append(entry_value)\n"
     "                module_exports.append((s['identity'][0], base + s['value']))\n"
     "                count += 1\n"),
    ("        table.append(dict(file=filename, base=base, size=modsize, init=base + m['tags'].get(12, 0),",
     "        if deferred:\n"
     "            dynamic.append(dict(file=filename, init=base + m['tags'].get(12, 0), base=base, size=modsize,\n"
     "                                exports=module_exports))\n"
     "        table.append(dict(file=filename, base=base, size=modsize,\n"
     "                          init=(base + m['tags'].get(12, 0)) | (DEFERRED_INIT if deferred else 0),"),
    ("    (out / 'link.json').write_text(json.dumps(report, indent=2) + '\\n')",
     "    (out / 'link.json').write_text(json.dumps(report, indent=2) + '\\n')\n"
     "    with (out / 'dynamic_modules.txt').open('w', newline='\\n') as f:\n"
     "        for d in dynamic:\n"
     "            f.write(f\"module {d['file']} {d['init']:#x} {d['base']:#x} {d['size']:#x}\\n\")\n"
     "            for nid_, offset in d['exports']:\n"
     "                f.write(f'export {nid_} {offset:#x}\\n')\n"
     "    if dynamic:\n"
     "        print('Deferred game modules (started by the game): ' + ', '.join(d['file'] for d in dynamic))"),
    ("    summary = ', '.join(f\"{t['file']}@{t['base']:#x}\" for t in table)",
     "    summary = ', '.join(f\"{t['file']}@{t['base']:#x}\" for t in table)  # base addresses"),
]
# report: init hex printing of the flagged value is fine (hex()).

# ---------- probe.c ----------
edits['probe'] += [
    ('typedef struct { uint64_t base, size, init, tls_address, tls_memsz, tls_filesz, tls_module; } LinkedModule;',
     'typedef struct { uint64_t base, size, init, tls_address, tls_memsz, tls_filesz, tls_module; } LinkedModule;\n'
     '/* NHL 24: link_modules.py marks game-folder modules whose start code waits for sceKernelLoadStartModule. */\n'
     '#define DEFERRED_INIT (UINT64_C(1)<<62)'),
    ('        if (!mapped(segments,ns,modules[m].init,1) ||',
     '        if (!mapped(segments,ns,modules[m].init&~DEFERRED_INIT,1) ||'),
    ('                if ((segments[i].flags&1) && modules[m].init>=segments[i].address && modules[m].init-segments[i].address<segments[i].size) init_executable=1;',
     '                if ((segments[i].flags&1) && (modules[m].init&~DEFERRED_INIT)>=segments[i].address && (modules[m].init&~DEFERRED_INIT)-segments[i].address<segments[i].size) init_executable=1;'),
    ('        runtime_set_procparam(image+procparam);\n',
     '        runtime_set_procparam(image+procparam);\n        runtime_set_guest_image(image,size);\n'),
    ('        for (uint64_t m=0;m<module_count;++m) {\n'
     '            printf("Starting linked module %" PRIu64 " at image offset 0x%" PRIx64 "; native bindings=%" PRIu64 "\\n",m,modules[m].init,nb);',
     '        for (uint64_t m=0;m<module_count;++m) {\n'
     '            if (modules[m].init&DEFERRED_INIT) {\n'
     '                printf("Linked module %" PRIu64 " at image offset 0x%" PRIx64 ": start deferred until sceKernelLoadStartModule\\n",m,modules[m].base);\n'
     '                continue;\n'
     '            }\n'
     '            printf("Starting linked module %" PRIu64 " at image offset 0x%" PRIx64 "; native bindings=%" PRIu64 "\\n",m,modules[m].init,nb);'),
]

# ---------- runtime.h ----------
edits['hdr'] += [
    ('void runtime_set_procparam(void *param);',
     'void runtime_set_procparam(void *param);\n'
     '/* NHL 24: the guest image (deferred modules, call-site logging). */\n'
     'void runtime_set_guest_image(const unsigned char *base, uint64_t size);'),
]

# ---------- runtime_kernel.c ----------
KERNEL_FN = r'''/* NHL 24: game modules started at run time. link_modules.py links them at boot but defers their
 * start code and lists them, with their exports, in out/dynamic_modules.txt (BB_DYNAMIC_MODULES). */
static const unsigned char *guest_base;
static uint64_t guest_size;
void runtime_set_guest_image(const unsigned char *base, uint64_t size) { guest_base=base; guest_size=size; }
typedef struct { char nid[12]; uint64_t offset; } DynExport;
typedef struct { char file[96]; uint64_t init, base, size; DynExport *exports; size_t count, cap; int started; } DynModule;
static DynModule dyn_modules[16];
static int dyn_count, dyn_loaded;
static atomic_flag dyn_lock=ATOMIC_FLAG_INIT;
static void dyn_load_list(void) {
    if (dyn_loaded) return;
    dyn_loaded=1;
    const char *path=getenv("BB_DYNAMIC_MODULES");
    FILE *f=path ? fopen(path,"r") : NULL;
    if (!f) { printf("Runtime: no deferred module list (BB_DYNAMIC_MODULES)\n"); return; }
    char line[256];
    while (fgets(line,sizeof line,f)) {
        char a[96]; unsigned long long x=0,y=0,z=0;
        if (sscanf(line,"module %95s %llx %llx %llx",a,&x,&y,&z)==4 && dyn_count<16) {
            DynModule *d=&dyn_modules[dyn_count++];
            snprintf(d->file,sizeof d->file,"%s",a); d->init=x&~(UINT64_C(1)<<62); d->base=y; d->size=z;
        } else if (sscanf(line,"export %11s %llx",a,&x)==2 && dyn_count) {
            DynModule *d=&dyn_modules[dyn_count-1];
            if (d->count==d->cap) { d->cap=d->cap ? d->cap*2 : 64; d->exports=realloc(d->exports,d->cap*sizeof *d->exports); }
            snprintf(d->exports[d->count].nid,sizeof d->exports[0].nid,"%s",a); d->exports[d->count++].offset=x;
        }
    }
    fclose(f);
    for (int i=0;i<dyn_count;++i) printf("Runtime: deferred module %s (%zu exports)\n",dyn_modules[i].file,dyn_modules[i].count);
}
/* NIDs: the first 8 bytes of SHA-1(name + salt), reversed, in base64 with '-' for '/'. */
static void sha1_block(uint32_t h[5], const unsigned char *p) {
    uint32_t w[80];
    for (int i=0;i<16;++i) w[i]=(uint32_t)p[4*i]<<24|(uint32_t)p[4*i+1]<<16|(uint32_t)p[4*i+2]<<8|p[4*i+3];
    for (int i=16;i<80;++i) { uint32_t t=w[i-3]^w[i-8]^w[i-14]^w[i-16]; w[i]=t<<1|t>>31; }
    uint32_t a=h[0],b=h[1],c=h[2],d=h[3],e=h[4];
    for (int i=0;i<80;++i) {
        uint32_t f,k;
        if (i<20) { f=(b&c)|(~b&d); k=0x5A827999; } else if (i<40) { f=b^c^d; k=0x6ED9EBA1; }
        else if (i<60) { f=(b&c)|(b&d)|(c&d); k=0x8F1BBCDC; } else { f=b^c^d; k=0xCA62C1D6; }
        uint32_t t=(a<<5|a>>27)+f+e+k+w[i]; e=d; d=c; c=b<<30|b>>2; b=a; a=t;
    }
    h[0]+=a; h[1]+=b; h[2]+=c; h[3]+=d; h[4]+=e;
}
static void name_nid(const char *name, char out[12]) {
    static const unsigned char salt[16]={0x51,0x8d,0x64,0xa6,0x35,0xde,0xd8,0xc1,0xe6,0xb0,0x39,0xb1,0xc3,0xe5,0x52,0x30};
    size_t n=strlen(name), total=n+16;
    uint32_t h[5]={0x67452301,0xEFCDAB89,0x98BADCFE,0x10325476,0xC3D2E1F0};
    unsigned char block[64]; size_t fill=0;
    for (size_t i=0;i<total;++i) {
        block[fill++]= i<n ? (unsigned char)name[i] : salt[i-n];
        if (fill==64) { sha1_block(h,block); fill=0; }
    }
    block[fill++]=0x80;
    if (fill>56) { memset(block+fill,0,64-fill); sha1_block(h,block); fill=0; }
    memset(block+fill,0,56-fill);
    uint64_t bits=(uint64_t)total*8;
    for (int i=0;i<8;++i) block[56+i]=(unsigned char)(bits>>(56-8*i));
    sha1_block(h,block);
    unsigned char d[8];
    for (int i=0;i<8;++i) d[7-i]=(unsigned char)(h[i/4]>>(24-8*(i%4)));   /* first 8 bytes, reversed */
    static const char b64[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-";
    int o=0;
    for (int i=0;i<8;i+=3) {
        uint32_t v=(uint32_t)d[i]<<16 | (i+1<8 ? (uint32_t)d[i+1]<<8 : 0) | (i+2<8 ? d[i+2] : 0);
        out[o++]=b64[v>>18&63]; out[o++]=b64[v>>12&63];
        if (i+1<8) out[o++]=b64[v>>6&63];
        if (i+2<8) out[o++]=b64[v&63];
    }
    out[o]=0;
}
#define DYN_HANDLE_BASE 0x100
'''
LOAD_OLD = '''static ABI int32_t load_start_module(const char *path,uint64_t argc,const void *argv,uint32_t flags,const void *opt,int32_t *result) {
    (void)argc; (void)argv; (void)flags; (void)opt; if (result) *result=0;
    printf("Runtime: sceKernelLoadStartModule(%s) -> not found (modules are linked offline)\\n",path ? path : "(null)");
    return (int32_t)0x80020002; /* ENOENT */
}'''
LOAD_NEW = '''static ABI int32_t load_start_module(const char *path,uint64_t argc,const void *argv,uint32_t flags,const void *opt,int32_t *result) {
    (void)flags; (void)opt; if (result) *result=0;
    const char *file=path ? strrchr(path,'/') : NULL;
    file=file ? file+1 : path;
    while (atomic_flag_test_and_set(&dyn_lock)) sched_yield();
    dyn_load_list();
    int index=-1;
    for (int i=0;file && i<dyn_count;++i) if (!strcasecmp(dyn_modules[i].file,file)) index=i;
    if (index<0) {
        atomic_flag_clear(&dyn_lock);
        printf("Runtime: sceKernelLoadStartModule(%s) -> not found (modules are linked offline)\\n",path ? path : "(null)");
        return (int32_t)0x80020002; /* ENOENT */
    }
    DynModule *d=&dyn_modules[index];
    int start=!d->started;
    d->started=1;
    atomic_flag_clear(&dyn_lock);
    if (start && guest_base) {
        printf("Runtime: sceKernelLoadStartModule(%s): starting the deferred module at +0x%llx\\n",path,(unsigned long long)d->init);
        typedef int (ABI *ModuleStart)(uint64_t,const void *,void *);
        int r=((ModuleStart)(guest_base+d->init))(argc,argv,NULL);
        printf("Runtime: %s start returned %d\\n",d->file,r);
        if (result) *result=r;
    }
    return DYN_HANDLE_BASE+index;
}
static ABI int32_t kernel_dlsym(int32_t handle,const char *symbol,void **address) {
    if (!symbol || !address) return (int32_t)0x80020016; /* EINVAL */
    int index=handle-DYN_HANDLE_BASE;
    if (index<0 || index>=dyn_count || !guest_base) {
        printf("Runtime: sceKernelDlsym(%d, %s) -> no such module\\n",handle,symbol);
        return (int32_t)0x80020003; /* ESRCH */
    }
    char nid[12]; name_nid(symbol,nid);
    DynModule *d=&dyn_modules[index];
    for (size_t i=0;i<d->count;++i) if (!strcmp(d->exports[i].nid,nid)) {
        *address=(void *)(guest_base+d->exports[i].offset);
        printf("Runtime: sceKernelDlsym(%s, %s) -> +0x%llx\\n",d->file,symbol,(unsigned long long)d->exports[i].offset);
        return 0;
    }
    printf("Runtime: sceKernelDlsym(%s, %s [%s]) -> not exported\\n",d->file,symbol,nid);
    return (int32_t)0x80020002; /* ENOENT */
}'''
edits['kernel'] += [
    (LOAD_OLD, KERNEL_FN + LOAD_NEW),
    ('{"sceKernelLoadStartModule",load_start_module},', '{"sceKernelLoadStartModule",load_start_module}, {"sceKernelDlsym",kernel_dlsym},'),
    ('    const uintptr_t text_lo=0x800000000ull, text_hi=0x800000000ull+0x50d96dcull;',
     '    /* The guest image range (NHL 24: it assumed UFC 3\'s code size). */\n'
     '    const uintptr_t text_lo=guest_base ? (uintptr_t)guest_base : 0x800000000ull,\n'
     '                    text_hi=guest_base ? (uintptr_t)guest_base+guest_size : 0x800000000ull+0x50d96dcull;'),
]

# ---------- game_check.py ----------
edits['check'] += [
    ("        modules=('libc.prx', 'libSceFios2.prx', 'libSceNpToolkit2.prx'), patches=False),",
     "        modules=('libc.prx', 'libSceFios2.prx', 'libSceNpToolkit2.prx',\n"
     "                 'Engine.Render.Core2.PlatformPs4.prx', 'Engine.BuildInfo.prx'), patches=False),"),
]
# ---------- run-msys2.sh ----------
edits['run'] += [
    ('patch_args=(); [[ -f $out/patches.bin ]] && patch_args=(--patches "$out/patches.bin")',
     'patch_args=(); [[ -f $out/patches.bin ]] && patch_args=(--patches "$out/patches.bin")\n'
     '# NHL 24: game modules the game starts itself (scripts/link_modules.py writes the list).\n'
     '[[ -f $out/dynamic_modules.txt ]] && export BB_DYNAMIC_MODULES="$PWD/$out/dynamic_modules.txt"'),
]

bad = []
for k, lst in edits.items():
    for old, _ in lst:
        if text[k].count(old) != 1:
            bad.append(f'{files[k]}: {old.splitlines()[0][:70]!r} (found {text[k].count(old)})')
if bad:
    sys.exit('not as expected (nothing changed):\n  ' + '\n  '.join(bad))
for k, lst in edits.items():
    for old, new in lst:
        text[k] = text[k].replace(old, new, 1)
    files[k].write_text(text[k], encoding='utf-8', newline='\n')
print('changed: ' + ', '.join(str(p) for p in files.values()))
print('Now prepare again: bash scripts/build-msys2.sh && bash scripts/run-msys2.sh nhl24  (without BB_SKIP_PREPARE)')
