# -*- coding: utf-8 -*-
"""Korean patch toolchain: Hangul glyph rendering, text encoding, byte budget check."""
import json, struct, os
from PIL import Image, ImageFont, ImageDraw

WORK = r'D:\nds\roms\NOBU2\_work'

# ---------- Hangul glyph rendering (Galmuri11 bitmap font, user-requested) ----------
_font = None
def get_font():
    global _font
    if _font is None:
        _font = ImageFont.truetype(r'D:\nds\files (1)\Galmuri11.ttf', 12)
    return _font

def render_glyph12(ch):
    """Render char to 12x12 1bpp rows (list of 12 ints, 12-bit each)."""
    f = get_font()
    img = Image.new('L', (16, 16), 255)
    d = ImageDraw.Draw(img)
    d.text((0, 0), ch, font=f, fill=0)
    px = img.load()
    rows = []
    for y in range(12):
        r = 0
        for x in range(12):
            r = (r << 1) | (1 if px[x, y] < 128 else 0)
        rows.append(r)
    return rows

def rows_to_bytes(rows):
    """Pack 12x12 rows into 18 bytes (bit-continuous, MSB first)."""
    bits = 0
    for r in rows:
        bits = (bits << 12) | (r & 0xFFF)
    return bits.to_bytes(18, 'big')

# ---------- charset / encoding ----------
# SJIS chars whose codes we keep (glyphs untouched): symbols, digits, latin, kana, punct
KEEP_CHARS = set('、。，．・：；？！´｀¨＾ー―‐／＼～…‥''""（）〔〕［］｛｝〈〉《》「」『』【】'
                 '＋－×÷＝＜＞≦≧％＆＊＠☆★○●◎◇◆□■△▲▽▼※→←↑↓　'
                 '０１２３４５６７８９'
                 'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
                 'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ')

def load_code2idx():
    return {int(k, 16): v for k, v in json.load(open(WORK + r'\code2idx.json')).items()}

def hangul_pool(code2idx):
    """SJIS codes available for Hangul (kanji slots, glyph idx >= 295)."""
    pool = [c for c, i in sorted(code2idx.items()) if i >= 295]
    return pool

def build_syllable_map(syllables, code2idx=None):
    """Assign each syllable an SJIS code from the kanji pool. Returns {syll: code}."""
    if code2idx is None: code2idx = load_code2idx()
    pool = hangul_pool(code2idx)
    if len(syllables) > len(pool):
        raise ValueError(f'too many syllables: {len(syllables)} > {len(pool)}')
    return {s: pool[i] for i, s in enumerate(sorted(syllables))}

def encode_line(text, smap, strict=True):
    """Encode one line of Korean template text to bytes. No padding."""
    out = bytearray()
    i = 0
    while i < len(text):
        if text.startswith('{C', i) and i + 3 < len(text) and text[i+3] == '}' and text[i+2].isdigit():
            out += bytes([0x1B, 0x43, ord(text[i+2])])
            i += 4
            continue
        ch = text[i]
        if ch == '\n':
            raise ValueError('newline inside line')
        o = ord(ch)
        if 0x20 <= o <= 0x7E:
            out.append(o)
        elif 0xAC00 <= o <= 0xD7A3:
            code = smap.get(ch)
            if code is None: raise KeyError(f'unmapped syllable {ch}')
            out += bytes([code >> 8, code & 0xFF])
        elif ch in KEEP_CHARS:
            out += ch.encode('shift_jis')
        elif strict:
            raise ValueError(f'forbidden char {ch!r} U+{o:04X}')
        else:
            out += ch.encode('shift_jis')
        i += 1
    return bytes(out)

def encode_unit(template, line_budgets, smap, pad='space'):
    """Encode full template with {BR} splits; pad each line to its budget.
    pad='space': fullwidth-space padding (msgsec). pad='null': 0x00 padding (C-string fields).
    Returns bytes of total length == sum(budgets) + len(budgets)-1 (for 0x0A separators)."""
    lines = template.split('{BR}')
    if len(lines) != len(line_budgets):
        raise ValueError(f'line count mismatch: {len(lines)} vs {len(line_budgets)}')
    parts = []
    for li, (txt, budget) in enumerate(zip(lines, line_budgets)):
        enc = encode_line(txt, smap)
        if len(enc) > budget:
            raise ValueError(f'line overflow: {len(enc)} > {budget}: {txt!r}')
        padn = budget - len(enc)
        if pad == 'null' and li == len(lines) - 1:
            enc += b'\x00' * padn
        else:
            enc += b'\x81\x40' * (padn // 2)
            if padn % 2:
                enc += b' '
        parts.append(enc)
    return b'\x0A'.join(parts)

def check_translation(template, line_budgets, smap_or_none=None):
    """Validate a translation fits budgets & uses only allowed chars."""
    lines = template.split('{BR}')
    if len(lines) != len(line_budgets):
        return False, f'line count mismatch: {len(lines)} vs {len(line_budgets)}'
    dummy = DummyMap()
    lens = []
    for txt, budget in zip(lines, line_budgets):
        try:
            enc = encode_line(txt, dummy, strict=True)
        except Exception as e:
            return False, f'encode error: {e}'
        if len(enc) > budget:
            return False, f'overflow {len(enc)}>{budget}: {txt!r}'
        lens.append(len(enc))
    return True, lens

class DummyMap(dict):
    def get(self, ch, default=None):
        return 0x8888  # any 2-byte placeholder

def used_syllables(text):
    return {ch for ch in text if 0xAC00 <= ord(ch) <= 0xD7A3}
