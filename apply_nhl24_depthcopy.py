#!/usr/bin/env python3
r"""NHL 24: depth copies between D32 and D32+S8 go through a buffer (the GPU was lost on them).
Run once from the repo root, then rebuild:

    python3 apply_nhl24_depthcopy.py
    bash scripts/build-msys2.sh && BB_SKIP_PREPARE=1 bash scripts/run-msys2.sh nhl24

The game uses its 1920x1080 depth buffer both with and without stencil. The texture cache keeps
two images for it (D32Sfloat and D32SfloatS8Uint) and copies one into the other when the game
switches. CopyColorAndDepth did that with a direct image-to-image copy, but Vulkan only allows a
direct copy between depth images of the same format; on the RTX 4080 the copy back
(D32SfloatS8Uint -> D32Sfloat) sometimes hung the GPU ("#... STUCK: pass image copy (image
0x110b5b0000 1920x1080 ...)", device lost) before the title screen, in about half the runs.

gpu/shadps4/video_core/renderer_vulkan/vk_runtime.cpp, Runtime::CopyColorAndDepth
    Two single-sample, single-level depth images whose Vulkan formats differ are copied through the staging
    buffer (depth aspect out, depth aspect in), the path already used for depth <-> colour.
    Logged once ("GPU: depth copy D32SfloatS8Uint -> D32Sfloat through a buffer").
"""
import sys
from pathlib import Path

p = Path('gpu/shadps4/video_core/renderer_vulkan/vk_runtime.cpp')
if not p.exists():
    sys.exit(f'run this from the repo root ({p} not found)')
s = p.read_text(encoding='utf-8')
if 'NHL 24: depth images of different formats' in s:
    sys.exit('already applied')

old = ('    if (src->info.num_samples == 1 && dst->info.num_samples == 1) {\n'
       '        if (instance.IsMaintenance8Supported() ||\n'
       '            src->info.props.is_depth == dst->info.props.is_depth) {\n')
new = ('    if (src->info.num_samples == 1 && dst->info.num_samples == 1) {\n'
       '        // NHL 24: depth images of different formats (D32 and D32+S8) cannot be copied directly\n'
       '        // (Vulkan needs the same format; the GPU was lost on it): through the buffer instead.\n'
       '        const auto src_format = src->backing->image.image_ci.format;\n'
       '        const auto dst_format = dst->backing->image.image_ci.format;\n'
       '        const bool depth_formats_differ =\n'
       '            src->info.props.is_depth && dst->info.props.is_depth && src_format != dst_format &&\n'
       '            std::min(src->info.resources.levels, dst->info.resources.levels) == 1 &&\n'
       '            src->info.resources.layers == dst->info.resources.layers; // the buffer path\'s limits\n'
       '        if (depth_formats_differ) {\n'
       '            static bool shown;\n'
       '            if (!shown) {\n'
       '                shown = true;\n'
       '                std::printf("GPU: depth copy %s -> %s through a buffer\\n",\n'
       '                            vk::to_string(src_format).c_str(), vk::to_string(dst_format).c_str());\n'
       '            }\n'
       '        }\n'
       '        if (!depth_formats_differ && (instance.IsMaintenance8Supported() ||\n'
       '            src->info.props.is_depth == dst->info.props.is_depth)) {\n')
if s.count(old) != 1:
    sys.exit(f'{p} was not as expected (nothing changed)')
s = s.replace(old, new, 1)
if '#include <cstdio>' not in s:
    s = s.replace('#include', '#include <cstdio>\n#include', 1)
p.write_text(s, encoding='utf-8', newline='\n')
print(f'changed: {p} (depth copies between different depth formats go through a buffer)')
