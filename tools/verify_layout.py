# -*- coding: utf-8 -*-
"""Verify the patched ROM differs ONLY inside expected regions (arm9, msgsec, common.snr)
and that header/FNT/FAT are byte-identical to the original."""
import json, struct

WORK = r'D:\nds\roms\NOBU2\_work'
a = open(r'D:\nds\roms\NOBU2\Nobunaga no Yabou DS 2 (Japan).nds', 'rb').read()
b = open(r'D:\nds\roms\NOBU2\Nobunaga no Yabou DS 2 (Korean).nds', 'rb').read()
print('sizes equal:', len(a) == len(b))

manifest = json.load(open(WORK + r'\manifest.json'))
allowed = [(0x4000, 0x4000 + 0x1A1098)]   # arm9
for f in manifest['files']:
    p = f['path']
    if p.startswith('/msg/msgsec') or p == '/scenario/common.snr':
        allowed.append((f['start'], f['start'] + f['size']))
allowed.sort()

def in_allowed(i):
    import bisect
    j = bisect.bisect_right(allowed, (i, 1 << 62)) - 1
    return j >= 0 and allowed[j][0] <= i < allowed[j][1]

# find diff runs
runs = []
i = 0
n = len(a)
while i < n:
    if a[i] != b[i]:
        j = i
        while j < n and a[j] != b[j]:
            j += 1
        runs.append((i, j))
        i = j
    else:
        i += 1
print('diff runs:', len(runs))
outside = [(s, e) for s, e in runs if not in_allowed(s)]
print('diff runs OUTSIDE allowed regions:', len(outside))
for s, e in outside[:10]:
    print(f'  0x{s:X}-0x{e:X} ({e-s} bytes)')

# header / FNT / FAT identity
fnt_off, fnt_size = struct.unpack_from('<II', a, 0x40)
fat_off, fat_size = struct.unpack_from('<II', a, 0x48)
print('header (0-0x200) identical:', a[:0x200] == b[:0x200])
print('FNT identical:', a[fnt_off:fnt_off+fnt_size] == b[fnt_off:fnt_off+fnt_size])
print('FAT identical:', a[fat_off:fat_off+fat_size] == b[fat_off:fat_off+fat_size])
print('arm7 identical:', a[0x1A5200:0x1A5200+0x26F28] == b[0x1A5200:0x1A5200+0x26F28])
# sound/graphics untouched?
for f in manifest['files']:
    if f['path'] in ('/snd/sound_data.sdat', '/bg/GrpBG.dat', '/movie/op.mods'):
        s, sz = f['start'], f['size']
        print(f"{f['path']} identical:", a[s:s+sz] == b[s:s+sz])
