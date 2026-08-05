# -*- coding: utf-8 -*-
"""Rebuild the common.snr unit list with a SAFE rule.

common.snr stores names as full-width Shift-JIS strings inside fixed, null-padded
fields.  Bytes 0xA1-0xDF (halfwidth katakana) never occur as text there - they are
binary record fields (ids, stats, face indices).  v1.0-v1.4 mis-detected those as
text and overwrote them, scrambling busho data.

Safe rule for a unit:
  * consists only of valid 2-byte Shift-JIS pairs
  * at least 2 characters
  * starts at a field boundary (preceded by 0x00) and is null-terminated
"""
import json, os, sys
import os as _os, sys as _sys
_sys.path[:0] = [_os.path.dirname(_os.path.abspath(__file__)),
                _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')]
from nobu2_paths import ROM_IN, ROM_OUT, WORK, FONT, DATA

d = open(_os.path.join(WORK, 'fs', 'scenario', 'common.snr'), 'rb').read()

def is_lead(c): return 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF
def is_trail(c): return 0x40 <= c <= 0xFC and c != 0x7F

runs = []
i, n = 0, len(d)
while i < n - 1:
    if is_lead(d[i]) and is_trail(d[i+1]):
        j = i
        while j < n - 1 and is_lead(d[j]) and is_trail(d[j+1]):
            j += 2
        runs.append((i, j))
        i = j
    else:
        i += 1

good = []
for (a, b) in runs:
    nchars = (b - a) // 2
    if nchars < 2:
        continue
    if a > 0 and d[a-1] != 0:
        continue                     # not at a field start
    if b >= n or d[b] != 0:
        continue                     # not null-terminated
    try:
        txt = d[a:b].decode('shift_jis')
    except Exception:
        continue
    # field capacity: up to (but not including) the last null before the next
    # non-null byte, so the terminator is always preserved
    j = b
    while j < n and d[j] == 0:
        j += 1
    cap = (b - a) + max(0, (j - b) - 1)
    good.append({'off': a, 'len': b - a, 'cap': cap, 'jp': txt, 'lines': [cap]})

print(f'safe common.snr text fields: {len(good)}')
tot = sum(g['len'] for g in good)
print(f'total text bytes: {tot}')

old = [u for u in json.load(open(_os.path.join(WORK, 'units.json'), encoding='utf-8'))
       if u['src'] == 'common.snr']
print(f'previous (unsafe) unit count: {len(old)}')
oldset = {u['off'] for u in old}
newset = {g['off'] for g in good}
print(f'  dropped (binary mis-detected): {len(oldset - newset)}')
print(f'  newly included: {len(newset - oldset)}')

json.dump(good, open(_os.path.join(WORK, 'snr_units_safe.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=0)
for g in good[:8]:
    print(f"   0x{g['off']:X} len={g['len']} cap={g['cap']} {g['jp']}")
