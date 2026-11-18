#!/usr/bin/env python3
r"""NHL 24, batch 3: the remaining PSN, 3D-audio, video-decoder and dialog functions on the missing
list, answered the way a PS4 that is offline (or lacks the feature) answers. Run once from the
repo root, then rebuild:

    python3 apply_nhl24_batch3.py
    bash scripts/build-msys2.sh

All in src/runtime_services.c:
  * PSN services (TUS cloud data, Score leaderboards, Matching2 rooms, Party, in-game messages,
    word filter, bandwidth test, NpAuth, account language): "signed out" (0x80550006) for
    requests; OK for delete / abort / terminate / unregister; memory statistics answer zeros.
  * Trophies: GetTrophyUnlockState from the local trophies (trophies.json), ShowTrophyList,
    CaptureScreenshot and AbortHandle OK, the icon calls "no icon".
  * 3D audio: PortGetAttributesSupported and BedWrite "not supported", like the rest of
    sceAudio3d here (the game keeps ordinary audio output).
  * Video decoder (sceVideodec2): "not supported" until a decoder is added; the game's movies
    should be skipped rather than played.
  * Sign-in dialog: opens and finishes at once as cancelled (no PSN sign-in here).
  * HTTP/SSL/Net: connections and requests fail as without network, memory statistics zeros.
  * AudioIn silent-state / shared-device: 0. sceRtcParseDateTime: invalid value.
  * libSceDiscMap 7C980FFB0AA27E7A (NID fJgP+wqifno, no name): as its 8A828CAEE7EDD5E9 twin.
The JSON (libSceJson2) and POSIX socket functions are left for when the game reaches them.
"""
import sys
from pathlib import Path

p = Path('src/runtime_services.c')
if not p.exists():
    sys.exit('run this from the repo root (src/runtime_services.c not found)')
s = p.read_text(encoding='utf-8')
if 'videodec2_unsupported' in s:
    sys.exit('already applied')

NP = '''sceNpTssCreateNpTitleCtxA sceNpTssGetData sceNpTusAddAndGetVariableA sceNpTusAddAndGetVariableAVUser
sceNpTusAddAndGetVariableForCrossSave sceNpTusAddAndGetVariableForCrossSaveVUser sceNpTusCreateNpTitleCtxA
sceNpTusCreateRequest sceNpTusGetDataA sceNpTusGetDataAVUser sceNpTusGetDataForCrossSave sceNpTusGetDataForCrossSaveVUser
sceNpTusGetFriendsDataStatusA sceNpTusGetFriendsDataStatusForCrossSave sceNpTusGetFriendsVariableA
sceNpTusGetFriendsVariableForCrossSave sceNpTusGetMultiSlotVariableA sceNpTusGetMultiSlotVariableAVUser
sceNpTusGetMultiSlotVariableForCrossSave sceNpTusGetMultiSlotVariableForCrossSaveVUser sceNpTusGetMultiUserDataStatusA
sceNpTusGetMultiUserDataStatusAVUser sceNpTusGetMultiUserDataStatusForCrossSave sceNpTusGetMultiUserDataStatusForCrossSaveVUser
sceNpTusGetMultiUserVariableA sceNpTusGetMultiUserVariableAVUser sceNpTusGetMultiUserVariableForCrossSave
sceNpTusGetMultiUserVariableForCrossSaveVUser sceNpTusSetDataA sceNpTusSetDataAVUser sceNpTusSetMultiSlotVariableA
sceNpTusSetMultiSlotVariableVUser sceNpTusTryAndSetVariableA sceNpTusTryAndSetVariableAVUser
sceNpTusTryAndSetVariableForCrossSave sceNpTusTryAndSetVariableForCrossSaveVUser
sceNpMatching2CreateContextA sceNpMatching2CreateJoinRoomA sceNpMatching2GetRoomDataExternalList
sceNpMatching2GetRoomDataInternal sceNpMatching2GetRoomMemberDataInternal sceNpMatching2GetRoomMemberIdListLocal
sceNpMatching2GetRoomPasswordLocal sceNpMatching2GetSignalingOptParamLocal sceNpMatching2GetUserInfoListA
sceNpMatching2JoinRoomA sceNpMatching2SendRoomChatMessage sceNpMatching2SendRoomMessage
sceNpMatching2SetSignalingOptParam sceNpMatching2SetUserInfo sceNpMatching2SignalingGetConnectionInfoA
sceNpBandwidthTestInitStart sceNpBandwidthTestGetStatus sceNpWordFilterCreateRequest sceNpWordFilterCreateTitleCtxA
sceNpWordFilterSanitizeComment sceNpScoreCreateNpTitleCtxA sceNpScoreGetFriendsRankingA
sceNpScoreGetFriendsRankingForCrossSave sceNpScoreGetGameDataByAccountId sceNpScoreGetRankingByAccountId
sceNpScoreGetRankingByAccountIdForCrossSave sceNpScoreGetRankingByAccountIdPcId
sceNpScoreGetRankingByAccountIdPcIdForCrossSave sceNpScoreGetRankingByRangeA sceNpScoreGetRankingByRangeForCrossSave
sceNpGetAccountLanguageA sceNpInGameMessageCreateHandle sceNpInGameMessageInitialize sceNpInGameMessagePrepareA
sceNpInGameMessageSendDataA sceNpPartyInitialize sceNpPartyRegisterHandlerA sceNpPartyRegisterPrivateHandler
sceNpAuthCreateRequest'''.split()
OK = '''sceNpTusAbortRequest sceNpTusDeleteMultiSlotDataA sceNpTusDeleteMultiSlotDataVUser sceNpTusDeleteNpTitleCtx
sceNpTusDeleteRequest sceNpMatching2RegisterRoomMessageCallback sceNpBandwidthTestAbort sceNpBandwidthTestShutdown
sceNpWordFilterAbortRequest sceNpWordFilterDeleteRequest sceNpWordFilterDeleteTitleCtx sceNpInGameMessageDeleteHandle
sceNpInGameMessageTerminate sceNpPartyCheckCallback sceNpPartyTerminate sceNpPartyUnregisterPrivateHandler
sceNpTrophyAbortHandle sceNpTrophyCaptureScreenshot sceNpTrophyShowTrophyList sceSigninDialogInitialize
sceSigninDialogOpen sceSigninDialogTerminate sceNpWebApiAddHttpRequestHeader sceVideodec2Flush sceVideodec2Reset
sceVideodec2DeleteDecoder sceVideodec2ReleaseComputeQueue'''.split()
STATS2 = 'sceHttpGetMemoryPoolStats sceSslGetMemoryPoolStats sceNetGetMemoryPoolStats sceNpWebApiGetMemoryPoolStats sceNpInGameMessageGetMemoryPoolStatistics'.split()
STATS1 = 'sceNpMatching2GetMemoryInfo sceNpMatching2GetSslMemoryInfo'.split()
VIDEO = 'sceVideodec2QueryDecoderMemoryInfo sceVideodec2QueryComputeMemoryInfo sceVideodec2AllocateComputeQueue sceVideodec2CreateDecoder sceVideodec2Decode'.split()
OTHER = [('sceNpTrophyGetGameIcon', 'trophy_no_icon'), ('sceNpTrophyGetGroupIcon', 'trophy_no_icon'),
         ('sceNpTrophyGetTrophyIcon', 'trophy_no_icon'), ('sceNpTrophyGetTrophyUnlockState', 'trophy_unlock_state'),
         ('sceAudio3dPortGetAttributesSupported', 'audio3d_unsupported'), ('sceAudio3dBedWrite', 'audio3d_unsupported'),
         ('sceSigninDialogUpdateStatus', 'signin_status'), ('sceSigninDialogGetResult', 'signin_result'),
         ('sceHttpCreateConnection', 'http_fail'), ('sceHttpCreateRequest2', 'http_fail'), ('sceSslGetPem', 'http_fail'),
         ('sceAudioInGetSilentState', 'zero_int'), ('sceAudioInIsSharedDevice', 'zero_int'),
         ('sceRtcParseDateTime', 'rtc_parse_invalid')]

present = [n for n in NP + OK + STATS2 + STATS1 + VIDEO + [o[0] for o in OTHER] if f'"{n}"' in s]
names = [n for n in NP + OK + STATS2 + STATS1 + VIDEO + [o[0] for o in OTHER] if n not in present]

FN = r'''/* NHL 24, batch 3: PSN and other services answered as an offline PS4 (see apply_nhl24_batch3.py);
 * np_signed_out and ok_void are the runtime's own. */
#define VIDEODEC2_NOT_SUPPORTED ((int32_t)0x811D0104)
#define TROPHY_NO_ICON ((int32_t)0x80551609)
#define RTC_INVALID_VALUE ((int32_t)0x80B50002)
static ABI int32_t videodec2_unsupported(void) { return VIDEODEC2_NOT_SUPPORTED; }
static ABI int32_t zero_int(void) { return 0; }
static ABI int32_t rtc_parse_invalid(void) { return RTC_INVALID_VALUE; }
/* Memory-pool statistics {pool size, max in use, current in use, reserved}: all zero. */
static ABI int32_t pool_stats_second(int32_t id, void *stats) { (void)id; if (stats) memset(stats,0,32); return 0; }
static ABI int32_t pool_stats_first(void *info) { if (info) memset(info,0,40); return 0; }
static ABI int32_t trophy_no_icon(void) { return TROPHY_NO_ICON; }
/* OrbisNpTrophyFlagArray: 128 bits; *count: the game's trophies (the ids with details). */
static ABI int32_t trophy_unlock_state(int32_t ctx, int32_t handle, uint32_t *flags, uint32_t *count) {
    (void)ctx; (void)handle;
    if (!flags || !count) return TROPHY_INVALID;
    memset(flags,0,TROPHY_MAX/8);
    uint32_t n=0;
    for (int id=0; id<TROPHY_MAX; ++id) {
        if (runtime_trophy_info(id,NULL,NULL)) continue;
        n=(uint32_t)id+1;
        if (runtime_trophy_is_unlocked(id)) flags[id/32]|=UINT32_C(1)<<(id%32);
    }
    *count=n;
    return 0;
}
/* Sign-in dialog: finished at once (status 3), result "cancelled" (1). */
static ABI int32_t signin_status(void) { return 3; }
static ABI int32_t signin_result(int32_t *result) { if (result) { memset(result,0,32); result[0]=1; } return 0; }
'''
entries = []
for n in names:
    if n in NP: fn = 'np_signed_out'
    elif n in OK: fn = 'ok_void'
    elif n in STATS2: fn = 'pool_stats_second'
    elif n in STATS1: fn = 'pool_stats_first'
    elif n in VIDEO: fn = 'videodec2_unsupported'
    else: fn = dict(OTHER)[n]
    entries.append(f'{{"{n}",{fn}}},')
TAB = ''
for i in range(0, len(entries), 3):
    TAB += '    ' + ' '.join(entries[i:i + 3]) + '\n'

fn_anchor = 'static const RuntimeExport exports[]={'
tab_anchor = '    {"sceAudio3dInitialize",audio3d_unsupported},'
res_old = 'uintptr_t runtime_services_resolve(const char *name) { return RUNTIME_LOOKUP(exports,name); }'
res_new = ('uintptr_t runtime_services_resolve(const char *name) {\n'
           '    /* NHL 24: libSceDiscMap 7C980FFB0AA27E7A has no name in the import list; as its 8A82 twin. */\n'
           '    if (runtime_nid_equals(name,"fJgP+wqifno")) return (uintptr_t)discmap_8a82;\n'
           '    return RUNTIME_LOOKUP(exports,name);\n'
           '}')
for a in (fn_anchor, tab_anchor, res_old):
    if s.count(a) != 1:
        sys.exit(f'src/runtime_services.c: {a[:60]!r} was not found as expected (nothing changed)')
if '#include "runtime_trophy.h"' not in s:
    sys.exit('src/runtime_services.c: runtime_trophy.h is not included (nothing changed)')
s = s.replace(fn_anchor, FN + '\n' + fn_anchor, 1)
s = s.replace(tab_anchor, TAB + tab_anchor, 1)
s = s.replace(res_old, res_new, 1)
p.write_text(s, encoding='utf-8', newline='\n')
print(f'changed: src/runtime_services.c ({len(entries)} functions added' +
      (f'; {len(present)} already present: {", ".join(present)}' if present else '') + ')')
