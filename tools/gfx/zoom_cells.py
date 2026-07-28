# -*- coding: utf-8 -*-
"""Zoom specific cells of a .dat archive for close reading."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ncer
import label_tools as lt

def main(path, outdir, indices, scale=8):
    os.makedirs(outdir, exist_ok=True)
    name = os.path.splitext(os.path.basename(path))[0]
    info = ncer.load(path)
    for i in indices:
        im = lt.cell_image(info, i, scale=scale)
        if im is None:
            print(f"cell {i}: none")
            continue
        outp = os.path.join(outdir, f'{name}_cell{i}_zoom{scale}.png')
        im.save(outp)
        print(outp, im.size)

if __name__ == '__main__':
    path = sys.argv[1]
    outdir = sys.argv[2]
    indices = [int(x) for x in sys.argv[3].split(',')]
    scale = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    main(path, outdir, indices, scale)
