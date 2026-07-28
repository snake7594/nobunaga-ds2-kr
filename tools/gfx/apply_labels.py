# -*- coding: utf-8 -*-
"""Apply Korean label translations into the sprite graphics of a .dat archive.

Two things make this harder than "draw text into a box":

1. The UI sprites are built from a shared GLYPH ATLAS - 確定 and 確認 both point
   at the tiles of 確.  Drawing whole strings per cell makes neighbouring labels
   overwrite each other.  So text is laid out CHARACTER BY CHARACTER into equal
   columns and each tile is claimed by exactly one character: a shared glyph
   then always receives the same Hangul syllable (hanja readings are 1:1).
   Tiles that two different characters would claim are left untouched.

2. Galmuri11 is a PIXEL font.  It must be rendered without antialiasing and at
   its native 12px size, otherwise thresholding shreds the strokes.

Usage: python apply_labels.py <dat-in> <labels.json> <dat-out>
"""
import os, sys, json, collections
from PIL import Image, ImageFont, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ncer
import label_tools as lt

FONT = r'D:\nds\files (1)\Galmuri11.ttf'
# Galmuri11 is pixel-perfect at multiples of 12, so 24 for tall buttons and 12
# everywhere else; the in-between sizes are a last resort for cramped boxes.
SIZES = (24, 12, 11, 10, 9, 8)
INSET = 2
MIN_INK = 8
_fonts = {}

def font(size):
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(FONT, size)
    return _fonts[size]

def measure(text, size):
    return font(size).getmask(text, mode='1').size[0]

def analyse(info, idx):
    """(W,H,src,bg,ink,box) - box is the bbox of the TEXT ink only, so frames,
    borders and gradients drawn in other colours stay out of the layout.

    Buttons here are ornate (bevelled frame over a gradient fill), so the text
    is not simply "the second most common colour" - it is the BRIGHTEST colour
    that covers a meaningful number of pixels well inside the frame."""
    r = lt.cell_pixels(info, idx)
    if r is None: return None
    W, H, src = r
    if W < 12 or H < 10: return None
    inx = max(INSET, W // 8)
    iny = max(INSET, H // 6)
    if W - 2*inx < 8 or H - 2*iny < 8:
        inx = iny = INSET
    vals, pal = info['vals'], info['pal']
    hist = collections.Counter(); banks = collections.Counter()
    for y in range(iny, H - iny):
        for x in range(inx, W - inx):
            s = src[y][x]
            if s:
                hist[vals[s[0]*64 + s[1]]] += 1
                banks[s[2] if len(s) > 2 else 0] += 1
    if len(hist) < 2: return None
    bg = hist.most_common(1)[0][0]
    pb = banks.most_common(1)[0][0] if banks else 0

    def lum(v):
        pi = pb*16 + v
        if not pal or pi >= len(pal): return v * 16
        r_, g_, b_ = pal[pi]
        return 0.30*r_ + 0.59*g_ + 0.11*b_

    cands = [v for v, n in hist.items() if v != bg and n >= MIN_INK]
    if not cands: return None
    ink = max(cands, key=lum)

    # Measure the text over the WHOLE cell, not the inset window: wide banner
    # labels have no frame and the inset would clip their first and last glyph.
    # A frame instead shows up as a row or column that is almost solid ink, so
    # drop those lines before taking the bounding box.
    ipx = [[False]*W for _ in range(H)]
    solid = [[False]*W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            s = src[y][x]
            if s is None: continue
            v = vals[s[0]*64 + s[1]]
            solid[y][x] = v != 0
            ipx[y][x] = v == ink
    cx = [x for x in range(W) if any(solid[y][x] for y in range(H))]
    cy = [y for y in range(H) if any(solid[y][x] for x in range(W))]
    if not cx or not cy: return None
    cx0, cx1, cy0, cy1 = cx[0], cx[-1], cy[0], cy[-1]

    def run(cells):
        best = cur = 0
        for c in cells:
            cur = cur + 1 if c else 0
            best = max(best, cur)
        return best
    def frame_at(fixed_is_col, start, step, span, need):
        """innermost near-edge line that is a continuous stroke - a frame, not text"""
        found = None
        for d in range(5):
            i = start + d*step
            if not (0 <= i < (W if fixed_is_col else H)): break
            line = ([ipx[y][i] for y in range(cy0, cy1 + 1)] if fixed_is_col
                    else [ipx[i][x] for x in range(cx0, cx1 + 1)])
            if run(line) >= need: found = i
        return found
    hspan, vspan = cx1 - cx0 + 1, cy1 - cy0 + 1
    fl = frame_at(True, cx0, 1, vspan, max(8, int(vspan * 0.7)))
    fr = frame_at(True, cx1, -1, vspan, max(8, int(vspan * 0.7)))
    ft = frame_at(False, cy0, 1, hspan, max(8, int(hspan * 0.7)))
    fb = frame_at(False, cy1, -1, hspan, max(8, int(hspan * 0.7)))
    rx0 = (fl + 1) if fl is not None else cx0
    rx1 = (fr - 1) if fr is not None else cx1
    ry0 = (ft + 1) if ft is not None else cy0
    ry1 = (fb - 1) if fb is not None else cy1
    if rx1 - rx0 < 8 or ry1 - ry0 < 6: return None

    pts = [(x, y) for y in range(ry0, ry1 + 1) for x in range(rx0, rx1 + 1) if ipx[y][x]]
    if len(pts) < MIN_INK: return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    box = (min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
    if box[2] < 6 or box[3] < 6: return None
    room = (rx0, ry0, rx1 - rx0 + 1, ry1 - ry0 + 1)
    framed = any(f is not None for f in (fl, fr, ft, fb))
    bgs = backgrounds(src, W, H, vals, box, room, ink, bg)
    erase = grow(src, W, H, vals, box, room, set(bgs.values()) | {bg, 0})
    # If the detected text swallows a framed button whole, the colour analysis
    # has latched onto the plate rather than the lettering; repainting it would
    # wipe the button.  Leave such a cell alone.
    if framed and erase[2]*erase[3] >= 0.85 * room[2]*room[3]: return None
    # If a lot of lettering on the same line survives outside the repaint area,
    # the result would read half Korean, half Japanese.  Better to leave it.
    bgset = set(bgs.values()) | {bg, 0}
    left = 0
    for y in range(erase[1], min(H, erase[1] + erase[3])):
        for x in range(rx0, rx1 + 1):
            if erase[0] <= x < erase[0] + erase[2]: continue
            s = src[y][x]
            if s and vals[s[0]*64 + s[1]] not in bgset: left += 1
    if left > 60: return None
    return W, H, src, bgs, bg, ink, box, room, erase

def grow(src, W, H, vals, box, room, bgset, limit=24):
    """Widen the bbox until it covers the glyph's decoration.  The layout box is
    the bbox of the core colour only; these labels are drawn with a coloured
    outline and swashes that reach past it, and leaving those behind puts stray
    strokes around the Hangul."""
    x0, y0, x1, y1 = box[0], box[1], box[0] + box[2], box[1] + box[3]
    rx, ry, rw, rh = room
    rx1, ry1 = rx + rw, ry + rh
    def dirty(pts):
        for x, y in pts:
            if 0 <= x < W and 0 <= y < H:
                s = src[y][x]
                if s and vals[s[0]*64 + s[1]] not in bgset: return True
        return False
    for _ in range(limit):
        moved = False
        if x0 > rx and dirty([(x0 - 1, y) for y in range(y0, y1)]):
            x0 -= 1; moved = True
        if x1 < rx1 and dirty([(x1, y) for y in range(y0, y1)]):
            x1 += 1; moved = True
        if y0 > ry and dirty([(x, y0 - 1) for x in range(x0, x1)]):
            y0 -= 1; moved = True
        if y1 < ry1 and dirty([(x, y1) for x in range(x0, x1)]):
            y1 += 1; moved = True
        if not moved: break
    return (x0, y0, x1 - x0, y1 - y0)

def backgrounds(src, W, H, vals, box, room, ink, bg):
    """Background colour PER ROW.  Buttons are painted with a vertical gradient,
    so erasing the kanji with one flat colour leaves a visible band - and when
    the plate is smaller than the cell, the cell-wide favourite is the
    transparent margin, which would punch a hole straight through the button."""
    bx, by, bw, bh = box
    rx, ry, rw, rh = room
    sides = list(range(rx, bx)) + list(range(bx + bw, rx + rw))
    # When the text spans the full width there is nothing beside it to sample.
    # Fall back to the cell's outer ring, which is always outside the lettering
    # - never to colours inside the text row, which are the glyph's own outline
    # and shadow and would erase the kanji into a dark bar.
    edge = collections.Counter()
    for y in range(max(0, by - 6), min(H, by + bh + 6)):
        for x in range(max(0, bx - 6), min(W, bx + bw + 6)):
            if bx - 2 <= x < bx + bw + 2 and by - 2 <= y < by + bh + 2:
                continue                       # too close - that is the outline
            s = src[y][x]
            if s:
                v = vals[s[0]*64 + s[1]]
                if v != ink: edge[v] += 1
    vfill = edge.most_common(1)[0][0] if edge else bg
    out = {}
    for y in range(max(0, min(ry, by - PAD)), min(H, max(ry + rh, by + bh + PAD))):
        beside = collections.Counter()
        for x in sides:
            if 0 <= x < W and src[y][x]:
                v = vals[src[y][x][0]*64 + src[y][x][1]]
                if v != ink: beside[v] += 1
        # a couple of pixels beside the text are just the outer glyph's outline;
        # only a real margin tells us the plate colour for this row
        if len(sides) >= 12 and sum(beside.values()) >= 12:
            out[y] = beside.most_common(1)[0][0]; continue
        out[y] = vfill
    return out

def layout(text, box, room):
    """split the ink bbox into equal character columns, sized as large as the
    space inside the frame allows.  Returns (size, [(rect, char), ...])."""
    bx, by, bw, bh = box
    _, ry, _, rh = room
    n = len(text)
    colw = bw / n
    size = SIZES[-1]
    for s in SIZES:
        if s <= rh and all(measure(c, s) <= colw + 1 for c in text):
            size = s; break
    dh = min(rh, max(bh, size))
    dy = max(ry, min(by + (bh - dh)//2, ry + rh - dh))
    out = []
    for i, ch in enumerate(text):
        x0 = bx + int(round(i * bw / n))
        x1 = bx + int(round((i + 1) * bw / n))
        out.append(((x0, dy, max(1, x1 - x0), dh), ch))
    return size, out

def pixels_in(src, W, H, col):
    """the atlas pixels (tile*64+k) a column covers - pixel granularity, because
    neighbouring columns legitimately share the tiles at their border"""
    x0, y0, w, h = col
    return {src[y][x][0]*64 + src[y][x][1]
            for y in range(max(0, y0), min(H, y0 + h))
            for x in range(max(0, x0), min(W, x0 + w))
            if src[y][x]}

def render(text, bw, bh, size):
    """bilevel Galmuri render, centred in a bw x bh box"""
    w = measure(text, size)
    while w > bw and size > SIZES[-1]:
        size = next(s for s in SIZES if s < size)
        w = measure(text, size)
    img = Image.new('L', (max(bw, 1), max(bh, 1)), 255)
    d = ImageDraw.Draw(img)
    d.fontmode = '1'                      # no antialiasing - keep pixel strokes intact
    d.text(((bw - w) // 2, (bh - size) // 2), text, font=font(size), fill=0)
    return img

PAD = 3      # the original glyph's soft edge sits just outside the ink bbox

def paint(info, src, W, H, region, canvas, ink, bgs, bg, claimed, blocked, own, mine):
    """write the rendered region; never touch a pixel another character owns"""
    rx, ry = region
    px = canvas.load(); vals = info['vals']
    for y in range(canvas.height):
        for x in range(canvas.width):
            X, Y = rx + x, ry + y
            if not (0 <= X < W and 0 <= Y < H): continue
            s = src[Y][X]
            if s is None or s[0] not in own: continue
            key = s[0]*64 + s[1]
            if key in claimed: continue
            if key in blocked and s[0] not in mine: continue
            claimed.add(key)
            fill = bgs.get(Y, bg)
            v = ink if px[x, y] < 128 else fill
            # A transparent pixel must stay transparent.  The same atlas tile is
            # reused by other cells where it shows through as empty space, so
            # touching it paints stray marks across the screen.  The exception is
            # a label that genuinely sits on transparency (banner titles): there
            # the row's own background IS transparent, so strokes may be added.
            if vals[key] == 0 and fill != 0: continue
            vals[key] = v

def main(dat_in, labels_json, dat_out):
    entries = json.load(open(labels_json, encoding='utf-8-sig'))
    info = ncer.load(dat_in)
    if not info or not info.get('ncer'):
        print(json.dumps({'error': 'no NCER', 'file': os.path.basename(dat_in)})); return 1
    nbanks = len(info['ncer']['banks'])

    # ---- pass 1: work out what each character column wants, and where two
    #      different characters would fight over the same atlas tiles
    plans = []
    want = collections.defaultdict(set)      # tile -> {char}
    for e in entries:
        idx = e.get('cell')
        jp = (e.get('jp') or '').strip()
        kr = (e.get('kr') or '').strip()
        if idx is None or idx >= nbanks or not kr: continue
        a = analyse(info, idx)
        if a is None: continue
        W, H, src, bgs, bg, ink, box, room, erase = a
        # Some banks are mid-animation frames that draw only a sliver of the
        # button.  Their text box is far too narrow for the label, and writing
        # into it both looks wrong and damages the tiles the full frame shares.
        if box[2] < 6 * len(kr.replace('\n', '')): continue
        size, cols = layout(kr, box, room)
        if not (jp and len(kr) == len(jp) and len(kr) > 1):
            cols = [(cols[0][0][:2] + (box[2], cols[0][0][3]), kr)]
        items = []
        for col, ch in cols:
            ps = pixels_in(src, W, H, col)
            for p in ps: want[p].add(ch)
            items.append((col, ch, ps))
        plans.append((idx, W, H, src, bgs, bg, ink, size, room, erase, items))

    conflicted = {p for p, cs in want.items() if len(cs) > 1}

    # ---- pass 2: fix the repaint rectangle of every label that survived
    jobs = []
    skipped = 0
    for idx, W, H, src, bgs, bg, ink, size, room, erase, items in plans:
        # all or nothing: a half-translated word ("데모플レ이") is worse than
        # leaving the original, so one contested character vetoes the label
        if any(ps & conflicted for _, _, ps in items):
            skipped += 1; continue
        cols = [(c, ch) for c, ch, ps in items]
        # repaint the accepted columns plus a small pad, so the original glyph's
        # soft outline does not survive around the new Hangul.  Stay inside the
        # frame: bleeding into the transparent margin leaves blobs on screen.
        rox, roy, row_, roh = room
        rx = max(rox, min([c[0] for c, _ in cols] + [erase[0]]) - PAD)
        rx1 = min(rox + row_, max([c[0] + c[2] for c, _ in cols] + [erase[0] + erase[2]]) + PAD)
        ry = max(roy, min([c[1] for c, _ in cols] + [erase[1]]) - PAD)
        ry1 = min(roy + roh, max([c[1] + c[3] for c, _ in cols] + [erase[1] + erase[3]]) + PAD)
        if rx1 <= rx or ry1 <= ry: continue
        jobs.append((idx, W, H, src, bgs, bg, ink, size, cols, (rx, ry, rx1, ry1)))

    # ---- pass 3: a cell layers a text sprite over a background sprite that
    # other labelled cells reuse at a different offset.  Any atlas pixel that
    # such a cell shows outside its own text rectangle must stay untouched, or
    # writes leak out as stray marks elsewhere on the screen.
    exposed = set()
    for _, W, H, src, _, _, _, _, _, (rx, ry, rx1, ry1) in jobs:
        for y in range(H):
            inside = ry <= y < ry1
            for x in range(W):
                s = src[y][x]
                if s is None: continue
                if inside and rx <= x < rx1: continue
                exposed.add(s[0]*64 + s[1])
    blocked = conflicted | exposed

    # ---- pass 4: draw
    claimed = set()
    drawn = 0
    vals = info['vals']
    for idx, W, H, src, bgs, bg, ink, size, cols, (rx, ry, rx1, ry1) in jobs:
        canvas = Image.new('L', (rx1 - rx, ry1 - ry), 255)
        for c, ch in cols:
            canvas.paste(render(ch, c[2], c[3], size), (c[0] - rx, c[1] - ry))
            drawn += 1
        bgset = set(bgs.values()) | {bg, 0}
        own = set(); art = collections.Counter()
        for y in range(max(0, ry), min(H, ry1)):
            for x in range(max(0, rx), min(W, rx1)):
                s = src[y][x]
                if s is None: continue
                own.add(s[0])
                if vals[s[0]*64 + s[1]] not in bgset: art[s[0]] += 1
        # tiles that carry this label's own artwork are ours to rewrite; the
        # exposure guard is for background tiles borrowed from another cell
        mine = {t for t in own if art[t] >= 2}
        paint(info, src, W, H, (rx, ry), canvas, ink, bgs, bg, claimed,
              blocked, own, mine)
    ok = lt.save_ncgr(info, dat_in, dat_out)
    print(json.dumps({'file': os.path.basename(dat_in), 'cells': len(plans),
                      'glyphs': drawn, 'skipped_conflict': skipped,
                      'written': bool(ok)}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
