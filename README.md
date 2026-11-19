# NHL 24 PS4 Port for Windows

This project runs the **PS4 version** of *EA SPORTS NHL 24* natively on Windows. It isn't an emulator
running a whole console. It loads the game's own x86-64 code directly, gives it Windows versions of
the PS4 system libraries it calls, and translates its graphics to Vulkan.

It grew out of the [NHL 19 port](https://github.com/thegh0sts/NHL-19-PS4-PORT-WINDOWS), itself a fork
of [GNSB's UFC 3 port](https://github.com/GNSB/UFC-3-PS4-PORT-LINUX-WINDOWS). NHL 24 runs on EA's
**Frostbite** engine rather than Ignite, so it needed its own memory, start-up and graphics work on
top of them.

> [!IMPORTANT]
> This project contains **no game files**. You need your own PS4 copy of the game (**CUSA37933**,
> with update 1.60), dumped from your own console. Game files, and files made from them such as
> `boot-linked.bin`, must not be shared.

> [!WARNING]
> **This port is an early work in progress.** Expect bugs, crashes and missing features, and back up
> your saves often. If you hit a bug, please report it **with your saves** so it can be reproduced:
> see [Reporting problems](#reporting-problems).

<!-- Add a screenshot here, e.g. ![NHL 24 in game](docs/screenshot.png) -->

## Status

The game boots through the intro and menus, and Play Now matches play from the opening to the final
whistle. Tournaments start and save. Most other modes haven't been tested much yet.

| Area | State |
|---|---|
| Boot, intro videos, menus | Working |
| Play Now matches | Working |
| Tournaments | Working, saves included |
| Be a Pro, Create a Team | A crash on entering them is fixed in the source; not tested in game yet |
| Other modes (Franchise, HUT, World of CHEL offline...) | Not tested yet |
| Frame rate | About 60 FPS in play with `BB_FLIP_RATE=0` (the game asks for 30). The match opening runs lower, about 40 FPS |
| Resolution | The game lowers its resolution for some camera shots (the overhead face-off view, the match opening), as on a PS4 |
| Player graphics | Clean edges on players and helmets; team select doesn't flicker |
| Saves | Working: profile, settings and tournament saves |
| Controller | Working (one local player for now) |
| Online play | Not supported: the game starts offline and shows a no-connection notice (see [Online](#online)) |
| Trophies | Recorded locally |

Known problems:
- A mid-match freeze has been seen once, with no error in the log. If it happens to you, see
  [Reporting problems](#reporting-problems).
- The occasional single blank frame at a face-off.

Found a problem? See [Reporting problems](#reporting-problems).

## Features

- **Launcher** (`NHL24.exe`) that sets everything up and starts the game:
  - checks your game folder, and merges a base game and update dumped separately
  - links the game's renderer modules and applies its patches
  - game language, controller for player 1, player name
  - video: output 720p or 1080p, window or screen size, FSR 1.0 upscaling with sharpening, FPS
    limit, presentation mode (Immediate, Mailbox, FIFO), fullscreen, FPS counter
  - developer switches (frame statistics, Vulkan validation, shader cache, logs)
  - a Steam shortcut, and `--play` to start without the window
- **In-game overlay** (Insert, or L3+R3 on a controller) to change settings while you play
- NHL 24's settings applied for you: the PS4's floating-point mode, precise readbacks and 60 FPS

## Requirements

- Windows 10 or 11, 64-bit
- A CPU from Intel Haswell (4th generation Core) or newer, or any AMD Ryzen
- A GPU with Vulkan 1.3 support and an up-to-date driver (tested: NVIDIA RTX 4080 SUPER)
- Your PS4 dump of *NHL 24*: the base game and update **1.60**

### Supported version

| Serial | Region | Update | Status |
|---|---|---|---|
| **CUSA37933** | North America (UP0006) | 01.60 | Tested |

The port recognises the game by a fingerprint of its executable, so other regions or updates are
refused until they're added. Reports are welcome. You can find a dump's serial in its
`sce_sys\param.sfo` (`TITLE_ID`).

## Getting started

1. Download the latest release from the [Releases](../../releases) page and unzip it somewhere
   outside OneDrive-synced folders, for example `C:\Games\NHL24`.
2. Run `NHL24.exe`.
3. Choose your game folder: the one with `eboot.bin` in it. If the base game and the 1.60 update
   are separate folders side by side (`CUSA37933` and `CUSA37933-patch`), choose the base game:
   the launcher merges them once, with links that take no extra space.
4. Click **Play**. The first start prepares the files the loader needs from *your* game, which
   takes a little while; later starts are quicker.

The first matches also build the shader cache, so expect stutter and a lower frame rate the first
time you see each new scene, the match opening especially.

### Presentation modes

- **Immediate:** frames are shown as soon as they're ready. Lowest lag, but the image can tear.
  Pair it with a 60 FPS limit, or use it with G-Sync / FreeSync.
- **Mailbox:** no tearing and low lag. The GPU keeps drawing frames and only the newest is shown.
- **FIFO (VSync):** no tearing, follows the monitor's refresh. A little more lag.

### Where your files are

Settings, saves, the shader cache and logs live in `%LOCALAPPDATA%\NHL24Native` (paste that into
the Explorer address bar). Set `BB_DATA_DIR=.` before starting the launcher to keep everything
beside the program instead.

### Updating

Unzip the new release over the old one, or into a new folder. Your settings and saves stay in
`%LOCALAPPDATA%\NHL24Native`.

## Online

The port starts NHL 24 without a network, so the game plays offline and shows a no-connection
notice at start-up. The network mode used by the NHL 19 port (`BB_ONLINE_SERVER`) sends NHL 24 down
its PlayStation Network path, which the port doesn't support yet, so it's off for NHL 24.

## Release layout

```
NHL24\
  NHL24.exe             start here (the launcher)
  bin\                  sacredfire-game.exe (the loader), bb-gpu-capabilities.exe and their DLLs
  python\               embedded Python, used to prepare the game
  scripts\  tools\      the preparation scripts
  patches\              game patches (nhl24.xml)
  share\                shadPS4's import name list (aerolib.inl)
  licenses\             licences of the port and its components
  VERSION               the build's version
```

## Building from source

The port builds natively on Windows with [MSYS2](https://www.msys2.org/)'s **CLANG64** environment.

1. Install MSYS2, open the **MSYS2 CLANG64** shell and install the tools and libraries (press Enter
   at each group prompt to take all of it):
   ```sh
   pacman -S --needed git mingw-w64-clang-x86_64-{toolchain,cmake,ninja,pkgconf,python,glslang,vulkan-devel,vulkan-memory-allocator,fmt,boost,robin-map,xxhash,sdl3,zydis}
   ```
2. Clone and build:
   ```sh
   git clone --recursive https://github.com/thegh0sts/NHL-24-PS4-PORT.git
   cd NHL-24-PS4-PORT
   bash scripts/build-msys2.sh
   ```
   The first build also builds a few pinned libraries MSYS2 doesn't package (magic_enum, miniz,
   VulkanMemoryAllocator, robin-map, xbyak). Programs and their DLLs go to `out/windows/bin`; the
   build log is `out/windows/build-msys2.log`. `BB_LTO=ON` gives a slower build and a faster game.
3. Put your game dump in `nhl24\` inside the repo, with the 1.60 update merged in (the folder is in
   `.gitignore`, so it's never committed), then run it:
   ```sh
   BB_READBACKS=2 BB_FLIP_RATE=0 bash scripts/run-msys2.sh
   BB_SKIP_PREPARE=1 BB_READBACKS=2 BB_FLIP_RATE=0 bash scripts/run-msys2.sh   # later runs: skip the preparation
   ```
   The whole log goes to `out/run.txt` as well as the terminal. Saves and the shader cache go to
   the repo's `user\` folder, separate from the launcher's.

To make a release zip (`dist/NHL24-windows-x86_64.zip`):

```sh
BB_PRODUCT=NHL24 BB_LAUNCHER_EXE=NHL24.exe bash scripts/package-msys2.sh
```

The script refuses to package uncommitted changes (`BB_ALLOW_DIRTY=1` for a test zip) or any game
file. The first run downloads the embeddable Python and checks it against a pinned checksum.

### Versions and releases

The version comes from git: `git describe --tags`, so a build of the commit tagged `v0.1.0` is
version `v0.1.0`, and later commits read like `v0.1.0-3-g2abb064`. A `-dirty` ending means the build
had uncommitted changes. To make a release, tag the commit, build and package, then upload. With the
[GitHub CLI](https://cli.github.com/):

```sh
git tag v0.1.0 && git push --tags
bash scripts/build-msys2.sh && BB_PRODUCT=NHL24 BB_LAUNCHER_EXE=NHL24.exe bash scripts/package-msys2.sh
gh release create v0.1.0 dist/NHL24-windows-x86_64.zip --title "NHL 24 port v0.1.0" --notes "What's new..."
```

### Settings for testing

The launcher sets NHL 24's defaults. Any setting can be changed for one run by putting it in front
of the command, for example `BB_FLIP_RATE=-1 bash scripts/run-msys2.sh`, or with `set` in a `.bat`
before starting `NHL24.exe`.

| Variable | NHL 24 default (launcher) | Effect |
|---|---|---|
| `BB_DETERMINISTIC_FP` | 1 | The PS4's floating-point mode. Without it the GPU is lost at the first screens |
| `BB_READBACKS` | 2 | Reads of GPU-written memory. 2 (precise) gives the cleanest picture; pass it to `run-msys2.sh` yourself |
| `BB_FLIP_RATE` | 0 | 0: 60 FPS throughout. `-1`: the game's own choice (30 FPS in menus, as on a PS4) |
| `BB_ONLINE_SERVER` | unset | Leave unset for NHL 24 (see [Online](#online)) |
| `BB_FRAME_STATS=1` | off | Frame timing in the log |
| `BB_LOG_UNRESOLVED=1` | off | Logs every unhandled system call (very large logs) |

Graphics fixes made for NHL 24 each have a switch, so a problem can be traced to one of them. All
are on by default; these turn one off:

| Variable | Fix it turns off |
|---|---|
| `BB_VTX_KILL=0` | Triangles the game culls through its vertex shaders (without it: jagged, flickering player and helmet edges) |
| `BB_DEPTH_ALIAS_COPY=1` | Depth copied only to images that read it (without it: player lighting flicker) |
| `BB_RELEASE_MEM_BACKING=0` | GPU fence writes through the backing memory (without it: team-select background flicker) |
| `BB_META_ERASE=1` | Reference counts for colour and depth metadata (without it: background flicker) |
| `BB_GPU_INVAL_SMALL=1` | Small CPU writes over images the GPU has drawn are ignored |
| `BB_DEPTH_STORE_BARRIER=0` | A barrier after depth writes |

Diagnostics: `BB_CAPTURE_ON_FLIP=1 BB_CAPTURE_FLIPS=2` (capture frames to `out\frame_*.txt` with the
capture key), `BB_READBACK_LOG=<file>` (every readback, as CSV), `BB_IMAGE_WATCH=<address>`,
`BB_IMAGE_SYNC_LOG=1`.

`python3 tools/module_imports.py <module.prx>` lists what a game module needs from the system and
how much of it the port already provides.

## How it works

1. **Preparation** (`scripts/prepare.py`, `link_libc.py`, `link_modules.py`) reads the game's
   `eboot.bin` and links it with the PS4 libraries the game ships (`libc.prx`, `libSceFios2.prx`,
   `libSceNpToolkit2.prx`) and Frostbite's own modules (`Engine.Render.Core2.PlatformPs4.prx`,
   `Engine.BuildInfo.prx`) into one image, `boot-linked.bin`. The two Frostbite modules are started
   later, when the game asks for them. `game_check.py` identifies the game by a fingerprint of its
   executable, `gen_import_names.py` names the system functions it imports, and
   `content_profile.py` records its content details.
2. **The loader** (`sacredfire-game.exe`, `src/`) maps that image into memory and runs the game's
   code natively. Each call into a PS4 system library (kernel, memory, threads, files, saves, pads,
   audio, video output, network and so on) goes to a Windows implementation in `src/runtime_*.c`.
3. **Red zone:** PS4 code uses the 128 bytes below the stack pointer, which Windows doesn't keep
   safe. The loader moves those accesses so they can't be overwritten (`BB_REDZONE_SHIFT`).
4. **AMD-only instructions:** the PS4's CPU has AMD's SSE4a extension, which Intel CPUs lack. When
   the game uses one, the loader catches the error and carries out the instruction itself
   (`src/platform/sse4a.inc`).
5. **Graphics** go through a Vulkan backend based on [shadPS4](https://github.com/shadps4-emu/shadPS4)'s
   `video_core` (`gpu/`), which translates the game's GNM command buffers and shaders to Vulkan.
6. **Game patches** (`patches/nhl24.xml`): replay compression runs synchronously, which stops a
   freeze at the first face-off.

## Reporting problems

The port is at an early stage, and bug reports are the fastest way to get problems fixed. Open an
issue with:

- your CPU, GPU and driver version, and Windows version
- what happened, in which mode and where (menu, face-off, intermission...), and what you were doing
- the log of that session: the newest file in `%LOCALAPPDATA%\NHL24Native\logs\`, or `out/run.txt`
  when running from source. For freezes, turn on **Frame statistics** in the launcher first, and
  wait 30 to 60 seconds before closing a frozen game so the log can record why
- **your saves**, so the bug can be reproduced:
  1. Close the game.
  2. Open `%LOCALAPPDATA%\NHL24Native` in Explorer.
  3. Right-click the `user` folder → *Send to* → *Compressed (zipped) folder*. If it's large, the
     `cache` folder inside can be left out: it's only the shader cache.
  4. Attach the zip to the issue.

Please don't attach game files or anything from the `out` folder: they're made from the game and
can't be shared. Saves are fine to share: they hold only your progress and settings.

## Version history

### v0.1.0 (2026-11-19)

First test release.

**Game**
- Runs the PS4 version (CUSA37933, update 1.60) natively on Windows: intro, menus, Play Now
  matches and tournaments
- 60 FPS (the game asks for 30)
- Graphics fixes for Frostbite: no team-select flicker, clean player and helmet edges
- Saves report their real size, so tournaments no longer show "not enough system storage"
- Fixes for Be a Pro and Create a Team (jump tables), texel buffers inside images, and colour and
  depth-compare views of one texture, from HajDEO's NHL 24 port

**Launcher**
- NHL 24's own launcher: serial and update check, NHL 24 modules and patches, NHL 24 defaults,
  data in `%LOCALAPPDATA%\NHL24Native`, NHL 24 icon

**Known issues**
- The match opening runs at about 40 FPS, and some camera shots render below 1080p
- One mid-match freeze seen so far
- Modes other than Play Now and tournaments are untested
- One local player only; no online play
- Some stutter the first time each scene's shaders are built

## Credits

This port is built on the work of:

- **[NHL 19 port](https://github.com/thegh0sts/NHL-19-PS4-PORT-WINDOWS)**, which this project grew from
- **[GNSB](https://github.com/GNSB/UFC-3-PS4-PORT-LINUX-WINDOWS)**'s UFC 3 port, the NHL 19 port's base
- **[HajDEO](https://github.com/HajDEO/nhl24pc)**'s NHL 24 port (GPL-2.0): several graphics and shader
  fixes were ported from it
- **SacredFire** (T3CHNOLOG1C): the loader and launcher the UFC 3 port grew from
- **bbport** (deadinside28): the original native PS4 loader approach
- **[shadPS4](https://github.com/shadps4-emu/shadPS4)**: the Vulkan graphics backend and much PS4 knowledge
- SDL3, Dear ImGui, Vulkan, Zydis, xxHash, fmt, sirit, LibAtrac9, miniz, AMD FidelityFX FSR and
  others: see [`licenses/`](licenses/)

## Licence

This project is free software, licensed under the **GNU General Public License v2.0 or later**: see
[`LICENSE`](LICENSE). Third-party components keep their own licences, listed in [`licenses/`](licenses/).

## Legal

This is a fan project and is not affiliated with, endorsed by or connected to Electronic Arts, EA
SPORTS, the National Hockey League, the NHL Players' Association or Sony Interactive Entertainment.
*NHL*, *EA SPORTS* and *PlayStation* are trademarks of their respective owners. The project contains
no copyrighted game code or assets; it only runs a copy of the game you dumped yourself from a
console you own.
