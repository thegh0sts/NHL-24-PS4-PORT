# NHL 24 PS4 port: handoff notes (2026-11-15)

Repo: `C:\Users\kshla\source\repos\NHL-24-PS4-PORT`, built from the NHL 19 port (the last run's
version string: `0.1.0-12-g01d7b14-dirty`). The README is still NHL 19's. Not touched since
2026-11-10. These notes were written from the repo's files and its last run log; the earlier
chat that did the work isn't available.

Rules: only my own dump; never commit or publish game files or anything made from them
(`nhl24\`, `out\`, `user\`, `boot-linked.bin`; `.gitignore` already has `/nhl24/`, `out/`,
`user/`). Commits use `17183580+thegh0sts@users.noreply.github.com`.

## The game
- Dump in `nhl24\`: **CUSA37933** (US), content ID `UP0006-CUSA37933_00-NHLPS4HOCKEY2024`,
  version **1.60** (update in `nhl24\Patch`), profile name `nhl24`.
- **Frostbite** engine (the earlier ports are Ignite), SDK 10.50. The renderer is a module of its
  own in the game folder: `Engine.Render.Core2.PlatformPs4.prx`, plus `Engine.BuildInfo.prx`.
  Both are linked at start-up and their start is deferred until the game calls
  sceKernelLoadStartModule (`out\dynamic_modules.txt` lists their exports).

## Status (last run, 2026-11-10)
Boots, loads the renderer modules, and plays in game: about **31 FPS**, 445 draws per frame,
ended by closing the window (no crash). Known open item: **visual glitches** (not described in
the repo; look at a run first).

## What was done (one-off patch scripts in the repo root, already applied)
Each `apply_nhl24_*.py` patched the source once; its docstring explains the problem.
- Memory: `sceKernelMapDirectMemory2` (mapdirect2), process memory parameters / flexible memory
  size (memparam, memlog), thousands of small direct-memory blocks (dmem_blocks), address hints at
  the top of the range (findfree), MAP_FIXED re-reservation (reserve_fixed), the fixed GPU mapping
  at 0x7F0000000 (sysmap), 3D audio (audio3d).
- Start-up: command line arguments (getargv), add-on content (addcont_fp), missing system
  functions (batch1-3), deferred module start (dynmodules, fix_probe_deferred).
- Network: sockets that exist offline but fail to send/connect, for EA's DirtySDK
  (offline_sockets).
- Crashes: the red zone fix (redzone: PS4 code using the 128 bytes below rsp; now standard in the
  later ports, "Red zone (BB_REDZONE_SHIFT)"), with faultnote for diagnosis.
- GPU: per-mip barriers assertion after PLAY NOW (barriers), the 1920x1080 depth buffer used with
  and without stencil (depthcopy).
- `out\missing_imports.txt` (older) listed libSceJson2, a few POSIX socket functions and
  sceKernelDlsym as not yet implemented; check whether the game still reaches them.

## Useful from the other ports (2026-11-15, Madden NFL 17 repo)
- A full `sce::Json` (`src/runtime_json2.c`) and POSIX accept/bind/connect/listen/send/shutdown.
- Texture cache fixes: several-level subresource views, small 1D-tiled mips of 2D-tiled images,
  and re-linking a stencil to its recreated depth-stencil buffer (`texture_cache.h`). These may
  help NHL 24's glitches.
- Diagnostics: `BB_DISPATCH_LOG`, `BB_OVERLAP_LOG`, `BB_SAMPLER_LOG`, `BB_CAPTURE_ON_FLIP` with
  `BB_CAPTURE_TRIGGER`, `BB_FRAME_STATS=1 BB_FRAME_LOG=out/frames.csv`.

## Next steps
1. Run it (`bash scripts/build-msys2.sh`, then `bash scripts/run-msys2.sh`) and describe the
   glitches with a screenshot or a short video.
2. Move the applied `apply_nhl24_*.py` scripts out of the repo root (e.g. `tools/history/`) or
   delete them; their changes are in the source.
3. Rewrite the README for NHL 24, then set up the GitHub repo as for the other ports.

## To fix later
- **Save warning when starting a tournament** (seen 2026-11-18): the game shows a save warning
  as a tournament starts. Not looked into yet; check the save data handling
  (`src/runtime_savedata.c`) and the `out/run.txt` lines around it.

## Graphics work, 2026-11-15 to 2026-11-18 (not yet compiled when written)
Each change is marked `nhl24`/`bbport` in the source and has an env switch to undo it.

Fixed: team-select background/lighting flicker (ReleaseMem fence writes through the backing,
`BB_RELEASE_MEM_BACKING=0` undoes; CMASK/HTILE metadata refcount, `BB_META_ERASE=1` undoes).
Player body edges improved.

Ported from HajDEO's nhl24pc (GPL-2.0) on 2026-11-18:
- Read faults download only the faulting pages while GPU writes are in flight. **Off by default**
  (`BB_READBACK_READ_WINDOW=0` turns it on): it caused one-frame dimming in team select.
- CMASK fill 0 while fast-cleared, else 0xFFFFFFFF. **Off by default** (`BB_CMASK_FULL=0` turns it
  on): also caused one-frame dimming; edges are clean without it.
- Skip small CPU-side invalidations of GPU-modified targets (`BB_GPU_INVAL_SMALL=1` restores).
- Depth alias copy only for texture/storage bindings (`BB_DEPTH_ALIAS_COPY=1` restores).
- Merged left-overlap target copy when the cached image is GPU-modified.
- Unresolvable equal-address overlap logged and recovered instead of UNREACHABLE (their PR #7).
- GetSrc16 handles VccHi/M0/Scc/ExecLo/ExecHi.
- Vertex kill emulation via CullDistance (`BB_VTX_KILL=0` disables; shader variant bit 0x80).
- Split-wave LDS barriers (`BB_SPLIT_WAVE_BARRIERS`, bit 0x20) and wave64 loop lowering (bit 0x40).
- Jump-table expansion for `S_SETPC_B64 without a resolvable offset` (Be a Pro / Create a Team).
- Also: DRS resize (`BB_DRS_RESIZE`), R8 depth store barrier (`BB_DEPTH_STORE_BARRIER=0`),
  16-bit storage feature, flat GPU clock by flip number.

Ported later on 2026-11-18: R6 (a texel buffer starting inside an image no longer hits an
ASSERT: the whole image is synced at its own address) and R10 (image bindings split by
colour/depth compare; shader cache version 12 -> 13, so shaders recompile once). Already
present before: the replay-compression patch (`patches/nhl24.xml`), the GC deletion counting.
Not ported: their stale-alias GC (ours has its own), presenter fence race (different presenter),
WRITE_DATA via backing (needs texture-cache invalidation), perf/diag-only changes.

Fixed 2026-11-18: player/helmet edge flicker. Confirmed by switching each off (both brought it
back): **vertex kill emulation** (`BB_VTX_KILL`, culled triangles were drawn as slivers, also in
shadow passes) and **depth alias copy only for texture bindings** (`BB_DEPTH_ALIAS_COPY`, the old
copy overwrote fresh depth; also the load-in flicker). Keep both on. Open: DRS still drops below 1080p, single blank
blue frames at faceoff, readback stalls (~5.4 ms/frame). The stall is
a real dependency, not wasted work: `out/readbacks.csv` (2026-11-18, 289 s) shows ~120 waits/s, each
on the same 4 KiB page as a GPU write recorded in the batch that has not been submitted yet (20-byte
records every 32 bytes, like indirect draw args written by a compute pass). The game reads results
the GPU has just produced, so it must wait. The narrowed read window gave the same 172 ms/s.
Tournament saves work (`Tournament0` written, 456 KB); the warning's text is still unknown.

Diagnostics: `BB_CAPTURE_ON_FLIP=1 BB_CAPTURE_FLIPS=2`, `BB_IMAGE_WATCH=addr`,
`BB_IMAGE_SYNC_LOG=1`, `BB_READBACK_LOG=path`, `BB_TOGGLE_FILE`.

Warning: twice, edited files on this PC reverted to older copies minutes after being written.
After pulling or building, check that the sizes/dates of changed files are still new.
