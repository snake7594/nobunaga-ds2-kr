# -*- coding: utf-8 -*-
"""Build the Korean-patched ROM:
1. merge translations
2. build syllable->SJIS-code map
3. render Hangul glyphs into arm9 font region
4. encode translations, patch bytes in-place
5. write patched ROM
"""
import json, glob, os, struct, sys, collections
import krtools

WORK = r'D:\nds\roms\NOBU2\_work'
ROM_IN = r'D:\nds\roms\NOBU2\Nobunaga no Yabou DS 2 (Japan).nds'
ROM_OUT = r'D:\nds\roms\NOBU2\Nobunaga no Yabou DS 2 (Korean).nds'
ARM9_ROM_OFF = 0x4000
FONT_OFF = 0x178E64  # arm9 file offset of glyph 0

def main():
    units = {u['id']: u for u in json.load(open(WORK + r'\units.json', encoding='utf-8'))}
    if os.path.exists(WORK + r'\units_extra.json'):
        for u in json.load(open(WORK + r'\units_extra.json', encoding='utf-8')):
            units[u['id']] = u
    # apply safe capacities for common.snr (field-boundary aware)
    import snr_caps as _snr
    safe = _snr.compute()
    tightened = 0
    for u in units.values():
        if u['src'] != 'common.snr': continue
        sc = safe.get(u['off'])
        if sc is not None and sc != u['cap']:
            if sc < u['cap']: tightened += 1
            u['cap'] = sc
            u['lines'] = [sc]
    print('snr capacities adjusted (tightened):', tightened)
    # 1. merge translations
    tr = {}
    for p in sorted(glob.glob(WORK + r'\tr\out\out_*.json')):
        try:
            for item in json.load(open(p, encoding='utf-8')):
                if 'id' in item and 'kr' in item:
                    tr[item['id']] = item['kr']
        except Exception as e:
            print('WARN: bad out file', p, e)
    print(f'translations: {len(tr)} / units: {len(units)}')

    # 2. normalize + validate + collect syllables (invalid ones fall back to original bytes)
    SAFE_ASCII = set('0123456789-+/(),.: ')
    def normalize(kr, budgets):
        """Convert unsupported ASCII to fullwidth if budget allows."""
        out_lines = []
        for txt, budget in zip(kr.split('{BR}'), budgets):
            conv = []
            i = 0
            while i < len(txt):
                if txt.startswith('{C', i) and i+3 < len(txt) and txt[i+3] == '}':
                    conv.append(txt[i:i+4]); i += 4; continue
                ch = txt[i]
                if ch in SAFE_ASCII or not (0x21 <= ord(ch) <= 0x7E):
                    conv.append(ch)
                else:
                    fw = chr(ord(ch) - 0x21 + 0xFF01)  # fullwidth form
                    conv.append(fw if fw in krtools.KEEP_CHARS or True else ch)
                i += 1
            cand = ''.join(conv)
            ok, _ = krtools.check_translation(cand, [budget])
            out_lines.append(cand if ok else txt)
        return '{BR}'.join(out_lines)

    valid = {}
    fails = []
    sylls = set()
    for uid, kr in tr.items():
        u = units.get(uid)
        if u is None: continue
        if any(0x21 <= ord(c) <= 0x7E and c not in SAFE_ASCII for c in kr):
            kr = normalize(kr, u['lines'])
        ok, info = krtools.check_translation(kr, u['lines'])
        if ok:
            valid[uid] = kr
            sylls |= krtools.used_syllables(kr)
        else:
            fails.append((uid, info, u['jp'][:30], kr[:30]))
    print(f'valid: {len(valid)}  invalid: {len(fails)}  unique syllables: {len(sylls)}')
    if fails:
        json.dump([{'id': f[0], 'err': f[1], 'jp': f[2], 'kr': f[3]} for f in fails],
                  open(WORK + r'\tr\fails.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # 3. syllable map (kanji slots idx>=351)
    c2i = krtools.load_code2idx()
    pool = [c for c, i in sorted(c2i.items()) if i >= 351]
    print(f'pool slots: {len(pool)}')
    if len(sylls) > len(pool):
        print('ERROR: syllables exceed pool', len(sylls)); sys.exit(1)
    smap = {s: pool[i] for i, s in enumerate(sorted(sylls))}
    json.dump({s: hex(c) for s, c in smap.items()},
              open(WORK + r'\syllable_map.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

    # 4. patch arm9: font glyphs
    arm9 = bytearray(open(WORK + r'\bin\arm9.bin', 'rb').read())
    for s, code in smap.items():
        idx = c2i[code]
        rows = krtools.render_glyph12(s)
        arm9[FONT_OFF + idx*18: FONT_OFF + idx*18 + 18] = krtools.rows_to_bytes(rows)
    print('font glyphs patched:', len(smap))

    # 5. encode + patch text
    file_bufs = {'arm9.bin': arm9}
    def get_buf(src):
        if src not in file_bufs:
            if src == 'common.snr':
                p = WORK + r'\fs\scenario\common.snr'
            else:
                p = WORK + r'\fs\msg' + '\\' + src
            file_bufs[src] = bytearray(open(p, 'rb').read())
        return file_bufs[src]

    patched = 0
    skipped = 0
    for uid, u in units.items():
        kr = valid.get(uid)
        if kr is None:
            skipped += 1
            continue
        buf = get_buf(u['src'])
        pad_mode = 'space' if u['src'].startswith('msgsec') else 'null'
        try:
            enc = krtools.encode_unit(kr, u['lines'], smap, pad=pad_mode)
        except Exception as e:
            print('ENC FAIL', uid, e)
            skipped += 1
            continue
        cap_total = sum(u['lines']) + (len(u['lines']) - 1)
        # unit byte span = len(u['len']) plus possible null-bonus area
        span = u['len']
        assert len(enc) == cap_total, (uid, len(enc), cap_total)
        if len(enc) < span:
            raise AssertionError(f'enc shorter than span {uid}')
        # write enc over [off, off+len(enc)); bytes beyond original span were nulls (bonus)
        off = u['off']
        # safety: bonus region must be nulls in original
        for k in range(span, len(enc)):
            if buf[off + k] not in (0x00,):
                raise AssertionError(f'bonus not null at {uid} +{k}')
        buf[off: off + len(enc)] = enc
        # if we consumed bonus, ensure one null terminator remains guaranteed by extractor
        patched += 1
    print(f'units patched: {patched}  skipped: {skipped}')

    # 6. assemble ROM
    rom = bytearray(open(ROM_IN, 'rb').read())
    manifest = json.load(open(WORK + r'\manifest.json'))
    fstart = {os.path.basename(f['path']): f['start'] for f in manifest['files']}
    rom[ARM9_ROM_OFF: ARM9_ROM_OFF + len(arm9)] = arm9
    for src, buf in file_bufs.items():
        if src == 'arm9.bin': continue
        rom[fstart[src]: fstart[src] + len(buf)] = buf
    open(ROM_OUT, 'wb').write(rom)
    print('ROM written:', ROM_OUT, len(rom))

if __name__ == '__main__':
    main()
