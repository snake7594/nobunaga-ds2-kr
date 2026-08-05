# -*- coding: utf-8 -*-
"""Original vs patched, side by side and magnified, for a list of cells.
Usage: python compare_cells.py <name> <out.png> <cell,cell,...> [scale]
"""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ncer
import label_tools as lt
import os as _os, sys as _sys
_sys.path[:0] = [_os.path.dirname(_os.path.abspath(__file__)),
                _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')]
from nobu2_paths import ROM_IN, ROM_OUT, WORK, FONT, DATA


def main(name, out, cells, scale=5):
    a = ncer.load(os.path.join(WORK, 'fs', 'obj', name + '.dat'))
    b = ncer.load(os.path.join(WORK, 'fs_gfx', 'obj', name + '.dat'))
    rows = []
    for c in cells:
        ia = lt.cell_image(a, c, scale=scale)
        ib = lt.cell_image(b, c, scale=scale)
        if ia is None or ib is None: continue
        rows.append((c, ia, ib))
    if not rows:
        print('nothing to draw'); return
    cw = max(max(i.width, j.width) for _, i, j in rows) + 10
    rh = max(max(i.height, j.height) for _, i, j in rows) + 8
    sheet = Image.new('RGB', (cw*2 + 60, rh*len(rows) + 16), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    d.text((56, 2), 'ORIGINAL', fill=(200, 200, 200))
    d.text((56 + cw, 2), 'PATCHED', fill=(160, 255, 160))
    for r, (c, ia, ib) in enumerate(rows):
        y = 16 + r*rh
        d.text((6, y + rh//2 - 4), f'#{c}', fill=(255, 255, 0))
        sheet.paste(ia.convert('RGB'), (50, y))
        sheet.paste(ib.convert('RGB'), (50 + cw, y))
    sheet.save(out)
    print(out, sheet.size)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(',')],
         int(sys.argv[4]) if len(sys.argv) > 4 else 5)
