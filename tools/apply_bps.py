# -*- coding: utf-8 -*-
"""BPS patch applier.
Usage: python apply_bps.py <patch.bps> <original.nds> <output.nds>"""
import sys, zlib

def apply_bps(patch_path, src_path, out_path):
    p = open(patch_path, 'rb').read()
    src = open(src_path, 'rb').read()
    assert p[:4] == b'BPS1', 'not a BPS patch'
    ip = 4
    def rdv():
        nonlocal ip
        data, shift = 0, 1
        while True:
            x = p[ip]; ip += 1
            data += (x & 0x7F) * shift
            if x & 0x80: return data
            shift <<= 7
            data += shift
    ssize = rdv(); tsize = rdv(); msize = rdv()
    ip += msize
    src_crc_expect = int.from_bytes(p[-12:-8], 'little')
    if zlib.crc32(src) != src_crc_expect:
        print(f'WARNING: source CRC mismatch (expected {src_crc_expect:08X}, got {zlib.crc32(src):08X})')
        print('원본 ROM이 다릅니다. 일본판 무수정 덤프인지 확인하세요.')
    out = bytearray()
    outOff = 0
    srcRel = 0; dstRel = 0
    end = len(p) - 12
    while ip < end:
        length = rdv()
        mode = length & 3
        length = (length >> 2) + 1
        if mode == 0:
            out += src[outOff:outOff+length]; outOff += length
        elif mode == 1:
            out += p[ip:ip+length]; ip += length; outOff += length
        else:
            d = rdv()
            off = (d >> 1) * (-1 if d & 1 else 1)
            if mode == 2:
                srcRel += off
                out += src[srcRel:srcRel+length]; srcRel += length; outOff += length
            else:
                dstRel += off
                for _ in range(length):
                    out.append(out[dstRel]); dstRel += 1
                outOff += length
    tgt_crc = int.from_bytes(p[-8:-4], 'little')
    assert zlib.crc32(bytes(out)) == tgt_crc, 'output CRC mismatch — patch failed'
    open(out_path, 'wb').write(out)
    print(f'OK: {out_path} ({len(out)} bytes)')

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(__doc__); sys.exit(1)
    apply_bps(sys.argv[1], sys.argv[2], sys.argv[3])
