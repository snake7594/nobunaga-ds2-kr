# -*- coding: utf-8 -*-
"""Apply Korean label translations into the sprite graphics of a .dat archive.

For each {cell, jp, kr} entry:
  - locate the cell's text region automatically (interior minus bevel)
  - detect ink / background palette indices from the interior histogram
  - clear the text box and draw the Korean text with Galmuri, sized to fit
  - write the modified NCGR pixel data back into the .dat

Usage: python apply_labels.py <dat-in> <labels.json> <dat-out>
"""
import os, sys, json, collections
from PIL import Image, ImageFont, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ncer
import label_tools as lt

FONT = r'D:\nds\files (1)\Galmuri11.ttf'
INSET = 5          # skip the 3D bevel when analysing the interior
MIN_INK = 8        # a cell needs at least this many non-bg pixels to be "text"

def analyse(info, idx):
    """return (W,H,src,bg,ink,box) or None"""
    r = lt.cell_pixels(info, idx)
    if r is None: return None
    W, H, src = r
    if W < 12 or H < 10: return None
    vals = info['vals']
    hist = collections.Counter()
    for y in range(INSET, H - INSET):
        for x in range(INSET, W - INSET):
            s = src[y][x]
            if s: hist[vals[s[0]*64 + s[1]]] += 1
    if len(hist) < 2: return None
    bg = hist.most_common(1)[0][0]
    ink = hist.most_common(2)[1][0]
    pts = [(x, y) for y in range(INSET, H - INSET) for x in range(INSET, W - INSET)
           if src[y][x] and vals[src[y][x][0]*64 + src[y][x][1]] != bg]
    if len(pts) < MIN_INK: return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    box = (min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
    return W, H, src, bg, ink, box

def draw_text(info, idx, text, W, H, src, bg, ink, box):
    bx, by, bw, bh = box
    # try decreasing font sizes until the text fits the box width
    chosen = None
    for size in (13, 12, 11, 10, 9, 8):
        f = ImageFont.truetype(FONT, size)
        probe = Image.new('L', (1, 1))
        wpx = ImageDraw.Draw(probe).textlength(text, font=f)
        if wpx <= bw:
            chosen = (f, size, wpx); break
    if chosen is None:
        f = ImageFont.truetype(FONT, 8)
        wpx = ImageDraw.Draw(Image.new('L', (1, 1))).textlength(text, font=f)
        chosen = (f, 8, wpx)
    f, size, wpx = chosen
    img = Image.new('L', (bw, bh), 255)
    d = ImageDraw.Draw(img)
    d.text(((bw - wpx) // 2, max(0, (bh - size) // 2)), text, font=f, fill=0)
    ipx = img.load()
    vals = info['vals']
    for y in range(bh):
        for x in range(bw):
            X, Y = bx + x, by + y
            if not (0 <= X < W and 0 <= Y < H): continue
            s = src[Y][X]
            if s is None: continue
            vals[s[0]*64 + s[1]] = ink if ipx[x, y] < 128 else bg

def main(dat_in, labels_json, dat_out):
    entries = json.load(open(labels_json, encoding='utf-8-sig'))
    info = ncer.load(dat_in)
    if not info or not info.get('ncer'):
        print(json.dumps({'error': 'no NCER', 'file': dat_in})); return 1
    nbanks = len(info['ncer']['banks'])
    done, skipped = 0, []
    for e in entries:
        idx = e.get('cell')
        kr = (e.get('kr') or '').strip()
        if idx is None or not kr or idx >= nbanks:
            skipped.append((idx, 'bad entry')); continue
        a = analyse(info, idx)
        if a is None:
            skipped.append((idx, 'no text region')); continue
        W, H, src, bg, ink, box = a
        draw_text(info, idx, kr, W, H, src, bg, ink, box)
        done += 1
    ok = lt.save_ncgr(info, dat_in, dat_out)
    print(json.dumps({'file': os.path.basename(dat_in), 'applied': done,
                      'skipped': len(skipped), 'written': bool(ok)}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
