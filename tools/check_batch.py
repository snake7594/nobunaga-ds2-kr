# -*- coding: utf-8 -*-
"""Validate a translated batch: python check_batch.py batch_in.json out.json
Prints PASS or per-item violations."""
import json, sys

def enc_len(text):
    """encoded byte length of one line"""
    n = 0
    i = 0
    while i < len(text):
        if text.startswith('{C', i) and i+3 < len(text) and text[i+3] == '}':
            n += 3; i += 4; continue
        ch = text[i]
        o = ord(ch)
        if 0x20 <= o <= 0x7E:
            n += 1
        else:
            n += 2
        i += 1
    return n

def check(inp, outp):
    src = {u['id']: u for u in json.load(open(inp, encoding='utf-8'))}
    try:
        out = json.load(open(outp, encoding='utf-8'))
    except Exception as e:
        print(f'FAIL: cannot parse output: {e}'); return 1
    seen = set()
    errs = []
    for item in out:
        uid = item.get('id')
        if uid not in src:
            errs.append(f'id {uid}: unknown id'); continue
        seen.add(uid)
        u = src[uid]
        kr = item.get('kr', None)
        if kr is None:
            errs.append(f'id {uid}: missing kr'); continue
        lines = kr.split('{BR}')
        if len(lines) != len(u['lines']):
            errs.append(f"id {uid}: line count {len(lines)} != {len(u['lines'])} | jp={u['jp'][:40]!r} kr={kr[:40]!r}")
            continue
        for li, (txt, budget) in enumerate(zip(lines, u['lines'])):
            L = enc_len(txt)
            if L > budget:
                errs.append(f'id {uid} line {li}: {L}B > budget {budget}B | kr={txt[:50]!r}')
            for ch in txt:
                o = ord(ch)
                if 0x20 <= o <= 0x7E: continue
                if 0xAC00 <= o <= 0xD7A3: continue
                if ch in '、。，．・：；？！´｀¨＾ー―‐／＼～…‥''""（）〔〕［］｛｝〈〉《》「」『』【】＋－×÷＝＜＞≦≧％＆＊＠☆★○●◎◇◆□■△▲▽▼※→←↑↓　０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ':
                    continue
                if ch in '{}C0123456789':
                    continue
                errs.append(f'id {uid} line {li}: forbidden char {ch!r} (U+{o:04X})')
                break
    missing = set(src) - seen
    if missing:
        errs.append(f'missing ids: {sorted(missing)[:20]}{"..." if len(missing)>20 else ""}')
    if errs:
        print('FAIL')
        for e in errs[:60]: print(' ', e)
        return 1
    print('PASS')
    return 0

if __name__ == '__main__':
    sys.exit(check(sys.argv[1], sys.argv[2]))
