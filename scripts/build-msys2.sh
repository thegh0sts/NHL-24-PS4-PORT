#!/usr/bin/env bash
# SacredFire Windows x86-64 build made ON Windows, in the MSYS2 CLANG64 shell: the same targets as
# scripts/build-windows.sh --runtime (sacredfire-game.exe, SacredFire.exe, bb-gpu-capabilities.exe)
# with MSYS2's own clang and libraries instead of the Linux-hosted llvm-mingw toolchain and sysroot.
#
#   bash scripts/build-msys2.sh            configure (first time) and build -> out/windows/bin
#   BB_LTO=ON bash scripts/build-msys2.sh  link-time optimisation (slower build, faster game: release)
#   BB_AVPLAYER=ON ...                     the AvPlayer/Videodec libraries (needs FFmpeg) for games
#                                          that play videos through sceAvPlayer
# One-time packages (MSYS2 CLANG64):
#   pacman -S --needed git mingw-w64-clang-x86_64-{toolchain,cmake,ninja,pkgconf,python,glslang,\
#     vulkan-devel,vulkan-memory-allocator,fmt,boost,robin-map,xxhash,sdl3,zydis}
#   (+ mingw-w64-clang-x86_64-ffmpeg for BB_AVPLAYER=ON)
#   magic_enum, miniz, VulkanMemoryAllocator, robin-map and xbyak: this script builds them once from
#   the commits pinned in packaging/windows/deps.lock into out/windows/msys2-deps (MSYS2 either
#   lacks them or packages them without the CMake files the project looks for).
# out/windows/bin also gets every MSYS2 DLL the programs load (found with ldd), so they run from a
# plain Windows folder too.
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ ${MSYSTEM:-} != CLANG64 ]]; then
    echo "build-msys2: run this in the MSYS2 CLANG64 shell (MSYSTEM is '${MSYSTEM:-unset}')" >&2
    exit 1
fi
root=${BB_WINDOWS_ROOT:-$PWD/out/windows}
build=$root/build-msys2
for tool in cmake ninja python3 pkg-config clang clang++; do
    command -v $tool >/dev/null || { echo "build-msys2: '$tool' is missing: install the packages listed at the top of this script" >&2; exit 1; }
done
command -v glslang >/dev/null || command -v glslangValidator >/dev/null ||
    { echo "build-msys2: glslang is missing (pacman -S mingw-w64-clang-x86_64-glslang)" >&2; exit 1; }

# Submodules and the FSR-Vulkan patch, as build-windows.sh does.
if [[ ! -f gpu/third_party/fsr-vulkan/CMakeLists.txt || ! -f gpu/third_party/imgui/imgui.h || ! -d third_party/LibAtrac9/C ]]; then
    git submodule update --init --recursive
fi
# With core.autocrlf=true (common on Windows) the submodule is checked out with CRLF line endings
# and the LF patch no longer applies ("patch does not apply"): check it out again with LF, once.
fsr=gpu/third_party/fsr-vulkan
if [[ $(git -C "$fsr" config --get core.autocrlf || true) != false ]] && grep -q $'\r' "$fsr/src/ffx_vk_fsr4_v07.c" 2>/dev/null; then
    echo "build-msys2: $fsr has Windows line endings (core.autocrlf): checking it out again with LF"
    git -C "$fsr" config core.autocrlf false
    git -C "$fsr" rm -r -q --cached .
    git -C "$fsr" reset -q --hard
fi
for patch in gpu/patches/fsr-vulkan/*.patch; do
    [[ -f $patch ]] || continue
    if ! git -C gpu/third_party/fsr-vulkan apply --reverse --check "$PWD/$patch" 2>/dev/null; then
        git -C gpu/third_party/fsr-vulkan apply "$PWD/$patch"
    fi
done

# Libraries MSYS2 lacks or packages without CMake config files: the pinned commits, built once.
deps=$root/msys2-deps
dep() {  # dep <lock name> <file that marks it installed> <cmake options...>
    local name=$1 marker=$2; shift 2
    [[ -f $deps/$marker ]] && return 0
    local url sha src=$root/msys2-src/$name
    url=$(awk -v n="$name" '$1 == n && $2 == "git" {print $3}' packaging/windows/deps.lock)
    sha=$(awk -v n="$name" '$1 == n && $2 == "git" {print $4}' packaging/windows/deps.lock)
    [[ -n $url && -n $sha ]] || { echo "build-msys2: $name is not in packaging/windows/deps.lock" >&2; exit 1; }
    echo "build-msys2: building $name ($sha) into $deps"
    rm -rf "$src"; mkdir -p "$src"
    git -C "$src" init -q
    git -C "$src" fetch -q --depth 1 "$url" "$sha"
    git -C "$src" checkout -q FETCH_HEAD
    cmake -S "$src" -B "$src/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$deps" \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ "$@" > "$src/build.log" 2>&1 &&
    ninja -C "$src/build" install >> "$src/build.log" 2>&1 ||
        { tail -30 "$src/build.log" >&2; echo "build-msys2: $name failed (log: $src/build.log)" >&2; exit 1; }
    [[ -f $deps/$marker ]] || { echo "build-msys2: $name installed, but $deps/$marker is missing" >&2; exit 1; }
}
dep magic_enum include/magic_enum/magic_enum.hpp -DMAGIC_ENUM_OPT_BUILD_EXAMPLES=OFF -DMAGIC_ENUM_OPT_BUILD_TESTS=OFF -DMAGIC_ENUM_OPT_INSTALL=ON
dep miniz lib/cmake/miniz/minizConfig.cmake -DBUILD_SHARED_LIBS=OFF -DBUILD_EXAMPLES=OFF -DBUILD_FUZZERS=OFF -DBUILD_TESTS=OFF
dep VulkanMemoryAllocator include/vk_mem_alloc.h
dep robin-map share/cmake/tsl-robin-map/tsl-robin-mapConfig.cmake
dep xbyak include/xbyak/xbyak.h
deps_win=$(cygpath -m "$deps")

version=$(git describe --tags --always 2>/dev/null || echo unknown)
if ! git diff --quiet --ignore-submodules=dirty HEAD -- 2>/dev/null; then version="$version-dirty"; fi

mkdir -p "$root"
cmake -S gpu -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_PREFIX_PATH="$deps_win" \
    -DCMAKE_CXX_FLAGS="-I$deps_win/include" -DCMAKE_C_FLAGS="-I$deps_win/include" \
    -DBB_BUILD_VERSION="$version" -DBB_PGO=off -DBB_LTO="${BB_LTO:-OFF}" -DBB_AVPLAYER="${BB_AVPLAYER:-OFF}" \
    > "$root/configure-msys2.log" 2>&1 || { tail -40 "$root/configure-msys2.log" >&2; echo "build-msys2: configure failed (log: $root/configure-msys2.log)" >&2; exit 1; }
echo "build-msys2: configured ($version, LTO ${BB_LTO:-OFF}, AvPlayer ${BB_AVPLAYER:-OFF})"

if ! ninja -C "$build" -j "${BB_JOBS:-$(nproc)}" sacredfire-game sacredfire bb-gpu-capabilities > "$root/build-msys2.log" 2>&1; then
    grep -v '^\[' "$root/build-msys2.log" | tail -60 >&2
    echo "build-msys2: build failed (full log: $root/build-msys2.log)" >&2
    exit 1
fi

mkdir -p "$root/bin"
cp "$build/sacredfire-game.exe" "$build/SacredFire.exe" "$build/bb-gpu-capabilities.exe" "$root/bin/"
# The MSYS2 DLLs the programs need, next to them (not the ones that come with Windows).
for exe in "$root"/bin/*.exe; do
    ldd "$exe" | awk '$2 == "=>" && $3 ~ /^\// {print $3}'
done | { grep -viE '^/c/windows/' || true; } | sort -u | while read -r dll; do
    # On a rebuild ldd finds the copies already in bin (SDL3.dll ...): nothing to copy.
    [[ $dll -ef $root/bin/$(basename "$dll") ]] && continue
    cp -u "$dll" "$root/bin/"
done
printf '%s\n' "$version" > "$root/bin/VERSION"
echo "build-msys2: $root/bin: sacredfire-game.exe, SacredFire.exe, bb-gpu-capabilities.exe + $(ls "$root"/bin/*.dll 2>/dev/null | wc -l) DLLs ($version)"
