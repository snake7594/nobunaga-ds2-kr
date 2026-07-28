# -*- coding: utf-8 -*-
"""v1.3 builder: expansion WITHIN the game's proven message-buffer limit.
- Cap every msgsec file at MAX_ORIG (= largest original msgsec size, 16137 B),
  which the game demonstrably loads, so no buffer overflow.
- Files that grew are relocated into the ROM's UNUSED TAIL; every other file
  (sound, graphics, movie, snr) stays byte-identical at its original offset.
- Only the grown files' FAT entries, header used-size and header CRC change.
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
            raise ValueError('overflow')
        parts.append(e)
    return b'\x0A'.join(parts)

def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc

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

    cand, budgets_of = {}, {}
    for uid, u in units_v2.items():
        budgets_of[uid] = u['lines']
        opts = []
        for src_tr, tag in ((tr2, 'v2'), (tr1, 'v1')):
            kr = src_tr.get(uid)
            if kr is None: continue
            kr = fix(kr)
            if krtools.check_translation(kr, u['lines'])[0]:
                opts.append((tag, kr))
        if opts: cand[uid] = opts
    for uid, u in units_v1.items():
        if not u['src'].startswith('msgsec') or uid in cand: continue
        kr = tr1.get(uid)
        if kr is None: continue
        kr = fix(kr)
        if krtools.check_translation(kr, u['lines'])[0]:
            cand[uid] = [('v1', kr)]
            budgets_of[uid] = u['lines']

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
        if krtools.check_translation(kr, u['lines'])[0]:
            inplace[uid] = (u, kr)
            sylls |= krtools.used_syllables(kr)

    c2i = krtools.load_code2idx()
    pool = [c for c, i in sorted(c2i.items()) if i >= 351]
    assert len(sylls) <= len(pool), f'pool exceeded {len(sylls)}'
    smap = {s: pool[i] for i, s in enumerate(sorted(sylls))}
    json.dump({s: hex(c) for s, c in smap.items()},
              open(WORK + r'\syllable_map.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

    arm9 = bytearray(open(WORK + r'\bin\arm9.bin', 'rb').read())
    for s, code in smap.items():
        i = c2i[code]
        arm9[FONT_OFF + i*18: FONT_OFF + i*18 + 18] = krtools.rows_to_bytes(krtools.render_glyph12(s))
    snr = bytearray(open(WORK + r'\fs\scenario\common.snr', 'rb').read())
    for uid, (u, kr) in inplace.items():
        enc = krtools.encode_unit(kr, u['lines'], smap, pad='null')
        buf = arm9 if u['src'] == 'arm9.bin' else snr
        off = u['off']
        for k in range(u['len'], len(enc)):
            assert buf[off + k] == 0
        buf[off: off + len(enc)] = enc
    print(f'font glyphs {len(smap)}, in-place units {len(inplace)}')

    manifest = json.load(open(WORK + r'\manifest.json'))
    msg_sizes = {os.path.basename(f['path']): f['size']
                 for f in manifest['files'] if '/msg/msgsec' in f['path']}
    MAX_ORIG = max(msg_sizes.values())
    print(f'message-buffer safe cap = {MAX_ORIG} bytes (largest original msgsec)')

    by_src = msg_rebuild.load_units()
    new_files = {}
    stats = {'v2': 0, 'v1': 0, 'jp': 0}
    for name in sorted(by_src):
        data = open(WORK + r'\fs\msg' + '\\' + name, 'rb').read()
        orig_size = len(data)
        cap = MAX_ORIG
        units = by_src[name]
        choice = {u['id']: (0 if u['id'] in cand else None) for u in units}

        def build(ch):
            texts = {}
            for u in units:
                ci = ch.get(u['id'])
                if ci is None: continue
                _, kr = cand[u['id']][ci]
                texts[u['id']] = enc_unit(kr, budgets_of[u['id']], smap)
            return msg_rebuild.rebuild(name, data, units, texts), texts

        nf, texts = build(choice)
        demotions = 0
        while len(nf) > cap:
            worst, gain_best = None, 0
            for u in units:
                ci = choice.get(u['id'])
                if ci is None: continue
                cur = len(texts[u['id']])
                opts = cand[u['id']]
                nxt = None
                if ci + 1 < len(opts):
                    try: nxt = len(enc_unit(opts[ci+1][1], budgets_of[u['id']], smap))
                    except Exception: nxt = None
                if nxt is None: nxt = u['len']
                if cur - nxt > gain_best:
                    worst, gain_best = u['id'], cur - nxt
            if worst is None: break
            opts = cand[worst]
            choice[worst] = choice[worst] + 1 if choice[worst] + 1 < len(opts) else None
            nf, texts = build(choice)
            demotions += 1
        assert len(nf) <= cap, f'{name}: {len(nf)} > cap {cap}'
        new_files['/msg/' + name] = nf
        for u in units:
            ci = choice.get(u['id'])
            stats['jp' if ci is None else cand[u['id']][ci][0]] += 1
        grow = len(nf) - orig_size
        print(f'  {name}: {orig_size} -> {len(nf)} ({grow:+d}, demotions={demotions})')
    print('msgsec unit sources:', stats)

    # ---- graphics: label-translated .dat files (same size, pixel data only) ----
    gfx_dir = WORK + r'\fs_gfx\obj'
    gfx_files = {}
    if os.path.isdir(gfx_dir):
        for fn in sorted(os.listdir(gfx_dir)):
            gfx_files['/obj/' + fn] = open(os.path.join(gfx_dir, fn), 'rb').read()
    print('graphics files patched:', len(gfx_files))

    # ---- ROM assembly: keep everything in place; relocate only grown files to the tail ----
    rom = bytearray(open(ROM_IN, 'rb').read())
    rom[ARM9_ROM_OFF: ARM9_ROM_OFF + len(arm9)] = arm9
    fat_off = manifest['fat_off']
    used_end = struct.unpack_from('<I', rom, 0x80)[0]
    tail = (used_end + 0x1FF) & ~0x1FF
    moved = 0
    for f in manifest['files']:
        p = f['path']
        if p == '/scenario/common.snr':
            assert len(snr) == f['size']
            rom[f['start']: f['start'] + len(snr)] = snr
            continue
        if p in gfx_files:
            g = gfx_files[p]
            assert len(g) == f['size'], f'{p}: graphics size changed'
            rom[f['start']: f['start'] + len(g)] = g
            continue
        if p not in new_files:
            continue
        d = new_files[p]
        if len(d) <= f['size']:
            rom[f['start']: f['start'] + len(d)] = d
            if len(d) < f['size']:
                rom[f['start'] + len(d): f['start'] + f['size']] = b'\x00' * (f['size'] - len(d))
            struct.pack_into('<II', rom, fat_off + f['id']*8, f['start'], f['start'] + len(d))
        else:
            start = tail
            end = start + len(d)
            assert end <= len(rom), 'ROM tail exhausted'
            rom[start:end] = d
            struct.pack_into('<II', rom, fat_off + f['id']*8, start, end)
            rom[f['start']: f['start'] + f['size']] = b'\xFF' * f['size']   # free old slot
            tail = (end + 0x1FF) & ~0x1FF
            moved += 1
    new_used = max(used_end, tail)
    struct.pack_into('<I', rom, 0x80, new_used)
    struct.pack_into('<H', rom, 0x15E, crc16(rom[:0x15E]))
    open(ROM_OUT, 'wb').write(rom)
    print(f'relocated files: {moved}, used 0x{used_end:X} -> 0x{new_used:X}')
    print('ROM written:', ROM_OUT)

if __name__ == '__main__':
    main()
