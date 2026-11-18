#!/usr/bin/env python3
r"""NHL 24, batch 2: asynchronous file reads (Frostbite's streaming), writev, and the POSIX names
of the read/write locks. Run once from the repo root, then rebuild:

    python3 apply_nhl24_batch2.py
    bash scripts/build-msys2.sh

src/runtime_file.c
  sceKernelAioInitializeImpl, sceKernelAioInitializeParam (the SDK's default scheduling values),
  sceKernelAioSubmitReadCommands / SubmitWriteCommands, PollRequest, WaitRequests,
  CancelRequest, DeleteRequest, DeleteRequests.
  The PS4 runs AIO requests in the background; here each submitted request is carried out at once
  with the runtime's own pread/pwrite (paths, mounts and error codes as sceKernelPread), its result
  written, and its state set to completed, so every poll or wait finds it done. Simple and safe;
  loading may be a little slower than with real background reads.
  sceKernelWritev: the buffers written one after another.
src/runtime_rwlock.c
  pthread_rwlock_rdlock / wrlock / unlock (libkernel's POSIX names): the runtime's rwlocks with
  POSIX return values (0 or an errno number instead of an Orbis error code).
src/runtime_kernel.c
  pthread_equal.
Each part is applied only if its file still has the expected anchor; nothing changes otherwise.
"""
import sys
from pathlib import Path

FILE_FN = r'''/* NHL 24: libkernel AIO, carried out synchronously at submit (see apply_nhl24_batch2.py). */
typedef struct { int64_t value; uint32_t state; } AioResult;
typedef struct { int64_t offset; int64_t nbyte; void *buffer; AioResult *result; int32_t fd; } AioRequest;
typedef struct { int32_t window, delayed_limit; uint32_t split, split_size, chunk_size; } AioScheduling;
enum { AIO_COMPLETED=3 };
static int32_t aio_last_id;
static ABI int32_t aio_initialize_impl(void *param, int32_t size) { (void)param; (void)size; return 0; }
static ABI int32_t aio_initialize_param(AioScheduling *param) {
    if (!param) return ERR(22);
    for (int i=0; i<3; ++i) param[i]=(AioScheduling){0x20,0x20,1,0x100000,0x100000};
    return 0;
}
static int32_t aio_submit(AioRequest *requests, int32_t count, int32_t *id, int write) {
    if (!requests || count<=0 || !id) return ERR(22);
    for (int32_t i=0; i<count; ++i) {
        AioRequest *r=&requests[i];
        int64_t n=write ? do_pwrite(r->fd,r->buffer,(uint64_t)r->nbyte,r->offset)
                        : do_pread(r->fd,r->buffer,(uint64_t)r->nbyte,r->offset);
        if (r->result) { r->result->value=sce(n); r->result->state=AIO_COMPLETED; }
    }
    *id=__atomic_add_fetch(&aio_last_id,1,__ATOMIC_RELAXED);
    return 0;
}
static ABI int32_t aio_submit_read(AioRequest *requests, int32_t count, int32_t priority, int32_t *id) {
    (void)priority; return aio_submit(requests,count,id,0);
}
static ABI int32_t aio_submit_write(AioRequest *requests, int32_t count, int32_t priority, int32_t *id) {
    (void)priority; return aio_submit(requests,count,id,1);
}
static ABI int32_t aio_poll(int32_t id, int32_t *state) { (void)id; if (state) *state=AIO_COMPLETED; return 0; }
static ABI int32_t aio_cancel(int32_t id, int32_t *state) { (void)id; if (state) *state=AIO_COMPLETED; return 0; }
static ABI int32_t aio_delete(int32_t id, int32_t *result) { (void)id; if (result) *result=0; return 0; }
static ABI int32_t aio_delete_many(const int32_t *ids, int32_t count, int32_t *results) {
    (void)ids; if (results) for (int32_t i=0; i<count; ++i) results[i]=0;
    return 0;
}
static ABI int32_t aio_wait_many(const int32_t *ids, int32_t count, int32_t *states, uint32_t mode, uint32_t *usec) {
    (void)ids; (void)mode; (void)usec;
    if (states) for (int32_t i=0; i<count; ++i) states[i]=AIO_COMPLETED;
    return 0;
}
typedef struct { const void *base; uint64_t length; } GuestIovec;
static ABI int64_t sce_writev(int fd, const GuestIovec *iov, int32_t count) {
    if (count<0 || (count && !iov)) return ERR(22);
    int64_t total=0;
    for (int32_t i=0; i<count; ++i) {
        if (!iov[i].length) continue;
        int64_t n=do_write(fd,iov[i].base,iov[i].length);
        if (n<0) return total ? total : sce(n);
        total+=n;
        if ((uint64_t)n<iov[i].length) break;
    }
    return total;
}
'''
FILE_TAB = ('    {"sceKernelAioInitializeImpl",aio_initialize_impl}, {"sceKernelAioInitializeParam",aio_initialize_param},\n'
            '    {"sceKernelAioSubmitReadCommands",aio_submit_read}, {"sceKernelAioSubmitWriteCommands",aio_submit_write},\n'
            '    {"sceKernelAioPollRequest",aio_poll}, {"sceKernelAioCancelRequest",aio_cancel},\n'
            '    {"sceKernelAioDeleteRequest",aio_delete}, {"sceKernelAioDeleteRequests",aio_delete_many},\n'
            '    {"sceKernelAioWaitRequests",aio_wait_many}, {"sceKernelWritev",sce_writev},\n')

RW_FN = r'''/* NHL 24: libkernel's POSIX names for the rwlocks: 0 or an errno number (the low bits of the
 * Orbis error code) instead of the Orbis code. */
static int32_t posix_code(int32_t r) { return r ? (int32_t)((uint32_t)r & 0xFFFFu) : 0; }
static ABI int32_t posix_rw_read(Rwlock **r) { return posix_code(rw_read(r)); }
static ABI int32_t posix_rw_write(Rwlock **r) { return posix_code(rw_write(r)); }
static ABI int32_t posix_rw_unlock(Rwlock **r) { return posix_code(rw_unlock(r)); }
'''
RW_TAB = ('    if (runtime_nid_equals(name,"iGjsr1WAtI0")) return (uintptr_t)posix_rw_read;   /* pthread_rwlock_rdlock */\n'
          '    if (runtime_nid_equals(name,"sIlRvQqsN2Y")) return (uintptr_t)posix_rw_write;  /* pthread_rwlock_wrlock */\n'
          '    if (runtime_nid_equals(name,"EgmLo6EWgso")) return (uintptr_t)posix_rw_unlock; /* pthread_rwlock_unlock */\n')

KERNEL_FN = ('/* NHL 24: pthread_equal (thread handles are compared as they are). */\n'
             'static ABI int32_t posix_thread_equal(const void *a, const void *b) { return a==b; }\n')

edits = [
    ('src/runtime_file.c', 'sceKernelAioSubmitReadCommands',
     'static const RuntimeExport exports[]={', FILE_FN + '\n',
     '    {"sceKernelPread",sce_pread},', FILE_TAB + '    {"sceKernelPread",sce_pread},'),
    ('src/runtime_rwlock.c', 'posix_rw_read',
     'uintptr_t runtime_rwlock_resolve(const char *name) {', RW_FN,
     'uintptr_t runtime_rwlock_resolve(const char *name) {\n', 'uintptr_t runtime_rwlock_resolve(const char *name) {\n' + RW_TAB),
    ('src/runtime_kernel.c', 'posix_thread_equal',
     'static const RuntimeExport exports[]={', KERNEL_FN + '\n',
     '    {"sceKernelUsleep",kernel_usleep},', '    {"pthread_equal",posix_thread_equal},\n    {"sceKernelUsleep",kernel_usleep},'),
]

for name, *_ in edits:
    if not Path(name).exists():
        sys.exit(f'run this from the repo root ({name} not found)')
changed = 0
for name, marker, fn_anchor, fn, tab_anchor, tab in edits:
    p = Path(name)
    s = p.read_text(encoding='utf-8')
    if marker in s:
        print(f'{name}: already applied')
        continue
    if s.count(fn_anchor) != 1 or s.count(tab_anchor) != 1:
        print(f'{name}: anchors not found as expected, skipped (nothing changed in it)')
        continue
    if fn_anchor == tab_anchor.rstrip('\n'):
        s = s.replace(tab_anchor, fn + tab, 1)
    else:
        s = s.replace(fn_anchor, fn + fn_anchor, 1).replace(tab_anchor, tab, 1)
    p.write_text(s, encoding='utf-8', newline='\n')
    print(f'changed: {name}')
    changed += 1
print(f'{changed} file(s) changed')
