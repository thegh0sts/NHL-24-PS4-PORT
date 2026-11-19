# NHL 24 native port — Windows

This archive runs **EA SPORTS NHL 24** (PlayStation 4, `CUSA37933`, update **1.60**) as a native
Windows x86-64 program. It was built from the source at the commit in `VERSION`
(https://github.com/thegh0sts/NHL-24-PS4-PORT) and **contains no game files**: you need your own
dump of the game and its 1.60 update.

It grew from the NHL 19 port (https://github.com/thegh0sts/NHL-19-PS4-PORT-WINDOWS), a fork of
**GNSB's UFC 3 port** (https://github.com/GNSB/UFC-3-PS4-PORT-LINUX-WINDOWS), and includes fixes
from HajDEO's NHL 24 port (https://github.com/HajDEO/nhl24pc). The full credits are in the
project's README.

## Requirements

- 64-bit Windows 10 (1903 or newer) or Windows 11.
- A GPU with a Vulkan 1.3 driver (tested: NVIDIA RTX 4080 SUPER).
- A CPU from Intel Haswell (4th generation Core) or newer, or any AMD Ryzen.
- The game: the base folder `CUSA37933` and the 1.60 update next to it, e.g.
  `PS4\CUSA37933` and `PS4\CUSA37933-patch` (also `-PATCH`, `-update`, `_patch`), or one folder
  with the update already merged. Separate folders are merged automatically into
  `CUSA37933-merged` with hard links (no extra space on NTFS).

## Playing

1. Extract the archive anywhere (not inside the game folder, and not in a OneDrive folder).
2. Run **`NHL24.exe`**, pick the game folder (the one with `eboot.bin`) with **Browse...**, press
   **Play**.
3. The first start prepares the game for a little while. Data, saves and logs live in
   `%LOCALAPPDATA%\NHL24Native` (**Open data** and **Open logs** in the launcher).

The first matches build the shader cache: expect stutter and a lower frame rate the first time each
scene appears, the match opening especially.

### Launcher settings

- **Player name**: the name the game shows (16 characters, ASCII).
- **Language**: the PS4 system language the game reads (its text and menus). A `BB_LANGUAGE` set
  before the launcher (e.g. `set BB_LANGUAGE=1` in a `.bat`) wins over this choice.
- **Controller** and **Controls...**: which gamepad is player 1, and keyboard keys (click, then
  press the key) and gamepad buttons for every PS4 input. The keyboard and a gamepad work
  together.
- **Game resolution**: 1280x720 or 1920x1080, what the game renders. The game also lowers its
  resolution itself for some camera shots, as on a PS4.
- **Display resolution**: the window size: the game's size, 1080p, 1440p (2K) or 4K. The game's
  frame is scaled to it; use **Upscaling = AMD FSR 1.0** and some **Sharpening** for a sharp image.
  In fullscreen the monitor's size is used.
- **Present mode**:
  - *Immediate*: frames shown as soon as they're ready; lowest lag, may tear. Use it with an FPS
    limit, or with G-Sync / FreeSync.
  - *Mailbox*: no tearing, low lag; the GPU keeps drawing and only the newest frame is shown.
  - *VSync (FIFO)*: no tearing, follows the monitor; a little more lag.
- **FPS limit**: 60 / 90 / 120 / 144 / 240 / Unlimited. The game itself runs at up to 60 FPS
  (the port overrides its request for 30).
- **Show the FPS counter**, **Skip the intro videos**, **Fullscreen**.
- **Online play**: leave it on **Offline**. NHL 24 isn't playable online with this port, and the
  join and host options are for the UFC 3 port's server.
- **Add to Steam**: a Steam shortcut to the launcher.
- In game: **Insert** or **L3+R3** opens the overlay menu.

The game shows a no-connection notice at start-up: it plays offline.

## Problems

If the game crashes or freezes, send the newest `.log` from `%LOCALAPPDATA%\NHL24Native\logs`
(the launcher's **Open logs**) with a short description of what was on screen. Checking
**Frame statistics** first makes the log more useful. If the game freezes, wait 30 to 60 seconds
before closing it, so the log can record why.

If you report a problem with a game mode, also send your saves: zip the `user` folder in
`%LOCALAPPDATA%\NHL24Native` (the `cache` folder inside can be left out). Don't send game files or
anything from the `out` folder.

If the launcher's log says a program "could not start" (Windows error 0xC0000022, access
denied): allow the file in your antivirus (Windows Security > Protection history), extract the
archive outside OneDrive (e.g. `C:\Games\NHL24`), or unblock the zip (Properties > Unblock) and
extract it again.

This project is not affiliated with or endorsed by Electronic Arts, EA SPORTS, the National Hockey
League, the NHL Players' Association or Sony Interactive Entertainment. GPL-2.0-or-later;
third-party licences are in `licenses\`.
