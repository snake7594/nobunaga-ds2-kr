# -*- coding: utf-8 -*-
"""Objective damage detector for the graphics patch.

Eyeballing 700 cells does not scale, and "the cell changed a lot" is not a
defect - erasing a kanji legitimately changes most of its pixels.  What IS a
defect is a change *outside* the rectangle the patcher was allowed to touch:
the sprites share an atlas, so a write meant for one label can surface in a
completely different cell as a hole in a button or a stray bar.

apply_labels.py records each cell's permitted rectangle next to the .dat;
this walks every bank and reports pixels that changed outside of it.

Usage: python check_damage.py [--json out.json] [--limit N]
"""
import os, sys, json, glob
import concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ncer
import label_tools as lt

WORK = r'D:\nds\roms\NOBU2\_work'
SRC = WORK + r'\fs\obj'
OUT = WORK + r'\fs_gfx\obj'
NOISE = 8      # a handful of pixels is antialias spill, not damage

def audit(name):
    a = ncer.load(os.path.join(SRC, name + '.dat'))
    b = ncer.load(os.path.join(OUT, name + '.dat'))
    if not a or not b or not a.get('ncer') or not b.get('ncer'): return []
    try:
        rects = json.load(open(os.path.join(WORK, 'fs_gfx', 'rects',
                                            name + '.dat.json'), encoding='utf-8'))
    except OSError:
        rects = {}
    va, vb = a['vals'], b['vals']
    n = min(len(a['ncer']['banks']), len(b['ncer']['banks']))
    bad = []
    for i in range(n):
        r = lt.cell_pixels(a, i)
        if r is None: continue
        W, H, src = r
        box = rects.get(str(i))
        leaked = holes = 0
        for y in range(H):
            inside_y = box and box[1] <= y < box[3]
            for x in range(W):
                s = src[y][x]
                if s is None: continue
                k = s[0]*64 + s[1]
                if va[k] == vb[k]: continue
                if inside_y and box[0] <= x < box[2]: continue
                leaked += 1
                if va[k] != 0 and vb[k] == 0: holes += 1
        if leaked > NOISE:
            bad.append({'file': name, 'cell': i, 'leaked': leaked,
                        'holes': holes, 'own_rect': bool(box)})
    return bad

def main():
    allbad = []
    names = [os.path.splitext(os.path.basename(p))[0]
             for p in sorted(glob.glob(OUT + r'\*.dat'))]
    with cf.ProcessPoolExecutor() as ex:
        results = list(ex.map(audit, names))
    for name, bad in zip(names, results):
        if bad:
            worst = sorted(bad, key=lambda x: -x['leaked'])
            print(f'{name}: {len(bad)} cell(s) changed outside their own text box')
            for x in worst[:5]:
                print(f"    #{x['cell']}: {x['leaked']} px leaked"
                      f"{', ' + str(x['holes']) + ' turned transparent' if x['holes'] else ''}"
                      f"{'' if x['own_rect'] else '  (cell was never patched itself)'}")
        allbad += bad
    tot = sum(x['leaked'] for x in allbad)
    print(f'cells with leakage: {len(allbad)}   leaked pixels: {tot}')
    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        json.dump(allbad, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return allbad

if __name__ == '__main__':
    main()
