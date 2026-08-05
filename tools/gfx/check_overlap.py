# -*- coding: utf-8 -*-
"""Do the labelled cells of a file share tile data? If two cells touch the same
tiles, redrawing both corrupts each other."""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ncer
import label_tools as lt

def main(dat, labels_json):
    info = ncer.load(dat)
    entries = json.load(open(labels_json, encoding='utf-8-sig'))
    owner = {}
    clash = collections.Counter()
    pairs = []
    for e in entries:
        idx = e.get('cell')
        if idx is None or idx >= len(info['ncer']['banks']):
            continue
        r = lt.cell_pixels(info, idx)
        if r is None:
            continue
        W, H, src = r
        tiles = {src[y][x][0] for y in range(H) for x in range(W) if src[y][x]}
        for t in tiles:
            if t in owner and owner[t] != idx:
                clash[(owner[t], idx)] += 1
            else:
                owner[t] = idx
    print(f'{os.path.basename(dat)}: labels={len(entries)} clashing cell pairs={len(clash)}')
    for (a, b), n in clash.most_common(10):
        ja = next((x['jp'] for x in entries if x.get('cell') == a), '?')
        jb = next((x['jp'] for x in entries if x.get('cell') == b), '?')
        print(f'   cell {a}({ja}) and {b}({jb}) share {n} tiles')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
