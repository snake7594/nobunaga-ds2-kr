# -*- coding: utf-8 -*-
import json, glob, os
for p in sorted(glob.glob(r'D:\nds\roms\NOBU2\_work\gfxlabels\*.json')):
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
