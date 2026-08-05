# -*- coding: utf-8 -*-
import json, glob, os
import os as _os, sys as _sys
_sys.path[:0] = [_os.path.dirname(_os.path.abspath(__file__)),
                _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')]
from nobu2_paths import ROM_IN, ROM_OUT, WORK, FONT, DATA
for p in sorted(glob.glob(_os.path.join(WORK, 'gfxlabels', '*.json'))):
    n = os.path.basename(p)
    if n.startswith('_'):
        continue
    try:
        e = json.load(open(p, encoding='utf-8-sig'))
    except Exception as ex:
        print(n, 'BAD', ex); continue
    if not e:
        print(f'{n}: (empty)'); continue
    x = e[0]
    print(f"{n}: n={len(e)} jp={x.get('jp','')!r} kr={x.get('kr','')!r}")
