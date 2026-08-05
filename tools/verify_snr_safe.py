# -*- coding: utf-8 -*-
"""Confirm the rebuilt common.snr only touches genuine text fields:
every changed byte must lie inside a safe field, and no byte in the
0xA1-0xDF binary range may have been altered."""
import json, bisect
import os as _os, sys as _sys
_sys.path[:0] = [_os.path.dirname(_os.path.abspath(__file__)),
                _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')]
from nobu2_paths import ROM_IN, ROM_OUT, WORK, FONT, DATA

orig = open(_os.path.join(WORK, 'fs', 'scenario', 'common.snr'), 'rb').read()
manifest = json.load(open(_os.path.join(WORK, 'manifest.json')))
rom = open(ROM_OUT, 'rb').read()
f = next(x for x in manifest['files'] if x['path'] == '/scenario/common.snr')
new = rom[f['start']: f['start'] + f['size']]

safe = json.load(open(_os.path.join(WORK, 'snr_units_safe.json'), encoding='utf-8'))
spans = sorted((s['off'], s['off'] + s['cap']) for s in safe)

def inside(i):
    j = bisect.bisect_right(spans, (i, 1 << 62)) - 1
    return j >= 0 and spans[j][0] <= i < spans[j][1]

changed = [i for i in range(len(orig)) if orig[i] != new[i]]
outside = [i for i in changed if not inside(i)]
print('changed bytes:', len(changed))
print('changed OUTSIDE safe text fields:', len(outside))
for i in outside[:10]:
    print(f'   0x{i:X}: {orig[i]:02X} -> {new[i]:02X}')

# the specific corruption class from v1.4: lone binary bytes 0xA1-0xDF -> 0x20
hw = [i for i in changed if 0xA1 <= orig[i] <= 0xDF and new[i] == 0x20]
print('binary bytes (0xA1-0xDF) overwritten with space:', len(hw))

# spot-check the records the user reported
smap = json.load(open(_os.path.join(WORK, 'syllable_map.json'), encoding='utf-8'))
rev = {int(v, 16): k for k, v in smap.items()}
def dec(b):
    out, i = '', 0
    while i < len(b) - 1:
        if b[i] == 0: break
        c = (b[i] << 8) | b[i+1]
        if c in rev: out += rev[c]
        else:
            try: out += bytes(b[i:i+2]).decode('shift_jis')
            except Exception: out += '?'
        i += 2
    return out
for name, pat in (('尾張', '尾張'), ('織田', '織田'), ('信長', '信長')):
    o = orig.find(pat.encode('shift_jis'))
    print(f'{name} @0x{o:X}: orig-binary-prefix {orig[o-16:o].hex(" ")}')
    print(f'{" "*len(name)}      new -binary-prefix {new[o-16:o].hex(" ")}')
    print(f'    text: {dec(new[o:o+16])}')
