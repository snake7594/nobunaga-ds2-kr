# -*- coding: utf-8 -*-
"""Recompute safe capacities for common.snr units:
- if the trailing null run ends exactly at the start of the next string run,
  the nulls are field padding -> capacity = next_start - off - 1 (keep 1 null)
- else (params follow) -> conservative: capacity = len + min(trailing_nulls - 1, 4)
"""
import json
import os as _os, sys as _sys
_sys.path[:0] = [_os.path.dirname(_os.path.abspath(__file__)),
                _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')]
from nobu2_paths import ROM_IN, ROM_OUT, WORK, FONT, DATA


def compute():
    d = open(_os.path.join(WORK, 'fs', 'scenario', 'common.snr'), 'rb').read()
    n = len(d)
    def is_lead(c): return 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF
    def is_trail(c): return 0x40 <= c <= 0xFC and c != 0x7F
    starts = set()
    runs = []
    i = 0
    while i < n:
        c = d[i]
        st = (0xA1 <= c <= 0xDF) or (is_lead(c) and i+1 < n and is_trail(d[i+1]))
        if not st: i += 1; continue
        j = i
        while j < n:
            cj = d[j]
            if is_lead(cj) and j+1 < n and is_trail(d[j+1]): j += 2
            elif 0xA1 <= cj <= 0xDF: j += 1
            else: break
        starts.add(i); runs.append((i, j)); i = j
    caps = {}
    for (a, b) in runs:
        j = b
        while j < n and d[j] == 0: j += 1
        nulls = j - b
        if nulls == 0:
            caps[a] = b - a
        elif j in starts:
            caps[a] = (j - a) - 1      # padding owned by this field, keep 1 null
        else:
            caps[a] = (b - a) + min(nulls - 1, 4) if nulls > 1 else (b - a)
    return caps

if __name__ == '__main__':
    caps = compute()
    json.dump({str(k): v for k, v in caps.items()}, open(_os.path.join(WORK, 'snr_caps.json'), 'w'))
    units = json.load(open(_os.path.join(WORK, 'units.json'), encoding='utf-8'))
    tight = 0
    for u in units:
        if u['src'] != 'common.snr': continue
        c = caps.get(u['off'])
        if c is not None and c < u['cap']:
            tight += 1
    print('snr units with reduced capacity:', tight)
