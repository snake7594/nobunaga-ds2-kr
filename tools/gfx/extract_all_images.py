# -*- coding: utf-8 -*-
"""Extract EVERY image in the game's graphics archives to PNG.

For each .dat under fs/obj and fs/bg:
  * decode its palette (NCLR) and tile data (NCGR)
  * if it has cell data (NCER), render every unique cell as its own PNG
  * always also render the raw tile sheet, so nothing is missed

Writes:  <out>/<file>/cell_NNN.png , <out>/<file>/sheet.png
         <out>/manifest.json
"""
import os, sys, json, glob, hashlib
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nitro_gfx as ng
import ncer
import label_tools as lt

WORK = r'D:\nds\roms\NOBU2\_work'
OUT = WORK + r'\images'

def sheet_png(info, path_out, per_row=32, scale=2):
    vals, pal = info['vals'], info['pal']
    ntile = len(vals) // 64
    if ntile == 0:
        return None
    rows = (ntile + per_row - 1) // per_row
    img = Image.new('RGB', (per_row * 8, rows * 8), (255, 0, 255))
    px = img.load()
    for t in range(ntile):
        tx, ty = (t % per_row) * 8, (t // per_row) * 8
        for k in range(64):
            v = vals[t * 64 + k]
            px[tx + k % 8, ty + k // 8] = pal[v] if pal and v < len(pal) else ((v * 16,) * 3)
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(path_out)
    return img.size

def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    files = sorted(glob.glob(WORK + r'\fs\obj\*.dat') + glob.glob(WORK + r'\fs\bg\*.dat'))
    for path in files:
        if path.endswith('Info.dat'):
            continue
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            info = ncer.load(path)
        except Exception as e:
            print(f'  {name}: load failed ({e})')
            continue
        if not info:
            continue
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        entry = {'file': name, 'path': path, 'cells': [], 'sheet': None}

        # full tile sheet (catches art that no cell references)
        try:
            sz = sheet_png(info, os.path.join(d, 'sheet.png'))
            entry['sheet'] = {'png': f'{name}/sheet.png', 'size': sz}
        except Exception as e:
            print(f'  {name}: sheet failed ({e})')

        if info.get('ncer'):
            seen = {}
            for i in range(len(info['ncer']['banks'])):
                try:
                    im = lt.cell_image(info, i, scale=3)
                except Exception:
                    im = None
                if im is None:
                    continue
                h = hashlib.md5(im.tobytes()).hexdigest()
                if h in seen:
                    continue
                seen[h] = i
                fn = f'cell_{i:03d}.png'
                im.save(os.path.join(d, fn))
                entry['cells'].append({'index': i, 'png': f'{name}/{fn}',
                                       'w': im.width // 3, 'h': im.height // 3})
        manifest.append(entry)
        print(f'{name}: cells={len(entry["cells"])}')

    json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    total_cells = sum(len(m['cells']) for m in manifest)
    print()
    print(f'files: {len(manifest)}   unique cell images: {total_cells}')

if __name__ == '__main__':
    main()
