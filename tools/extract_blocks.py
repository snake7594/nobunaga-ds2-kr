# -*- coding: utf-8 -*-
"""Block-based extraction:
- msgsec: blocks absorbing text runs, spaces, 0x0A newlines, 1B4B/1B48 kana toggles, 1B43+digit colors
- common.snr / arm9: per-run + trailing-null capacity
Output: units.json with per-line budgets and decoded template text using tokens:
  {BR} newline, {C0}-{C9} color, kana-toggles dropped silently.
"""
import struct, glob, os, json, unicodedata

WORK = r'D:\nds\roms\NOBU2\_work'
HW = '｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ'

def is_lead(c): return 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xEF
def is_trail(c): return 0x40 <= c <= 0xFC and c != 0x7F

def hw_merge(s):
    merged = ''
    for ch in s:
        if ch in 'ﾞﾟ' and merged:
            comb = unicodedata.normalize('NFKC', merged[-1] + ch)
            if len(comb) == 1:
                merged = merged[:-1] + comb; continue
        merged += ch
    res = ''
    for ch in merged:
        n = unicodedata.normalize('NFKC', ch)
        if n and 0x30A1 <= ord(n[0]) <= 0x30F6:
            res += chr(ord(n[0]) - 0x60)
        else:
            res += n
    return res

COMMON_PUNCT = set('、。，．・：；？！ー―…（）「」『』　〜・！？')
def quality(txt):
    t = txt.replace('{BR}', '').replace('　', '')
    for i in range(10): t = t.replace('{C%d}' % i, '')
    kana = sum(1 for ch in t if '぀' <= ch <= 'ヿ')
    cjk = sum(1 for ch in t if '一' <= ch <= '鿿')
    if kana >= 1: return True
    punct = sum(1 for ch in t if ch in COMMON_PUNCT)
    other = len(t) - kana - cjk - punct
    if cjk >= 2 and other == 0: return True
    if cjk >= 1 and punct >= 1 and other == 0: return True
    return False

def parse_block(d, i, hi):
    """Try to parse a block starting at i. Returns (end, template, has_text) or None.
    template: decoded text with {BR}/{C#} tokens."""
    parts = []
    kana = []
    j = i
    has_text = False
    def flush():
        if kana:
            parts.append(hw_merge(''.join(kana)))
            kana.clear()
    while j < hi:
        c = d[j]
        if c == 0x0A:
            flush(); parts.append('{BR}'); j += 1
        elif c == 0x1B and j+1 < hi and d[j+1] in (0x4B, 0x48):
            flush(); j += 2  # kana mode toggle - dropped
        elif c == 0x1B and j+2 < hi and d[j+1] == 0x43 and 0x30 <= d[j+2] <= 0x39:
            flush(); parts.append('{C%c}' % d[j+2]); j += 3
        elif c == 0x20:
            flush(); parts.append(' '); j += 1
        elif 0xA1 <= c <= 0xDF:
            kana.append(HW[c-0xA1]); has_text = True; j += 1
        elif is_lead(c) and j+1 < hi and is_trail(d[j+1]):
            flush()
            parts.append(d[j:j+2].decode('shift_jis', 'replace'))
            has_text = True; j += 2
        else:
            break
    flush()
    if not has_text or j == i: return None
    # trim trailing toggles-only tail is fine; strip trailing {BR}? keep — budget matters
    return j, ''.join(parts), has_text

units = []
def add(src, off, ln, cap, jp, lines):
    units.append({'id': len(units), 'src': src, 'off': off, 'len': ln,
                  'cap': cap, 'jp': jp, 'lines': lines})

# ---- msgsec ----
for path in sorted(glob.glob(WORK + r'\fs\msg\msgsec*.dat')):
    name = os.path.basename(path)
    d = open(path, 'rb').read()
    first = struct.unpack_from('<H', d, 0)[0]
    lo = first if (first % 2 == 0 and 4 <= first < len(d)) else 0
    i = lo
    n = len(d)
    while i < n:
        c = d[i]
        startable = (0xA1 <= c <= 0xDF) or (is_lead(c) and i+1 < n and is_trail(d[i+1]))
        if not startable:
            i += 1; continue
        r = parse_block(d, i, n)
        if r is None:
            i += 1; continue
        end, template, _ = r
        raw = d[i:end]
        if quality(template):
            # per-line byte budgets (split raw on 0x0A)
            line_budgets = [len(seg) for seg in raw.split(b'\x0A')]
            add(name, i, len(raw), len(raw), template, line_budgets)
        i = end

# ---- common.snr ----
d = open(WORK + r'\fs\scenario\common.snr', 'rb').read()
i = 0
n = len(d)
def find_runs(data, lo, hi):
    runs = []
    i = lo
    while i < hi:
        c = data[i]
        st = (0xA1 <= c <= 0xDF) or (is_lead(c) and i+1 < hi and is_trail(data[i+1]))
        if not st:
            i += 1; continue
        j = i
        while j < hi:
            cj = data[j]
            if is_lead(cj) and j+1 < hi and is_trail(data[j+1]): j += 2
            elif 0xA1 <= cj <= 0xDF: j += 1
            else: break
        runs.append((i, j)); i = j
    return runs

for (a, b) in find_runs(d, 0, n):
    raw = d[a:b]
    kana = []
    txt_parts = []
    ii = 0
    while ii < len(raw):
        c = raw[ii]
        if 0xA1 <= c <= 0xDF: kana.append(HW[c-0xA1]); ii += 1
        else:
            if kana: txt_parts.append(hw_merge(''.join(kana))); kana.clear()
            txt_parts.append(raw[ii:ii+2].decode('shift_jis','replace')); ii += 2
    if kana: txt_parts.append(hw_merge(''.join(kana)))
    txt = ''.join(txt_parts)
    if not quality(txt): continue
    j = b
    while j < n and d[j] == 0: j += 1
    bonus = max(0, (j - b) - 1)
    add('common.snr', a, len(raw), len(raw) + bonus, txt, [len(raw) + bonus])

# ---- arm9 ----
d = open(WORK + r'\bin\arm9.bin', 'rb').read()
for lo, hi in [(0x1914A0, 0x1914B0), (0x195830, 0x195B10), (0x1A0220, 0x1A0830)]:
    i = lo
    while i < hi:
        c = d[i]
        st = (0xA1 <= c <= 0xDF) or (is_lead(c) and i+1 < hi and is_trail(d[i+1]))
        if not st:
            i += 1; continue
        r = parse_block(d, i, hi)
        if r is None:
            i += 1; continue
        end, template, _ = r
        raw = d[i:end]
        if quality(template):
            j = end
            while j < len(d) and d[j] == 0: j += 1
            bonus = max(0, (j - end) - 1)
            line_budgets = [len(seg) for seg in raw.split(b'\x0A')]
            if bonus: line_budgets[-1] += bonus
            add('arm9.bin', i, len(raw), len(raw) + bonus, template, line_budgets)
        i = end

print('total units:', len(units))
print('total jp bytes:', sum(u['len'] for u in units))
json.dump(units, open(WORK + r'\units.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
import collections
cnt = collections.Counter(u['src'] for u in units)
for k in sorted(cnt): print(f'  {k}: {cnt[k]}')
