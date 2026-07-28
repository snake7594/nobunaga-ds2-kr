# -*- coding: utf-8 -*-
"""Dump NCER cells of a .dat archive as contact sheets + manifest, for label transcription.

Usage: python dump_cells.py <path-to-dat> <out-dir>
Writes: <out-dir>/<name>_sheetNN.png  (grid of cells, each labeled with its index)
        <out-dir>/<name>_cells.json   (per-cell geometry: index, w, h, nsprites, tiles)
"""
import struct, os, sys, json
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nitro_gfx as ng
import ncer
import label_tools as lt

def main(path, outdir):
    os.makedirs(outdir, exist_ok=True)
    name = os.path.splitext(os.path.basename(path))[0]
    info = ncer.load(path)
    if not info or not info.get('ncer'):
        print(json.dumps({'file': name, 'cells': 0, 'note': 'no NCER'}))
        return
    banks = info['ncer']['banks']
    manifest = []
    imgs = []
    seen = {}
    for i, bk in enumerate(banks):
        r = lt.cell_pixels(info, i)
        if r is None:
            continue
        W, H, src = r
        im = lt.cell_image(info, i, scale=3)
        if im is None: continue
        # dedupe identical cells (animation frames share art)
        key = im.tobytes()
        if key in seen:
            manifest.append({'index': i, 'w': W, 'h': H, 'same_as': seen[key]})
            continue
        seen[key] = i
        tiles = sorted({s['tile'] for s in bk['sprites']})
        manifest.append({'index': i, 'w': W, 'h': H,
                         'nsprites': len(bk['sprites']), 'tiles': tiles[:8]})
        imgs.append((i, im))

    PER = 24
    for page in range((len(imgs) + PER - 1)//PER):
        chunk = imgs[page*PER:(page+1)*PER]
        cols = 4
        cw = max(im.width for _, im in chunk) + 8
        chh = max(im.height for _, im in chunk) + 20
        rows = (len(chunk) + cols - 1)//cols
        sheet = Image.new('RGB', (cols*cw, rows*chh), (20, 20, 20))
        dr = ImageDraw.Draw(sheet)
        for k, (idx, im) in enumerate(chunk):
            X = (k % cols)*cw + 4
            Y = (k//cols)*chh + 16
            sheet.paste(im, (X, Y))
            dr.text((X, Y - 14), f'#{idx}', fill=(255, 255, 0))
        sheet.save(os.path.join(outdir, f'{name}_sheet{page:02d}.png'))

    json.dump({'file': name, 'path': path, 'cells': manifest},
              open(os.path.join(outdir, f'{name}_cells.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(json.dumps({'file': name, 'unique_cells': len(imgs), 'total_banks': len(banks),
                      'sheets': (len(imgs) + PER - 1)//PER}, ensure_ascii=False))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
