# -*- coding: utf-8 -*-
"""NCER (cell) parsing + cell rendering from NCGR tiles. Lets us see complete
menu-label sprites so they can be read and later redrawn in Korean."""
import struct, os, sys
from PIL import Image
import nitro_gfx as ng

SHAPES = {
    (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
    (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
    (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64),
}

def parse_ncer(d, sub):
    for b in ng.blocks_of(d, sub):
        if b['name'] in ('CEBK', 'KBEC'):
            o = b['off']
            nbanks, btype = struct.unpack_from('<HH', d, o+8)
            bank_off = struct.unpack_from('<I', d, o+12)[0]
            mapping = struct.unpack_from('<I', d, o+16)[0]
            base = o + 8 + bank_off
            ent = 16 if btype == 1 else 8
            banks = []
            for k in range(nbanks):
                p = base + k*ent
                noam, attr = struct.unpack_from('<HH', d, p)
                oam_off = struct.unpack_from('<I', d, p+4)[0]
                banks.append({'noam': noam, 'attr': attr, 'oam_off': oam_off})
            oam_base = base + nbanks*ent
            for bk in banks:
                sprites = []
                for s in range(bk['noam']):
                    p = oam_base + bk['oam_off'] + s*6
                    if p + 6 > o + b['size']: break
                    a0, a1, a2 = struct.unpack_from('<HHH', d, p)
                    y = a0 & 0xFF
                    if y >= 128: y -= 256
                    shape = (a0 >> 14) & 3
                    x = a1 & 0x1FF
                    if x >= 256: x -= 512
                    size = (a1 >> 14) & 3
                    tile = a2 & 0x3FF
                    pal = (a2 >> 12) & 0xF
                    wh = SHAPES.get((shape, size))
                    if wh is None: continue
                    sprites.append({'x': x, 'y': y, 'w': wh[0], 'h': wh[1],
                                    'tile': tile, 'pal': pal})
                bk['sprites'] = sprites
            return {'banks': banks, 'mapping': mapping, 'btype': btype}
    return None

def load(path):
    d = open(path, 'rb').read()
    subs = ng.find_subs(d)
    pal, ncgr, ncer = None, None, None
    for s in subs:
        if s['type'] == 'NCLR' and pal is None:
            pal, _ = ng.read_nclr(d, s)
        elif s['type'] == 'NCGR' and ncgr is None:
            ncgr = ng.read_ncgr(d, s)
        elif s['type'] == 'NCER' and ncer is None:
            ncer = parse_ncer(d, s)
    pix, bpp, w, h, lin = ncgr if ncgr else (None,)*5
    if pix is None: return None
    if bpp == 4:
        vals = []
        for byte in pix:
            vals.append(byte & 0xF); vals.append(byte >> 4)
    else:
        vals = list(pix)
    return {'vals': vals, 'bpp': bpp, 'pal': pal, 'ncer': ncer, 'raw': d}

def render_cell(info, bank_idx, scale=2, boundary=1):
    """1D mapping: sprite tiles are stored consecutively from tile index."""
    bk = info['ncer']['banks'][bank_idx]
    sp = bk['sprites']
    if not sp: return None
    xs = [s['x'] for s in sp]; ys = [s['y'] for s in sp]
    xe = [s['x'] + s['w'] for s in sp]; ye = [s['y'] + s['h'] for s in sp]
    x0, y0, x1, y1 = min(xs), min(ys), max(xe), max(ye)
    W, H = x1 - x0, y1 - y0
    if W <= 0 or H <= 0 or W > 512 or H > 512: return None
    img = Image.new('RGB', (W, H), (255, 0, 255))
    px = img.load()
    vals = info['vals']
    pal = info['pal']
    for s in reversed(sp):
        tw, th = s['w'] // 8, s['h'] // 8
        base_tile = s['tile'] * boundary
        for ty in range(th):
            for tx in range(tw):
                t = base_tile + ty*tw + tx
                if (t+1)*64 > len(vals): continue
                for k in range(64):
                    v = vals[t*64 + k]
                    if v == 0: continue
                    X = s['x'] - x0 + tx*8 + (k % 8)
                    Y = s['y'] - y0 + ty*8 + (k // 8)
                    if 0 <= X < W and 0 <= Y < H:
                        px[X, Y] = pal[v] if pal and v < len(pal) else ((v*16,)*3)
    return img.resize((W*scale, H*scale), Image.NEAREST)

if __name__ == '__main__':
    path = sys.argv[1]
    OUT = r'C:\Users\Jay\AppData\Local\Temp\claude\D--nds-roms-NOBU2\9265263d-585d-4b0c-acac-1cfa176f7263\scratchpad\gfx\cells'
    os.makedirs(OUT, exist_ok=True)
    info = load(path)
    name = os.path.splitext(os.path.basename(path))[0]
    if not info or not info['ncer']:
        print('no NCER'); sys.exit()
    banks = info['ncer']['banks']
    print(f'{name}: banks={len(banks)} mapping=0x{info["ncer"]["mapping"]:X} btype={info["ncer"]["btype"]}')
    # contact-sheet of the first N cells
    imgs = []
    for i in range(min(len(banks), 60)):
        im = render_cell(info, i)
        if im: imgs.append((i, im))
    if imgs:
        cols = 6
        cw = max(im.width for _, im in imgs) + 4
        ch = max(im.height for _, im in imgs) + 4
        rows = (len(imgs) + cols - 1)//cols
        sheet = Image.new('RGB', (cols*cw, rows*ch), (30, 30, 30))
        for k, (i, im) in enumerate(imgs):
            sheet.paste(im, ((k % cols)*cw + 2, (k//cols)*ch + 2))
        sheet.save(f'{OUT}\\{name}_cells.png')
        print(f'  -> {name}_cells.png  ({len(imgs)} cells)')
        for i, im in imgs[:12]:
            print(f'     cell {i}: {im.width//2}x{im.height//2} sprites={len(banks[i]["sprites"])}')
