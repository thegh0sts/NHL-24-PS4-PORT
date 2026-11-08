#!/usr/bin/env bash
# Development runner on Windows (MSYS2 CLANG64): run.sh's preparation steps, then the game with
# out/windows/bin/sacredfire-game.exe (from scripts/build-msys2.sh). The whole output goes to
# out/run.txt as well as the terminal.
#
#   bash scripts/run-msys2.sh [GAME_DIR] [extra loader arguments...]
#   GAME_DIR: the game folder with eboot.bin (default: $BB_GAME_DIR, else ./nhl24)
#   BB_SKIP_PREPARE=1   run again without preparing (after the first run)
# Any BB_* variable set before it reaches the game (BB_LOG_UNRESOLVED=1, BB_NEO=1, ...).
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
[[ ${MSYSTEM:-} == CLANG64 ]] || { echo "run-msys2: run this in the MSYS2 CLANG64 shell" >&2; exit 1; }
game=${BB_GAME_DIR:-nhl24}
if [[ $# -gt 0 && -d $1 ]]; then game=$1; shift; fi
[[ -f $game/eboot.bin ]] || { echo "run-msys2: no eboot.bin in '$game' (pass the game folder, or set BB_GAME_DIR)" >&2; exit 1; }
exe=out/windows/bin/sacredfire-game.exe
[[ -f $exe ]] || { echo "run-msys2: $exe not found: build first (bash scripts/build-msys2.sh)" >&2; exit 1; }
out=out
mkdir -p "$out"
export BB_CONFIG=${BB_CONFIG:-$PWD/bbport.ini}

# The game check: the profile (nhl19, ufc3) and what to link.
# (Windows Python ends lines with \r\n: tr removes the \r.)
profile=$(python3 scripts/game_check.py "$game" | tr -d '\r') || { echo "$profile" >&2; exit 2; }
export BB_GAME_PROFILE=$profile
export BB_GAME_VARIANT=$(python3 scripts/game_check.py "$game" --variant 2>/dev/null | tr -d '\r' || echo '?')
read -r title version modules < <(python3 - "$game" <<'PY' | tr -d '\r'
import sys
sys.path.insert(0, 'scripts')
import game_check
p = game_check.profile(sys.argv[1]) or {}
print(p.get('title', '?'), p.get('version', '?'), ' '.join(p.get('modules', ('libc.prx', 'libSceFios2.prx'))))
PY
)
echo "run-msys2: $profile ($title $version, build $BB_GAME_VARIANT), modules: $modules"

if [[ ${BB_SKIP_PREPARE:-0} != 1 ]]; then
    python3 scripts/prepare.py "$game" --out "$out"
    python3 scripts/link_libc.py "$game" --out "$out"
    python3 scripts/link_modules.py "$game" --out "$out" --modules $modules
    aerolib_args=(); [[ -f share/aerolib.inl ]] && aerolib_args=(--aerolib share/aerolib.inl)
    python3 tools/gen_import_names.py --out "$out" "${aerolib_args[@]}"
    python3 scripts/content_profile.py "$game" --out "$out" --sku "${BB_CONTENT_SKU:-full}"
    python3 scripts/patches.py --patches-dir "${BB_PATCHES_DIR:-patches}" --patches-config "${BB_PATCHES_CONFIG:-patches.json}" \
        --app-version "$version" --title-id "$title" --out "$out" --settings "$BB_CONFIG"
fi
patch_args=(); [[ -f $out/patches.bin ]] && patch_args=(--patches "$out/patches.bin")
export BB_NEO=${BB_NEO:-0}
# NHL 19: with the runtime's offline network answers the sim thread reads an online-service object
# that was never made (guest fault at 0x3846425, a null global); with the network mode on
# (BB_ONLINE_SERVER: simulated PSN sign-in, only *.ea.com names resolve, to 127.0.0.1) start-up
# continues. Nothing listens there, so the game finds no EA servers. BB_ONLINE_SERVER= (empty) turns it off.
if [[ $profile == nhl19 && -z ${BB_ONLINE_SERVER+set} ]]; then
    export BB_ONLINE_SERVER=127.0.0.1
    echo "run-msys2: NHL 19: network mode on (BB_ONLINE_SERVER=127.0.0.1)"
fi
# Ignite games (UFC 3, NHL 19): the 3D scene renders black without precise readbacks of linear
# images (shadPS4 issue #4375 for UFC 4, same engine); the rest as run.sh's ufc3 defaults: twins
# off (they deadlock against precise readbacks), write windows + pre-upload + single-stepped
# writes, Z16+S8 depth kept as D16. Each can still be overridden from the command line.
if [[ $profile == nhl19 || $profile == ufc3 ]]; then
    if [[ $profile == nhl19 ]]; then
        # NHL 19: readbacks 1 draws the players as 2 does, with calmer jerseys (2 still left a slight jitter).
        export BB_READBACKS=${BB_READBACKS:-1}
    fi
    export BB_READBACKS=${BB_READBACKS:-2} BB_READBACK_LINEAR=${BB_READBACK_LINEAR:-1} BB_GPU_WRITE_TWINS=${BB_GPU_WRITE_TWINS:-0}
    if [[ $profile == nhl19 ]]; then
        # NHL 19: write windows/stepped writes send the players' cloth vertices to the GPU while the
        # game is still writing them (jerseys shake), so they are off. The background pre-upload stays
        # on: without it the main menu's mode tiles are missing. Black models without the linear
        # readbacks above.
        export BB_WRITE_WINDOW=${BB_WRITE_WINDOW:-0} BB_PREUPLOAD=${BB_PREUPLOAD:-1} BB_WRITE_STEP=${BB_WRITE_STEP:-0}
    else
        export BB_WRITE_WINDOW=${BB_WRITE_WINDOW:-1} BB_PREUPLOAD=${BB_PREUPLOAD:-1} BB_WRITE_STEP=${BB_WRITE_STEP:-1}
    fi
    export BB_Z16S8_AS_D16=${BB_Z16S8_AS_D16:-1}
    echo "run-msys2: Ignite graphics defaults: readbacks $BB_READBACKS, linear $BB_READBACK_LINEAR, pre-upload $BB_PREUPLOAD, write windows $BB_WRITE_WINDOW"
fi
# NHL 19: the game asks for flip rate 1 (30 FPS) for its intro videos, team select and matches, and
# 0 (60 FPS) in the menus. BB_FLIP_RATE=0 keeps it at 60 throughout; BB_FLIP_RATE=-1 lets the game
# choose again (the console's behaviour).
if [[ $profile == nhl19 ]]; then
    export BB_FLIP_RATE=${BB_FLIP_RATE:-0}
    if [[ $BB_FLIP_RATE == 0 ]]; then echo "run-msys2: NHL 19: 60 FPS throughout (BB_FLIP_RATE=0; -1 lets the game choose)"
    else echo "run-msys2: NHL 19: flip rate $BB_FLIP_RATE"; fi
fi

echo "run-msys2: starting $exe (log: $out/run.txt)"
"$exe" "$out/boot-linked.bin" --import-names "$out/import_names.txt" --content-profile "$out/content.bin" \
    "${patch_args[@]}" --app0 "$game" --user "${BB_USER_DIR:-user}" --timeout "${BB_TIMEOUT:-0}" "$@" 2>&1 | tee "$out/run.txt"
