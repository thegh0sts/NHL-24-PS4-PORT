#!/usr/bin/env python3
r"""NHL 24: offline sockets that can be created. Run once from the repo root, then rebuild:

    python3 apply_nhl24_offline_sockets.py
    bash scripts/build-msys2.sh && BB_SKIP_PREPARE=1 bash scripts/run-msys2.sh nhl24

EA's network library (DirtySDK) start-up, NetConnStartup (Ghidra FUN_022f1d30), creates its UPnP
module, which opens a UDP socket. Offline, the runtime refused every socket call ("network
unreachable"), so the UPnP module failed, NetConnStartup undid itself (return -7: NetConn and the
DirtyHttpCM state at DAT_0bdf4d40 left empty), and the next caller read the empty state: the
crash at guest offset 0x785d2c4 (Ghidra 0x885d2c4, MOVSXD R14,[RCX+0x18] with RCX = DAT_0bdf4d40).
A PS4 without a network still creates sockets; only sending and connecting fail.

src/runtime_services.c (offline mode; with BB_ONLINE_SERVER runtime_net.c is used instead)
    With offline sockets on: sceNetSocket returns a descriptor; bind, socket options, getsockname,
    shutdown, abort and close succeed; receive says "would block"; epoll control succeeds and
    epoll wait waits (at most 50 ms) and reports nothing. Connect, send and the resolver still
    fail as unreachable.
    On by default for the nhl24 profile only (BB_GAME_PROFILE); BB_OFFLINE_SOCKETS=1/0 forces it
    on or off for any game. NHL 19 and UFC 3 are unchanged.
"""
import sys
from pathlib import Path

p = Path('src/runtime_services.c')
if not p.exists():
    sys.exit('run this from the repo root (src/runtime_services.c not found)')
s = p.read_text(encoding='utf-8')
if 'offline_sockets' in s:
    sys.exit('already applied')

anchor = 'static ABI int32_t netctl_state(int32_t *state) {'
funcs = r'''/* NHL 24: offline sockets. EA's network start-up opens a UDP socket (UPnP) and gives up if it
 * cannot; a PS4 without a network still creates sockets, only connecting and sending fail.
 * On for the nhl24 profile; BB_OFFLINE_SOCKETS=1/0 forces it for any game. */
#define NET_EAGAIN ((int32_t)0x80410123)
static int offline_sockets(void) {
    static int on=-1;
    if (on<0) {
        const char *v=getenv("BB_OFFLINE_SOCKETS"), *profile=getenv("BB_GAME_PROFILE");
        on = v && *v ? *v!='0' : profile && !strcmp(profile,"nhl24");
        if (on) note("Net: offline sockets (created; nothing is sent or received)");
    }
    return on;
}
static ABI int32_t sock_create(const char *name,int family,int type,int protocol) {
    (void)family; (void)protocol;
    if (!offline_sockets()) return net_unreachable();
    int id=new_id();
    static int shown;
    if (shown++<8) printf("Runtime: Net: socket '%s' (type %d) -> %d (offline)\n",name ? name : "",type,id);
    return id;
}
static ABI int32_t sock_ok(void) { return offline_sockets() ? 0 : net_unreachable(); }
static ABI int32_t sock_getsockopt(int s,int level,int option,void *value,uint32_t *length) {
    (void)s; (void)level; (void)option;
    if (!offline_sockets()) return net_unreachable();
    if (value && length && *length) memset(value,0,*length);
    return 0;
}
static ABI int32_t sock_getsockname(int s,unsigned char *address,uint32_t *length) {
    (void)s;
    if (!offline_sockets()) return net_unreachable();
    if (address && length && *length>=16) { memset(address,0,16); address[0]=16; address[1]=2; *length=16; }
    return 0;
}
static ABI int32_t sock_recv(void) {
    if (!offline_sockets()) return net_unreachable();
    net_errno=35; return NET_EAGAIN;
}
static ABI int32_t sock_epoll_wait(int eid,void *events,int max,int timeout_us) {
    (void)eid; (void)events; (void)max;
    if (!offline_sockets()) return net_unreachable();
    const int64_t cap=50000;
    int64_t wait = timeout_us<0 || timeout_us>cap ? cap : timeout_us;
    if (wait>0) platform_sleep_ns((uint64_t)wait*1000);
    return 0;
}
'''
subs = [
    (anchor, funcs + anchor),
    ('{"sceNetSocket",net_unreachable}', '{"sceNetSocket",sock_create}'),
    ('{"sceNetBind",net_unreachable}', '{"sceNetBind",sock_ok}'),
    ('{"sceNetRecv",net_unreachable}', '{"sceNetRecv",sock_recv}'),
    ('{"sceNetRecvfrom",net_unreachable}', '{"sceNetRecvfrom",sock_recv}'),
    ('{"sceNetSetsockopt",net_unreachable}', '{"sceNetSetsockopt",sock_ok}'),
    ('{"sceNetGetsockopt",net_unreachable}', '{"sceNetGetsockopt",sock_getsockopt}'),
    ('{"sceNetGetsockname",net_unreachable}', '{"sceNetGetsockname",sock_getsockname}'),
    ('{"sceNetShutdown",net_unreachable}', '{"sceNetShutdown",sock_ok}'),
    ('{"sceNetSocketClose",net_unreachable}', '{"sceNetSocketClose",sock_ok}'),
    ('{"sceNetSocketAbort",net_unreachable}', '{"sceNetSocketAbort",sock_ok}'),
    ('{"sceNetEpollControl",net_unreachable}', '{"sceNetEpollControl",sock_ok}'),
    ('{"sceNetEpollWait",net_unreachable}', '{"sceNetEpollWait",sock_epoll_wait}'),
    ('{"sceNetEpollAbort",net_unreachable}', '{"sceNetEpollAbort",sock_ok}'),
]
missing = [old[:70] for old, _ in subs if s.count(old) != 1]
if missing:
    sys.exit('src/runtime_services.c was not as expected (nothing changed); not found:\n  ' + '\n  '.join(missing))
for old, new in subs:
    s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8', newline='\n')
print('changed: src/runtime_services.c (offline sockets for nhl24; BB_OFFLINE_SOCKETS=1/0 to force)')
