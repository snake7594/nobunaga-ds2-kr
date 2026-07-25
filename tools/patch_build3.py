# -*- coding: utf-8 -*-
"""v1.2 builder (safe): msgsec rebuilt but each file capped to its ORIGINAL size.
- Text may be redistributed WITHIN a file (rebuild remaps internal pointers)
- File size never grows -> no ROM repack, no FAT change, no fixed-buffer overflow
- If v2 (quality) texts overflow the file, worst offenders fall back to v1 then to original JP
"""
import json, glob, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import krtools, msg_rebuild
import snr_caps as _snr

WORK = r'D:\nds\roms\NOBU2\_work'
ROM_IN = r'D:\nds\roms\NOBU2\Nobunaga no Yabou DS 2 (Japan).nds'
ROM_OUT = r'D:\nds\roms\NOBU2\Nobunaga no Yabou DS 2 (Korean).nds'
ARM9_ROM_OFF = 0x4000
FONT_OFF = 0x178E64

CHAR_FIX = {'－':'−','·':'・','‧':'・','～':'〜','–':'―','—':'―','─':'―',
            '‘':"'",'’':"'",'“':'"','”':'"','⋯':'…'}
def fix(kr):
    for b, g in CHAR_FIX.items():
        if b in kr: kr = kr.replace(b, g)
    return kr

def enc_unit(kr, budgets, smap):
    lines = kr.split('{BR}')
    if len(lines) != len(budgets):
        raise ValueError('line count')
    parts = []
    for txt, b in zip(lines, budgets):
        e = krtools.encode_line(txt, smap)
        if len(e) > b:
            raise ValueError(f'overflow {len(e)}>{b}')
        parts.append(e)
    return b'\x0A'.join(parts)

def main():
    units_v1 = {u['id']: u for u in json.load(open(WORK + r'\units.json', encoding='utf-8'))}
    for ex in (r'\units_extra.json', r'\units_extra2.json', r'\units_extra3.json'):
        if os.path.exists(WORK + ex):
            for u in json.load(open(WORK + ex, encoding='utf-8')):
                units_v1[u['id']] = u
    units_v2 = {u['id']: u for u in json.load(open(WORK + r'\units_v2.json', encoding='utf-8'))}

    tr1, tr2 = {}, {}
    for p in sorted(glob.glob(WORK + r'\tr\out\out_*.json')):
        try:
            for it in json.load(open(p, encoding='utf-8')): tr1[it['id']] = it.get('kr', '')
        except Exception: pass
    for p in sorted(glob.glob(WORK + r'\tr\out2\out_*.json')):
        try:
            for it in json.load(open(p, encoding='utf-8')): tr2[it['id']] = it.get('kr', '')
        except Exception: pass

    # candidate texts per msgsec unit: prefer v2 (relaxed budget), then v1
    # budgets[uid] = line budgets to encode against
    cand = {}
    budgets_of = {}
    for uid, u in units_v2.items():
        budgets_of[uid] = u['lines']
        opts = []
        for src_tr, tag in ((tr2, 'v2'), (tr1, 'v1')):
            kr = src_tr.get(uid)
            if kr is None: continue
            kr = fix(kr)
            ok, _ = krtools.check_translation(kr, u['lines'])
            if ok: opts.append((tag, kr))
        if opts: cand[uid] = opts
    # msgsec units outside units_v2 (extras like ＜필요행동력): use their own v1 budgets
    for uid, u in units_v1.items():
        if not u['src'].startswith('msgsec') or uid in cand: continue
        kr = tr1.get(uid)
        if kr is None: continue
        kr = fix(kr)
        ok, _ = krtools.check_translation(kr, u['lines'])
        if ok:
            cand[uid] = [('v1', kr)]
            budgets_of[uid] = u['lines']

    # syllables from all candidates + in-place units
    sylls = set()
    for opts in cand.values():
        for _, kr in opts: sylls |= krtools.used_syllables(kr)

    safe = _snr.compute()
    inplace = {}
    for uid, u in units_v1.items():
        if u['src'].startswith('msgsec'): continue
        if u['src'] == 'common.snr':
            sc = safe.get(u['off'])
            if sc is not None:
                u = dict(u); u['cap'] = sc; u['lines'] = [sc]
        kr = tr1.get(uid)
        if kr is None: continue
        kr = fix(kr)
        ok, _ = krtools.check_translation(kr, u['lines'])
        if ok:
            inplace[uid] = (u, kr)
            sylls |= krtools.used_syllables(kr)

    c2i = krtools.load_code2idx()
    pool = [c for c, i in sorted(c2i.items()) if i >= 351]
    assert len(sylls) <= len(pool), f'pool exceeded {len(sylls)}>{len(pool)}'
    smap = {s: pool[i] for i, s in enumerate(sorted(sylls))}
    json.dump({s: hex(c) for s, c in smap.items()},
              open(WORK + r'\syllable_map.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

    arm9 = bytearray(open(WORK + r'\bin\arm9.bin', 'rb').read())
    for s, code in smap.items():
        arm9[FONT_OFF + c2i[code]*18: FONT_OFF + c2i[code]*18 + 18] = krtools.rows_to_bytes(krtools.render_glyph12(s))

    snr = bytearray(open(WORK + r'\fs\scenario\common.snr', 'rb').read())
    for uid, (u, kr) in inplace.items():
        enc = krtools.encode_unit(kr, u['lines'], smap, pad='null')
        buf = arm9 if u['src'] == 'arm9.bin' else snr
        off = u['off']
        for k in range(u['len'], len(enc)):
            assert buf[off + k] == 0
        buf[off: off + len(enc)] = enc
    print(f'font glyphs {len(smap)}, in-place units {len(inplace)}')

    # ---- msgsec: rebuild with size cap ----
    by_src = msg_rebuild.load_units()
    new_files = {}
    stats = {'v2': 0, 'v1': 0, 'jp': 0}
    for name in sorted(by_src):
        data = open(WORK + r'\fs\msg' + '\\' + name, 'rb').read()
        orig_size = len(data)
        units = by_src[name]
        # start with best (v2) choice for each unit
        choice = {}
        for u in units:
            opts = cand.get(u['id'])
            choice[u['id']] = 0 if opts else None   # index into opts, None = keep JP

        def build(choice):
            texts = {}
            for u in units:
                ci = choice.get(u['id'])
                if ci is None: continue
                tag, kr = cand[u['id']][ci]
                budgets = budgets_of[u['id']]
                texts[u['id']] = enc_unit(kr, budgets, smap)
            return msg_rebuild.rebuild(name, data, units, texts), texts

        nf, texts = build(choice)
        # demote worst offenders until it fits
        guard = 0
        while len(nf) > orig_size and guard < 20000:
            guard += 1
            # pick the unit with the largest growth over its original byte length
            worst, worst_gain = None, 0
            for u in units:
                ci = choice.get(u['id'])
                if ci is None: continue
                cur = len(texts[u['id']])
                nxt_len = None
                opts = cand[u['id']]
                if ci + 1 < len(opts):
                    tag, kr = opts[ci+1]
                    try:
                        nxt_len = len(enc_unit(kr, budgets_of[u['id']], smap))
                    except Exception:
                        nxt_len = None
                if nxt_len is None:
                    nxt_len = u['len']   # fall back to original JP bytes
                gain = cur - nxt_len
                if gain > worst_gain:
                    worst, worst_gain = u['id'], gain
            if worst is None:
                break
            opts = cand[worst]
            choice[worst] = choice[worst] + 1 if choice[worst] + 1 < len(opts) else None
            nf, texts = build(choice)
        assert len(nf) <= orig_size, f'{name}: cannot fit ({len(nf)} > {orig_size})'
        # pad tail to exact original size (append zeros after last record)
        nf = nf + b'\x00' * (orig_size - len(nf))
        new_files['/msg/' + name] = nf
        for u in units:
            ci = choice.get(u['id'])
            if ci is None: stats['jp'] += 1
            else: stats[cand[u['id']][ci][0]] += 1
        print(f'  {name}: {orig_size} -> {len(nf)} (fit, demotions={guard})')
    print('msgsec unit sources:', stats)

    # ---- ROM: in-place file writes (sizes unchanged!) ----
    rom = bytearray(open(ROM_IN, 'rb').read())
    manifest = json.load(open(WORK + r'\manifest.json'))
    rom[ARM9_ROM_OFF: ARM9_ROM_OFF + len(arm9)] = arm9
    for f in manifest['files']:
        p = f['path']
        if p in new_files:
            d = new_files[p]
            assert len(d) == f['size'], f'{p} size changed'
            rom[f['start']: f['start'] + len(d)] = d
        elif p == '/scenario/common.snr':
            assert len(snr) == f['size']
            rom[f['start']: f['start'] + len(snr)] = snr
    open(ROM_OUT, 'wb').write(rom)
    print('ROM written (no repack):', ROM_OUT)

if __name__ == '__main__':
    main()
