# -*- coding: utf-8 -*-
"""v1.1 builder:
- font + arm9 strings + common.snr : in-place (as v1.0)
- msgsec : full rebuild with expanded text (no padding), internal pointers remapped
- ROM: repack file data region, rewrite FAT, update header used-size
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

def encode_line_join(kr, budgets, smap):
    lines = kr.split('{BR}')
    assert len(lines) == len(budgets), 'line count mismatch'
    encs = []
    for txt, b in zip(lines, budgets):
        e = krtools.encode_line(txt, smap)
        assert len(e) <= b, f'overflow {len(e)}>{b}: {txt[:30]!r}'
        encs.append(e)
    return b'\x0A'.join(encs)

def main():
    # ---- unit sets ----
    units_v1 = {u['id']: u for u in json.load(open(WORK + r'\units.json', encoding='utf-8'))}
    for ex in (r'\units_extra.json', r'\units_extra2.json', r'\units_extra3.json'):
        if os.path.exists(WORK + ex):
            for u in json.load(open(WORK + ex, encoding='utf-8')):
                units_v1[u['id']] = u
    units_v2 = {u['id']: u for u in json.load(open(WORK + r'\units_v2.json', encoding='utf-8'))}

    # ---- translations: v2 first, fallback v1 ----
    tr1, tr2 = {}, {}
    for p in sorted(glob.glob(WORK + r'\tr\out\out_*.json')):
        try:
            for it in json.load(open(p, encoding='utf-8')):
                tr1[it['id']] = it.get('kr', '')
        except Exception: pass
    for p in sorted(glob.glob(WORK + r'\tr\out2\out_*.json')):
        try:
            for it in json.load(open(p, encoding='utf-8')):
                tr2[it['id']] = it.get('kr', '')
        except Exception: pass
    print(f'v1 translations: {len(tr1)}, v2 translations: {len(tr2)}')

    CHAR_FIX = {'－':'−','·':'・','‧':'・','～':'〜','–':'―','—':'―','─':'―',
                '‘':"'",'’':"'",'“':'"','”':'"','⋯':'…'}
    def fix(kr):
        for b, g in CHAR_FIX.items():
            if b in kr: kr = kr.replace(b, g)
        return kr

    # ---- collect syllables over final chosen texts ----
    sylls = set()
    final_kr = {}   # id -> (kr, budgets, version)
    stats = {'v2': 0, 'v1fallback': 0, 'jp_keep': 0}
    for uid, u in units_v2.items():
        kr = tr2.get(uid)
        budgets = u['lines']
        if kr is not None:
            kr = fix(kr)
            ok, info = krtools.check_translation(kr, budgets)
            if ok:
                final_kr[uid] = (kr, budgets, 'v2')
                sylls |= krtools.used_syllables(kr)
                stats['v2'] += 1
                continue
        kr = tr1.get(uid)
        if kr is not None:
            kr = fix(kr)
            ok, info = krtools.check_translation(kr, budgets)
            if ok:
                final_kr[uid] = (kr, budgets, 'v1')
                sylls |= krtools.used_syllables(kr)
                stats['v1fallback'] += 1
                continue
        stats['jp_keep'] += 1
    print('msgsec chosen:', stats)

    # non-msgsec (common.snr + arm9): v1 in-place path
    safe = _snr.compute()
    inplace_units = {}
    for uid, u in units_v1.items():
        if u['src'].startswith('msgsec'):
            continue
        if u['src'] == 'common.snr':
            sc = safe.get(u['off'])
            if sc is not None:
                u = dict(u); u['cap'] = sc; u['lines'] = [sc]
        kr = tr1.get(uid)
        if kr is None: continue
        kr = fix(kr)
        ok, _ = krtools.check_translation(kr, u['lines'])
        if ok:
            inplace_units[uid] = (u, kr)
            sylls |= krtools.used_syllables(kr)
    print('in-place units (snr/arm9):', len(inplace_units), 'total syllables:', len(sylls))

    # ---- syllable map + font ----
    c2i = krtools.load_code2idx()
    pool = [c for c, i in sorted(c2i.items()) if i >= 351]
    assert len(sylls) <= len(pool), 'pool exceeded'
    smap = {s: pool[i] for i, s in enumerate(sorted(sylls))}
    json.dump({s: hex(c) for s, c in smap.items()},
              open(WORK + r'\syllable_map.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

    arm9 = bytearray(open(WORK + r'\bin\arm9.bin', 'rb').read())
    for s, code in smap.items():
        idx = c2i[code]
        arm9[FONT_OFF + idx*18: FONT_OFF + idx*18 + 18] = krtools.rows_to_bytes(krtools.render_glyph12(s))
    print('font glyphs:', len(smap))

    # ---- in-place patches (arm9 strings, common.snr) ----
    snr = bytearray(open(WORK + r'\fs\scenario\common.snr', 'rb').read())
    n_inplace = 0
    for uid, (u, kr) in inplace_units.items():
        pad_mode = 'null'
        enc = krtools.encode_unit(kr, u['lines'], smap, pad=pad_mode)
        buf = arm9 if u['src'] == 'arm9.bin' else snr
        off = u['off']
        for k in range(u['len'], len(enc)):
            assert buf[off + k] == 0, f'bonus not null {uid}'
        buf[off: off + len(enc)] = enc
        n_inplace += 1
    print('in-place patched:', n_inplace)

    # ---- msgsec rebuild ----
    by_src = msg_rebuild.load_units()
    new_files = {}
    for name in sorted(by_src):
        data = open(WORK + r'\fs\msg' + '\\' + name, 'rb').read()
        texts = {}
        for u in by_src[name]:
            uid = u['id']
            if uid in final_kr:
                kr, budgets, _ = final_kr[uid]
                texts[uid] = encode_line_join(kr, budgets, smap)
            elif uid in tr1 and uid not in units_v2:
                # extra units (singles etc.) keep v1 fixed-length encoding
                u1 = units_v1[uid]
                kr = fix(tr1[uid])
                ok, _ = krtools.check_translation(kr, u1['lines'])
                if ok:
                    texts[uid] = krtools.encode_unit(kr, u1['lines'], smap, pad='space')
        nf = msg_rebuild.rebuild(name, data, by_src[name], texts)
        new_files['/msg/' + name] = nf
        print(f'  {name}: {len(data)} -> {len(nf)} bytes')

    # ---- ROM repack ----
    rom = bytearray(open(ROM_IN, 'rb').read())
    manifest = json.load(open(WORK + r'\manifest.json'))
    files = sorted(manifest['files'], key=lambda f: f['start'])
    fat_off = manifest['fat_off']

    contents = {}
    for f in files:
        p = f['path']
        if p in new_files:
            contents[p] = new_files[p]
        elif p == '/scenario/common.snr':
            contents[p] = bytes(snr)
        else:
            contents[p] = bytes(rom[f['start']: f['start'] + f['size']])

    # arm9 in place (same size)
    rom[ARM9_ROM_OFF: ARM9_ROM_OFF + len(arm9)] = arm9

    cursor = files[0]['start']  # keep first file position
    for f in files:
        p = f['path']
        data = contents[p]
        cursor = (cursor + 0x1FF) & ~0x1FF
        start = cursor
        end = start + len(data)
        assert end <= len(rom), 'ROM overflow'
        rom[start:end] = data
        struct.pack_into('<II', rom, fat_off + f['id']*8, start, end)
        cursor = end
    # wipe slack to 0xFF up to old used end? pad remainder region with 0xFF
    used_end = cursor
    old_used = struct.unpack_from('<I', rom, 0x80)[0]
    if used_end < old_used:
        rom[used_end:old_used] = b'\xFF' * (old_used - used_end)
    struct.pack_into('<I', rom, 0x80, used_end)
    # header CRC (0x15E over 0x000-0x15D)
    crc = crc16(rom[:0x15E])
    struct.pack_into('<H', rom, 0x15E, crc)
    open(ROM_OUT, 'wb').write(rom)
    print('ROM written:', ROM_OUT, 'used:', hex(used_end))

def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc

if __name__ == '__main__':
    main()
