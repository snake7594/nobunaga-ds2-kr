# -*- coding: utf-8 -*-
"""Sanity-check every gfxlabels/*.json before applying:
 - valid UTF-8 JSON, jp really Japanese, kr really Hangul
 - Korean not longer than the Japanese (button width constraint)
 - report anything suspicious so it can be fixed rather than silently applied
"""
import json, glob, os

LAB = r'D:\nds\roms\NOBU2\_work\gfxlabels'

def is_jp(s):
    return any('\u3041' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff' for c in s)
def is_kr(s):
    return any('\uac00' <= c <= '\ud7a3' for c in s)

tot = files = bad = longer = 0
issues = []
for p in sorted(glob.glob(LAB + r'\*.json')):
    n = os.path.basename(p)
    if n.startswith('_'):
        continue
    try:
        entries = json.load(open(p, encoding='utf-8-sig'))
    except Exception as e:
        issues.append(f'{n}: unreadable ({e})'); bad += 1; continue
    if not entries:
        continue
    files += 1
    for e in entries:
        tot += 1
        jp, kr = e.get('jp', ''), e.get('kr', '')
        if not is_kr(kr) or '?' in kr:
            issues.append(f'{n} cell {e.get("cell")}: kr not Hangul {kr!r}'); bad += 1
        elif jp and not is_jp(jp):
            issues.append(f'{n} cell {e.get("cell")}: jp not Japanese {jp!r}'); bad += 1
        elif jp and len(kr) > len(jp) + 1:
            longer += 1
            if longer <= 12:
                issues.append(f'{n} cell {e.get("cell")}: kr longer  {jp!r} -> {kr!r}')

print(f'files: {files}   labels: {tot}   bad: {bad}   kr-longer-than-jp: {longer}')
for i in issues[:30]:
    print('  ', i)
