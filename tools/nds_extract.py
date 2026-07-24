import os, struct, sys, json

ROM = r"D:\nds\roms\NOBU2\Nobunaga no Yabou DS 2 (Japan).nds"
OUT = r"D:\nds\roms\NOBU2\_work\fs"

data = open(ROM, "rb").read()

def u32(o): return struct.unpack_from("<I", data, o)[0]
def u16(o): return struct.unpack_from("<H", data, o)[0]

title = data[0:12].rstrip(b"\0").decode("ascii", "replace")
gamecode = data[12:16].decode("ascii", "replace")
arm9_off, arm9_entry, arm9_ram, arm9_size = u32(0x20), u32(0x24), u32(0x28), u32(0x2C)
arm7_off, arm7_size = u32(0x30), u32(0x3C)
fnt_off, fnt_size = u32(0x40), u32(0x44)
fat_off, fat_size = u32(0x48), u32(0x4C)
ov9_off, ov9_size = u32(0x50), u32(0x54)

print(f"Title: {title}  Code: {gamecode}")
print(f"ARM9 off=0x{arm9_off:X} size=0x{arm9_size:X}  ARM7 off=0x{arm7_off:X} size=0x{arm7_size:X}")
print(f"FNT off=0x{fnt_off:X} size=0x{fnt_size:X}  FAT off=0x{fat_off:X} size=0x{fat_size:X} files={fat_size//8}")
print(f"OVT9 off=0x{ov9_off:X} size=0x{ov9_size:X}")

# FAT
nfiles = fat_size // 8
fat = []
for i in range(nfiles):
    s = u32(fat_off + i*8); e = u32(fat_off + i*8 + 4)
    fat.append((s, e))

# FNT walk
def read_dir(dir_id, path, out):
    entry_off = fnt_off + (dir_id & 0xFFF) * 8
    sub_off = u32(entry_off)
    first_id = u16(entry_off + 4)
    p = fnt_off + sub_off
    fid = first_id
    while True:
        t = data[p]; p += 1
        if t == 0: break
        namelen = t & 0x7F
        name = data[p:p+namelen].decode("shift_jis", "replace"); p += namelen
        if t & 0x80:
            sub_id = u16(p); p += 2
            read_dir(sub_id, path + "/" + name, out)
        else:
            out.append((fid, path + "/" + name))
            fid += 1

files = []
read_dir(0xF000, "", files)
print(f"FNT files: {len(files)}")

manifest = []
os.makedirs(OUT, exist_ok=True)
for fid, path in files:
    s, e = fat[fid]
    dest = OUT + path.replace("/", os.sep)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data[s:e])
    manifest.append({"id": fid, "path": path, "start": s, "size": e - s})

# also dump arm9/arm7/overlays
bin_out = r"D:\nds\roms\NOBU2\_work\bin"
os.makedirs(bin_out, exist_ok=True)
open(os.path.join(bin_out, "arm9.bin"), "wb").write(data[arm9_off:arm9_off+arm9_size])
open(os.path.join(bin_out, "arm7.bin"), "wb").write(data[arm7_off:arm7_off+arm7_size])
# overlay table
if ov9_size:
    ovt = data[ov9_off:ov9_off+ov9_size]
    n = ov9_size // 32
    for i in range(n):
        oid, ram, sz, bss, sinit, einit, fileid, flag = struct.unpack_from("<8I", ovt, i*32)
        s, e = fat[fileid]
        open(os.path.join(bin_out, f"overlay_{oid:04d}.bin"), "wb").write(data[s:e])
    print(f"Overlays: {n}")

json.dump({"title": title, "gamecode": gamecode, "files": manifest,
           "fat_off": fat_off, "fnt_off": fnt_off, "nfiles": nfiles},
          open(r"D:\nds\roms\NOBU2\_work\manifest.json", "w"), indent=1)
print("Extracted OK")
