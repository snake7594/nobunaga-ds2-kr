# -*- coding: utf-8 -*-
"""Copy the working toolchain into the repo, making it machine independent.

The tools were developed with absolute paths baked in.  Rather than hand-edit
twenty files (and drift from what actually produced the release), this rewrites
those literals to reference tools/nobu2_paths.py, so the repo copy is generated
from the exact code that built the ROM.

Usage:  python tools/dev/vendor.py <source_gfxtools_dir> <source_tools_dir>
"""
import os, re, sys, shutil

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# literal -> expression that replaces it
SUBS = [
    (r'D:\nds\roms\NOBU2\Nobunaga no Yabou DS 2 (Japan).nds',  'ROM_IN'),
    (r'D:\nds\roms\NOBU2\Nobunaga no Yabou DS 2 (Korean).nds', 'ROM_OUT'),
    (r'D:\nds\files (1)\Galmuri11.ttf',                        'FONT'),
    (r'D:\nds\roms\NOBU2\_work',                               'WORK'),
]
HEADER = ("import os as _os, sys as _sys\n"
          "_sys.path[:0] = [_os.path.dirname(_os.path.abspath(__file__)),\n"
          "                _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')]\n"
          "from nobu2_paths import ROM_IN, ROM_OUT, WORK, FONT, DATA\n")

def rewrite(text):
    hit = False
    for lit, name in SUBS:
        # r'LIT'  /  r"LIT"  ->  NAME
        for q in ("'", '"'):
            exact = f'r{q}{lit}{q}'
            if exact in text:
                text = text.replace(exact, name); hit = True
        # r'LIT\tail'  ->  NAME + r'\tail'
        pat = re.compile(r'r([\'"])' + re.escape(lit) + r'(\\[^\'"]*)\1')
        def rep(m, name=name):
            return f'{name} + r{m.group(1)}{m.group(2)}{m.group(1)}'
        text, n = pat.subn(rep, text)
        hit = hit or bool(n)
    if not hit:
        return text, False
    # insert the import right after the leading import block
    lines = text.split('\n')
    last = -1
    for i, ln in enumerate(lines[:60]):
        if re.match(r'(import|from)\s+\w', ln):      # top level only
            last = i
    at = last + 1 if last >= 0 else 0
    lines.insert(at, HEADER.rstrip('\n'))
    out = '\n'.join(lines)
    # the substitution can leave a no-op like "WORK = WORK"; drop those
    out = re.sub(r'^(ROM_IN|ROM_OUT|WORK|FONT) = \1$\n', '', out, flags=re.M)
    # NAME + r'\a\b'  ->  os.path.join(NAME, 'a', 'b')  so the repo runs on
    # Linux and macOS too, not just the machine this was written on
    def join(m):
        parts = [p for p in m.group(2).split('\\') if p]
        args = ', '.join(f"'{p}'" for p in parts)
        return f'_os.path.join({m.group(1)}, {args})'
    out = re.sub(r'\b(\w+) \+ r[\'"](\\[^\'"]*)[\'"]', join, out)
    return out, True

def copy_tree(src, dst, exts=('.py',)):
    os.makedirs(dst, exist_ok=True)
    done = 0
    for fn in sorted(os.listdir(src)):
        sp = os.path.join(src, fn)
        if not os.path.isfile(sp) or not fn.endswith(exts): continue
        text = open(sp, encoding='utf-8').read()
        text, changed = rewrite(text)
        open(os.path.join(dst, fn), 'w', encoding='utf-8', newline='\n').write(text)
        done += 1
        if changed: print(f'  rewrote {fn}')
    return done

if __name__ == '__main__':
    gfx_src, tools_src = sys.argv[1], sys.argv[2]
    n1 = copy_tree(tools_src, os.path.join(REPO, 'tools'))
    n2 = copy_tree(gfx_src, os.path.join(REPO, 'tools', 'gfx'))
    print(f'tools: {n1}, gfx tools: {n2}')
