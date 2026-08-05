# -*- coding: utf-8 -*-
"""msgsec rebuild engine:
- parse file into (top_table, segments) where segments = opaque byte chunks + text-unit slots
- rebuild with replacement texts of arbitrary length
- remap top-table offsets and record-0 pointer-table offsets
Round-trip identity: rebuild with original unit bytes == original file.
"""
import struct, json, os
import os as _os, sys as _sys
_sys.path[:0] = [_os.path.dirname(_os.path.abspath(__file__)),
                _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')]
from nobu2_paths import ROM_IN, ROM_OUT, WORK, FONT, DATA


def load_units():
    units = json.load(open(_os.path.join(WORK, 'units.json'), encoding='utf-8'))
    for ex in (r'\units_extra.json', r'\units_extra3.json'):
        p = WORK + ex
        if os.path.exists(p):
            units += json.load(open(p, encoding='utf-8'))
    # msgsec only, sorted by offset
    by_src = {}
    for u in units:
        if u['src'].startswith('msgsec'):
            by_src.setdefault(u['src'], []).append(u)
    for k in by_src:
        by_src[k].sort(key=lambda u: u['off'])
    return by_src

def parse_file(name, data):
    """Returns dict with:
    n_top: top table entry count, top_offsets: list,
    r0_is_ptr: bool, r0_range: (start,end) if ptr table, r0_values: [...],
    """
    first = struct.unpack_from('<H', data, 0)[0]
    assert 4 <= first < len(data), f'{name}: bad top table'
    cnt = first // 2   # floor; odd 'first' leaves a 1-byte gap before record 0
    tops = [struct.unpack_from('<H', data, i*2)[0] for i in range(cnt)]
    assert tops[0] == first, f'{name}: top[0] != table size'
    # ascending check (tolerate equal)
    for i in range(1, cnt):
        assert tops[i] >= tops[i-1], f'{name}: top table not ascending @{i}'
        assert tops[i] <= len(data), f'{name}: top offset OOB'
    # record 0 span; pointer table is u16-aligned to EVEN file offsets
    r0s, r0e = tops[0], tops[1] if cnt > 1 else len(data)
    r0_is_ptr = False
    r0_tbl_start = None
    for align in (r0s, r0s + 1):
        if align % 2: continue
        nv = (r0e - align) // 2
        if nv < 3: continue
        vals = [struct.unpack_from('<H', data, align + i*2)[0] for i in range(nv)]
        asc = all(vals[i] <= vals[i+1] for i in range(nv - 1))
        inb = all(4 <= v <= len(data) for v in vals)
        if asc and inb:
            r0_is_ptr = True
            r0_tbl_start = align
            break
    return {'cnt': cnt, 'tops': tops, 'r0_span': (r0s, r0e), 'r0_is_ptr': r0_is_ptr,
            'r0_tbl_start': r0_tbl_start}

def rebuild(name, data, units, texts):
    """units: list of unit dicts (sorted by off), texts: {id: bytes or None(keep)}.
    Returns new file bytes. Internal offsets remapped."""
    info = parse_file(name, data)
    cnt = info['cnt']
    tops = info['tops']
    r0s, r0e = info['r0_span']

    # exclude false-positive units: inside top table or inside record 0 (pointer/data table)
    units = [u for u in units if u['off'] >= tops[0] and not (r0s <= u['off'] < r0e)]

    # build segment list over region [tops[0], len(data)): (kind, a, b, unit)
    segs = []
    pos = tops[0]
    for u in units:
        a, b = u['off'], u['off'] + u['len']
        assert a >= pos, f'{name}: unit overlap at {a:#x}'
        if a > pos:
            segs.append(('raw', pos, a, None))
        segs.append(('unit', a, b, u))
        pos = b
    if pos < len(data):
        segs.append(('raw', pos, len(data), None))

    # old->new offset mapping for segment boundaries
    out = bytearray()
    mapping = {}  # old offset -> new offset (for boundaries and interior of raw segs we map linearly)
    new_top_base = tops[0]  # table (+gap byte if odd) preserved verbatim
    cursor = new_top_base
    seg_newstart = []
    for kind, a, b, u in segs:
        mapping[a] = cursor
        seg_newstart.append((kind, a, b, u, cursor))
        if kind == 'raw':
            cursor += b - a
        else:
            t = texts.get(u['id'])
            cursor += (b - a) if t is None else len(t)
    mapping[len(data)] = cursor

    def remap(off):
        """map an old file offset to new (must be a segment boundary or inside a raw seg)"""
        if off in mapping:
            return mapping[off]
        # find segment containing off
        for kind, a, b, u, ns in seg_newstart:
            if a <= off < b:
                if kind == 'raw':
                    return ns + (off - a)
                # inside a unit: map to unit start (shouldn't happen for pointers)
                return ns
        raise KeyError(hex(off))

    # emit: top table (+ gap byte(s) between table end and first record, preserved)
    for i in range(cnt):
        out += struct.pack('<H', remap(tops[i]))
    if tops[0] > cnt * 2:
        out += data[cnt*2: tops[0]]
    # emit segments (with record-0 pointer remap if applicable)
    for kind, a, b, u, ns in seg_newstart:
        if kind == 'raw':
            out += data[a:b]
        else:
            t = texts.get(u['id'])
            out += data[a:b] if t is None else t

    # record-0 pointer remap (r0 fully inside raw segments now — units there excluded)
    if info['r0_is_ptr']:
        ts = info['r0_tbl_start']
        new_ts = remap(ts)
        nvals = (r0e - ts) // 2
        for k in range(nvals):
            old_v = struct.unpack_from('<H', data, ts + k*2)[0]
            struct.pack_into('<H', out, new_ts + k*2, remap(old_v))
    return bytes(out)

if __name__ == '__main__':
    by_src = load_units()
    ok = 0
    for name in sorted(by_src):
        path = _os.path.join(WORK, 'fs', 'msg') + '\\' + name
        data = open(path, 'rb').read()
        units = by_src[name]
        info = parse_file(name, data)
        # identity round trip
        rb = rebuild(name, data, units, {})
        ident = rb == data
        print(f'{name}: records={info["cnt"]} r0_ptr={info["r0_is_ptr"]} units={len(units)} identity={ident}')
        if ident: ok += 1
    print('identity OK:', ok, '/', len(by_src))
