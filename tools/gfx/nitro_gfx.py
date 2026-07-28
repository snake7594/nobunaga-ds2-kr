# -*- coding: utf-8 -*-
"""Decode NitroSDK graphics inside the game's .dat archives and render tilesets to PNG."""
import struct, os, sys
from PIL import Image

MAGICS = {b'RLCN': 'NCLR', b'RGCN': 'NCGR', b'RCSN': 'NSCR', b'RECN': 'NCER', b'RNAN': 'NANR'}

def find_subs(d):
    """scan every 4-byte boundary for Nitro sub-file headers"""
    subs = []
    for i in range(0, len(d) - 16, 4):
        m = d[i:i+4]
        if m in MAGICS:
            bom, ver = struct.unpack_from('<HH', d, i+4)
            size = struct.unpack_from('<I', d, i+8)[0]
            hsize, nblk = struct.unpack_from('<HH', d, i+12)
            if bom == 0xFEFF and hsize == 0x10 and 0x10 < size <= len(d) - i:
                subs.append({'off': i, 'type': MAGICS[m], 'size': size, 'blocks': nblk})
    return subs

def blocks_of(d, sub):
    """iterate blocks inside a sub-file: {name, off, size}"""
    out = []
    p = sub['off'] + 0x10
    end = sub['off'] + sub['size']
    for _ in range(sub['blocks']):
        if p + 8 > end: break
        name = d[p:p+4][::-1].decode('ascii', 'replace')
        sz = struct.unpack_from('<I', d, p+4)[0]
        if sz <= 0 or p + sz > end + 4: break
        out.append({'name': name, 'off': p, 'size': sz})
        p += sz
    return out

def read_nclr(d, sub):
    """PLTT: +8 bitDepth(3=16col,4=256col), +12 pad, +16 dataSize, +20 colorsPerPal, +24 data"""
    for b in blocks_of(d, sub):
        if b['name'] in ('PLTT', 'TTLP'):
            o = b['off']
            depth = struct.unpack_from('<I', d, o+8)[0]
            datsz = struct.unpack_from('<I', d, o+16)[0]
            base = o + 24
            avail = min(datsz, b['size'] - 24)
            pal = []
            for k in range(avail // 2):
                v = struct.unpack_from('<H', d, base + k*2)[0]
                pal.append(((v & 31)*255//31, ((v >> 5) & 31)*255//31, ((v >> 10) & 31)*255//31))
            return pal, (8 if depth == 4 else 4)
    return None, None

def read_ncgr(d, sub):
    """CHAR: +8 nTilesY, +10 nTilesX, +12 depth, +16 mapType, +20 tiledFlag,
             +24 dataSize, +28 dataOffset(=0x18) -> data at off+8+dataOffset"""
    for b in blocks_of(d, sub):
        if b['name'] in ('CHAR', 'RAHC'):
            o = b['off']
            ny, nx = struct.unpack_from('<HH', d, o+8)
            depth = struct.unpack_from('<I', d, o+12)[0]
            tiled = struct.unpack_from('<I', d, o+20)[0]
            datsz = struct.unpack_from('<I', d, o+24)[0]
            datoff = struct.unpack_from('<I', d, o+28)[0]
            start = o + 8 + datoff
            bpp = 8 if depth == 4 else 4
            return d[start:start+datsz], bpp, nx, ny, (tiled & 1)
    return None, None, None, None, None

def render_meta16(pix, bpp, pal, out_path, per_row=16, scale=2):
    """render assuming 4 consecutive 8x8 tiles form one 16x16 sprite char (2x2 order)"""
    if bpp == 4:
        vals = []
        for byte in pix:
            vals.append(byte & 0xF); vals.append(byte >> 4)
    else:
        vals = list(pix)
    ntile = len(vals) // 64
    nchar = ntile // 4
    rows = (nchar + per_row - 1) // per_row
    img = Image.new('RGB', (per_row*17, rows*17), (255, 0, 255))
    px = img.load()
    for c in range(nchar):
        cx = (c % per_row) * 17
        cy = (c // per_row) * 17
        for sub in range(4):
            t = c*4 + sub
            ox = (sub % 2) * 8
            oy = (sub // 2) * 8
            for k in range(64):
                v = vals[t*64 + k]
                col = pal[v] if pal and v < len(pal) else ((v*16,)*3)
                px[cx + ox + (k % 8), cy + oy + (k // 8)] = col
    img = img.resize((img.width*scale, img.height*scale), Image.NEAREST)
    img.save(out_path)
    return nchar

def render_tiles(pix, bpp, pal, out_path, per_row=32, scale=2):
    """render 8x8 tiles in a grid"""
    if bpp == 4:
        vals = []
        for byte in pix:
            vals.append(byte & 0xF); vals.append(byte >> 4)
    else:
        vals = list(pix)
    ntile = len(vals) // 64
    rows = (ntile + per_row - 1) // per_row
    img = Image.new('RGB', (per_row*8, rows*8), (255, 0, 255))
    px = img.load()
    for t in range(ntile):
        tx = (t % per_row) * 8
        ty = (t // per_row) * 8
        for k in range(64):
            v = vals[t*64 + k]
            c = pal[v] if pal and v < len(pal) else ((v*16,)*3)
            px[tx + (k % 8), ty + (k // 8)] = c
    img = img.resize((img.width*scale, img.height*scale), Image.NEAREST)
    img.save(out_path)
    return ntile

if __name__ == '__main__':
    OUT = r'C:\Users\Jay\AppData\Local\Temp\claude\D--nds-roms-NOBU2\9265263d-585d-4b0c-acac-1cfa176f7263\scratchpad\gfx'
    os.makedirs(OUT, exist_ok=True)
    for path in sys.argv[1:]:
        d = open(path, 'rb').read()
        subs = find_subs(d)
        name = os.path.splitext(os.path.basename(path))[0]
        print(f'--- {name}')
        pal = None; bpp_p = None
        for s in subs:
            if s['type'] == 'NCLR':
                pal, bpp_p = read_nclr(d, s)
                print(f"    NCLR +0x{s['off']:X} colors={len(pal) if pal else 0} bpp={bpp_p}")
        ci = 0
        for s in subs:
            if s['type'] == 'NCGR':
                pix, bpp, w, h, linear = read_ncgr(d, s)
                if pix is None: continue
                n = render_tiles(pix, bpp, pal, f'{OUT}\\{name}_{ci}.png')
                print(f"    NCGR +0x{s['off']:X} bpp={bpp} tiles={n} linear={linear} -> {name}_{ci}.png")
                ci += 1
        for s in subs:
            if s['type'] == 'NSCR':
                print(f"    NSCR +0x{s['off']:X} size=0x{s['size']:X}")
