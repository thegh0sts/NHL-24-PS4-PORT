#!/usr/bin/env python3
r"""NHL 24: 3D-audio calls answer "not supported" AND fill in their output values. Run once from
the repo root (after apply_nhl24_batch3.py), then rebuild:

    python3 apply_nhl24_audio3d.py
    bash scripts/build-msys2.sh

Why: the crash in Frostbite's memory code (VirtualAlloc_Sony.cpp "couldn't be mapped") came from
a heap allocation made by the game's object-audio code (backtrace frame +0xd25182) just after
sceAudio3dPortGetAttributesSupported (+0xd2513d). The runtime answered "not supported" but left
the count of supported attributes unwritten, so the game read whatever was in that memory and
asked for gigabytes (a different amount every run: 11.8, 8.7, 7.5, 3.8 GB). Now:
  sceAudio3dPortGetAttributesSupported(port, caps, *count)  -> *count = 0
  sceAudio3dPortOpen(user, params, *port)                    -> *port = -1 (no port)
  sceAudio3dObjectReserve(port, *object)                     -> *object = 0xFFFFFFFF (none)
each still answering "not supported", so the game keeps its ordinary audio output.
"""
import sys
from pathlib import Path

p = Path('src/runtime_services.c')
if not p.exists():
    sys.exit('run this from the repo root (src/runtime_services.c not found)')
s = p.read_text(encoding='utf-8')
if 'audio3d_attributes_none' in s:
    sys.exit('already applied')

fn_anchor = 'static ABI int32_t audio3d_unsupported(void) { return AUDIO3D_NOT_SUPPORTED; }'
fn = (fn_anchor + '\n'
      '/* NHL 24: the same answer, with the output values written (the game uses them even on failure). */\n'
      'static ABI int32_t audio3d_attributes_none(uint32_t port, void *caps, uint32_t *count) {\n'
      '    (void)port; (void)caps; if (count) *count=0; return AUDIO3D_NOT_SUPPORTED;\n'
      '}\n'
      'static ABI int32_t audio3d_port_open_none(int32_t user, const void *params, int32_t *port) {\n'
      '    (void)user; (void)params; if (port) *port=-1; return AUDIO3D_NOT_SUPPORTED;\n'
      '}\n'
      'static ABI int32_t audio3d_object_reserve_none(uint32_t port, uint32_t *object) {\n'
      '    (void)port; if (object) *object=UINT32_C(0xFFFFFFFF); return AUDIO3D_NOT_SUPPORTED;\n'
      '}')
subs = [(fn_anchor, fn),
        ('{"sceAudio3dPortGetAttributesSupported",audio3d_unsupported}', '{"sceAudio3dPortGetAttributesSupported",audio3d_attributes_none}'),
        ('{"sceAudio3dPortOpen",audio3d_unsupported}', '{"sceAudio3dPortOpen",audio3d_port_open_none}'),
        ('{"sceAudio3dObjectReserve",audio3d_unsupported}', '{"sceAudio3dObjectReserve",audio3d_object_reserve_none}')]
missing = [a[:70] for a, _ in subs if s.count(a) != 1]
if missing:
    sys.exit('src/runtime_services.c was not as expected (apply apply_nhl24_batch3.py first; nothing changed):\n  ' + '\n  '.join(missing))
for a, b in subs:
    s = s.replace(a, b, 1)
p.write_text(s, encoding='utf-8', newline='\n')
print('changed: src/runtime_services.c (3D audio: output values written)')
