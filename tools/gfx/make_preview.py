# -*- coding: utf-8 -*-
"""Build before/after preview sheets of every cell the graphics patch changed.

These go into the release so the change can be checked without running the game.
Usage: python make_preview.py <outdir>
"""
import os, sys, glob, json
import concurrent.futures as cf
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ncer
import label_tools as lt

WORK = r'D:\nds\roms\NOBU2\_work'
SRC = WORK + r'\fs\obj'
PATCHED = WORK + r'\fs_gfx\obj'
SCALE = 3
PER_SHEET = 24
GAP = 6

def changed_cells(a, b):
    """cells whose pixels differ, skipping cells that render identically to an
    earlier one (the archives repeat art across animation frames)"""
    out, seen = [], set()
    n = min(len(a['ncer']['banks']), len(b['ncer']['banks']))
    for i in range(n):
        ra = lt.cell_pixels(a, i)
        rb = lt.cell_pixels(b, i)
        if ra is None or rb is None: continue
        W, H, sa = ra
        va, vb = a['vals'], b['vals']
        sig = []
        diff = False
        for y in range(H):
            for x in range(W):
                s = sa[y][x]
                if s is None: continue
                k = s[0]*64 + s[1]
                sig.append(va[k])
                if va[k] != vb[k]: diff = True
        if not diff: continue
        key = (W, H, bytes(bytearray(v & 0xFF for v in sig)))
        if key in seen: continue
        seen.add(key)
        out.append(i)
    return out

def sheet(a, b, cells, title, path):
    rows = []
    for c in cells:
        ia = lt.cell_image(a, c, scale=SCALE)
        ib = lt.cell_image(b, c, scale=SCALE)
        if ia and ib: rows.append((c, ia, ib))
    if not rows: return False
    cw = max(max(i.width, j.width) for _, i, j in rows) + GAP
    rh = max(max(i.height, j.height) for _, i, j in rows) + GAP + 10
    img = Image.new('RGB', (cw*2 + 70, rh*len(rows) + 26), (20, 20, 24))
    d = ImageDraw.Draw(img)
    d.text((6, 4), title, fill=(255, 220, 120))
    d.text((62, 15), 'BEFORE', fill=(190, 190, 190))
    d.text((62 + cw, 15), 'AFTER', fill=(150, 255, 150))
    for r, (c, ia, ib) in enumerate(rows):
        y = 26 + r*rh
        d.text((6, y + rh//2 - 4), f'#{c}', fill=(255, 255, 0))
        img.paste(ia.convert('RGB'), (56, y))
        img.paste(ib.convert('RGB'), (56 + cw, y))
    img.save(path)
    return True

def one(args):
    name, outdir = args
    src = os.path.join(SRC, name + '.dat')
    p = os.path.join(PATCHED, name + '.dat')
    if not os.path.exists(src): return None
    a, b = ncer.load(src), ncer.load(p)
    if not a or not b or not a.get('ncer') or not b.get('ncer'): return None
    cells = changed_cells(a, b)
    if not cells: return None
    made = 0
    for s in range(0, len(cells), PER_SHEET):
        out = os.path.join(outdir, f'{name}_{s//PER_SHEET:02d}.png')
        if sheet(a, b, cells[s:s+PER_SHEET], f'{name}.dat', out):
            made += 1
    return {'file': name, 'cells': len(cells), 'sheets': made}

def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    index, total = [], 0
    names = [os.path.splitext(os.path.basename(p))[0]
             for p in sorted(glob.glob(PATCHED + r'\*.dat'))]
    with cf.ProcessPoolExecutor() as ex:
        for r in ex.map(one, [(n, outdir) for n in names]):
            if not r: continue
            index.append(r)
            total += r['cells']
            print(f"  {r['file']}: {r['cells']} cells -> {r['sheets']} sheet(s)")
    json.dump(index, open(os.path.join(outdir, 'index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'files: {len(index)}  changed cells: {total}')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else WORK + r'\preview')
