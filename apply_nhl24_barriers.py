#!/usr/bin/env python3
r"""NHL 24: a GPU image transition outside the image's own levels/layers no longer stops the game.
Run once from the repo root, then rebuild:

    python3 apply_nhl24_barriers.py
    bash scripts/build-msys2.sh && BB_SKIP_PREPARE=1 bash scripts/run-msys2.sh nhl24

After PLAY NOW the game stopped with "image.cpp:312 GetBarriers: Assertion Failed!". The per-level
/ per-layer layout list belongs to the image's backing (its Vulkan image), which several cache
images can share; it was sized by whichever image first needed it. An image with more levels or
layers on the same backing (or a range asking past the image's last level/layer) then indexed
past the end of the list.

gpu/shadps4/video_core/texture_cache/image.cpp, Image::GetBarriers
    - the list is rebuilt (every entry = the last whole-image state) when its size does not match
      this image's levels x layers;
    - the requested level and layer range is clipped to the image's own levels and layers.
    The first time either happens the GPU log says so (once), so we can see how often.
"""
import sys
from pathlib import Path

p = Path('gpu/shadps4/video_core/texture_cache/image.cpp')
if not p.exists():
    sys.exit(f'run this from the repo root ({p} not found)')
s = p.read_text(encoding='utf-8')
if 'NHL 24: the layout list belongs to the backing' in s:
    sys.exit('already applied')

subs = [
    ('        if (!partially_transited) {\n'
     '            subresource_states.resize(info.resources.levels * info.resources.layers);\n'
     '            std::fill(subresource_states.begin(), subresource_states.end(), last_state);\n'
     '        }\n',
     '        // NHL 24: the layout list belongs to the backing, which images with other level/layer\n'
     '        // counts can share; rebuild it when it was sized for a different image.\n'
     '        const size_t wanted_states = size_t(info.resources.levels) * info.resources.layers;\n'
     '        if (partially_transited && subresource_states.size() != wanted_states) {\n'
     '            static bool shown;\n'
     '            if (!shown) {\n'
     '                shown = true;\n'
     '                std::printf("GPU: image %#llx: layout list of %zu entries rebuilt for %u levels x %u layers (shared backing)\\n",\n'
     '                            (unsigned long long)info.guest_address, subresource_states.size(),\n'
     '                            info.resources.levels, info.resources.layers);\n'
     '            }\n'
     '        }\n'
     '        if (!partially_transited || subresource_states.size() != wanted_states) {\n'
     '            subresource_states.resize(wanted_states);\n'
     '            std::fill(subresource_states.begin(), subresource_states.end(), last_state);\n'
     '        }\n'
     '        // The requested range, clipped to this image\'s own levels and layers.\n'
     '        u32 range_level = 0, range_level_end = info.resources.levels;\n'
     '        u32 range_layer = 0, range_layer_end = info.resources.layers;\n'
     '        if (needs_partial_transition) {\n'
     '            range_level = std::min<u32>(subres_range->base.level, info.resources.levels);\n'
     '            range_level_end = std::min<u32>(subres_range->base.level + subres_range->extent.levels, info.resources.levels);\n'
     '            range_layer = std::min<u32>(subres_range->base.layer, info.resources.layers);\n'
     '            range_layer_end = std::min<u32>(subres_range->base.layer + subres_range->extent.layers, info.resources.layers);\n'
     '            static bool clipped_shown;\n'
     '            if (!clipped_shown && (range_level_end - range_level != subres_range->extent.levels ||\n'
     '                                   range_layer_end - range_layer != subres_range->extent.layers)) {\n'
     '                clipped_shown = true;\n'
     '                std::printf("GPU: image %#llx: transition of levels %u+%u layers %u+%u clipped to %u levels x %u layers\\n",\n'
     '                            (unsigned long long)info.guest_address, subres_range->base.level,\n'
     '                            subres_range->extent.levels, subres_range->base.layer, subres_range->extent.layers,\n'
     '                            info.resources.levels, info.resources.layers);\n'
     '            }\n'
     '        }\n'),
    ('        const auto mips =\n'
     '            needs_partial_transition\n'
     '                ? std::ranges::views::iota(subres_range->base.level,\n'
     '                                           subres_range->base.level + subres_range->extent.levels)\n'
     '                : std::views::iota(0u, info.resources.levels);\n'
     '        const auto layers =\n'
     '            needs_partial_transition\n'
     '                ? std::ranges::views::iota(subres_range->base.layer,\n'
     '                                           subres_range->base.layer + subres_range->extent.layers)\n'
     '                : std::views::iota(0u, info.resources.layers);\n',
     '        const auto mips = std::views::iota(range_level, range_level_end);\n'
     '        const auto layers = std::views::iota(range_layer, range_layer_end);\n'),
]
missing = [old[:70] for old, _ in subs if s.count(old) != 1]
if missing:
    sys.exit(f'{p} was not as expected (nothing changed); not found:\n  ' + '\n  '.join(missing))
for old, new in subs:
    s = s.replace(old, new, 1)
for header in ('<cstdio>', '<algorithm>'):
    if f'#include {header}' not in s:
        s = s.replace('#include', f'#include {header}\n#include', 1)
p.write_text(s, encoding='utf-8', newline='\n')
print(f'changed: {p} (image layout transitions stay inside the image)')
