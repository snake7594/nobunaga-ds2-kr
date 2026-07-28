# -*- coding: utf-8 -*-
"""Apply every gfxlabels/*.json to its .dat, writing patched copies to fs_gfx/obj/.
Expands duplicate cells (animation frames sharing identical art) via the dump manifest."""
import os, sys, json, glob, shutil, subprocess

WORK = r'D:\nds\roms\NOBU2\_work'
SRC_OBJ = WORK + r'\fs\obj'
OUT_OBJ = WORK + r'\fs_gfx\obj'
LABELS = WORK + r'\gfxlabels'
DUMPS = [WORK + r'\gfxdump2', WORK + r'\gfxdump']
TOOLS = os.path.dirname(os.path.abspath(__file__))

def manifest_for(name):
    for d in DUMPS:
        p = os.path.join(d, f'{name}_cells.json')
        if os.path.exists(p):
            return json.load(open(p, encoding='utf-8'))
    return None

def expand(name, entries):
    man = manifest_for(name)
    if not man: return entries
    dup = {}
    for c in man['cells']:
        if 'same_as' in c:
            dup.setdefault(c['same_as'], []).append(c['index'])
    out = list(entries)
    have = {e['cell'] for e in entries}
    for e in entries:
        for d in dup.get(e['cell'], []):
            if d not in have:
                out.append({'cell': d, 'jp': e.get('jp', ''), 'kr': e['kr']})
                have.add(d)
    return out

def main():
    os.makedirs(OUT_OBJ, exist_ok=True)
    total_files = total_labels = 0
    for lp in sorted(glob.glob(LABELS + r'\*.json')):
        name = os.path.splitext(os.path.basename(lp))[0]
        if name.startswith('_'): continue
        dat = os.path.join(SRC_OBJ, name + '.dat')
        if not os.path.exists(dat):
            print(f'  skip {name}: no .dat'); continue
        try:
            entries = json.load(open(lp, encoding='utf-8-sig'))
        except Exception as e:
            print(f'  skip {name}: bad json ({e})'); continue
        entries = [e for e in entries if e.get('kr')]
        if not entries:
            continue
        # reject mojibake: a valid entry has Japanese in `jp` AND Hangul in `kr`.
        # Encoding-damaged files show Hangul-looking bytes in `jp` and '?' in `kr`.
        def is_jp(s):
            return any('\u3041' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff'
                       or '\uff10' <= c <= '\uff5a' for c in s)
        def is_kr(s):
            return any('\uac00' <= c <= '\ud7a3' for c in s)
        good = [e for e in entries
                if is_jp(e.get('jp', '')) and is_kr(e['kr']) and '?' not in e['kr']]
        if not good:
            print(f'  skip {name}: encoding-damaged or unusable'); continue
        if len(good) < len(entries):
            print(f'  {name}: dropped {len(entries)-len(good)} damaged entries')
        entries = good
        entries = expand(name, entries)
        tmp = os.path.join(WORK, '_labels_tmp.json')
        json.dump(entries, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
        out = os.path.join(OUT_OBJ, name + '.dat')
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'apply_labels.py'), dat, tmp, out],
                           capture_output=True, text=True, encoding='utf-8')
        print(f'  {name}: {r.stdout.strip()}')
        if os.path.exists(out):
            total_files += 1
            total_labels += len(entries)
    print(f'files patched: {total_files}, labels applied: {total_labels}')

if __name__ == '__main__':
    main()
