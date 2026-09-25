import struct
import xml.etree.ElementTree as ET
from pathlib import Path

def s15(v):
    return struct.pack(">i", round(v * 65536))

def xyz(v):
    return struct.pack(">4s4xiii", b"XYZ ", round(v[0]*65536), round(v[1]*65536), round(v[2]*65536))

def curve(values):
    vals = [max(0, min(65535, round(x * 65535))) for x in values]
    return struct.pack(">4s4xI", b"curv", len(vals)) + struct.pack(">%dH" % len(vals), *vals)

def description(text):
    raw = text.encode("ascii", errors="replace") + b"\0"
    # ICC v2 descType: ASCII, Unicode, and ScriptCode representations.
    return (struct.pack(">4s4xI", b"desc", len(raw)) + raw +
            struct.pack(">II", 0, 0) + struct.pack(">HB", 0, 0) + b"\0" * 67)

def resample(samples, count=256):
    samples = sorted(samples)
    out = []
    for i in range(count):
        x = i / (count - 1)
        if x <= samples[0][0]: out.append(samples[0][1]); continue
        if x >= samples[-1][0]: out.append(samples[-1][1]); continue
        for (x0, y0), (x1, y1) in zip(samples, samples[1:]):
            if x0 <= x <= x1:
                t = (x-x0)/(x1-x0) if x1 != x0 else 0
                out.append(y0 + t*(y1-y0)); break
    return out

def inverse_lut(curve_values):
    out = []
    n = len(curve_values)
    for i in range(n):
        target = i / (n - 1)
        j = next((j for j in range(n - 1) if curve_values[j] <= target <= curve_values[j+1]), n-2)
        y0, y1 = curve_values[j], curve_values[j+1]
        t = (target-y0)/(y1-y0) if y1 != y0 else 0.0
        out.append((j+t)/(n-1))
    return out

def mhc2(min_lum, peak_lum, lut, matrix3):
    n = len(lut)
    matrix_offset = 36
    lut0 = matrix_offset + 48
    lut1 = lut0 + 8 + 4*n
    lut2 = lut1 + 8 + 4*n
    h = struct.pack(">4s4xIiiIIII", b"MHC2", n, round(min_lum*65536), round(peak_lum*65536), matrix_offset, lut0, lut1, lut2)
    matrix = struct.pack(">12i", *[round(x*65536) for row in matrix3 for x in (row + [0.0])])
    def lut_tag(): return struct.pack(">4s4x", b"sf32") + struct.pack(">%di" % n, *[round(max(0,min(1,x))*65536) for x in lut])
    return h + matrix + lut_tag() + lut_tag() + lut_tag()

def inv3(a):
    d = a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])-a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])+a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0])
    return [[(a[(j+1)%3][(i+1)%3]*a[(j+2)%3][(i+2)%3]-a[(j+1)%3][(i+2)%3]*a[(j+2)%3][(i+1)%3])/d for j in range(3)] for i in range(3)]

def mm(a, b): return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def read_bcs(path):
    root = ET.parse(path).getroot()
    rows = []
    for p in root.findall(".//patch"):
        st = p.find("stimuli")
        z = p.find("results/XYZ")
        if st is None or z is None:
            continue
        rgb = tuple(float(st.find(k).text) for k in ("red", "green", "blue"))
        XYZ = tuple(float(z.find(k).text) for k in ("X", "Y", "Z"))
        rows.append((rgb, XYZ))
    return rows

def read_tags(data):
    n = struct.unpack_from(">I", data, 128)[0]
    tags = {}
    for i in range(n):
        sig, off, size = struct.unpack_from(">4sII", data, 132 + i*12)
        tags[sig] = data[off:off+size]
    return tags

def read_cube(path):
    size = None; vals = []
    for line in path.open(errors="replace"):
        line=line.strip()
        if not line or line.startswith("#") or line.startswith("TITLE"): continue
        if line.startswith("LUT_3D_SIZE"): size=int(line.split()[1]); continue
        if line[0].isdigit() or line[0] == '-':
            q=line.split();
            if len(q) >= 3: vals.append(tuple(float(x) for x in q[:3]))
    return size, vals

def bradford_to_d50(v, w):
    # Bradford chromatic adaptation, measured white -> ICC D50 PCS.
    M = ((0.8951, 0.2664, -0.1614), (-0.7502, 1.7135, 0.0367), (0.0389, -0.0685, 1.0296))
    Mi = ((0.9869929, -0.1470543, 0.1599627), (0.4323053, 0.5183603, 0.0492912), (-0.0085287, 0.0400428, 0.9684867))
    src = tuple(sum(M[i][j]*w[j] for j in range(3)) for i in range(3))
    d50 = (0.96422, 1.0, 0.82521)
    dst = tuple(sum(M[i][j]*d50[j] for j in range(3)) for i in range(3))
    D = tuple(dst[i]/src[i] for i in range(3))
    vc = tuple(sum(M[i][j]*v[j] for j in range(3)) for i in range(3))
    cone = tuple(vc[i] * D[i] for i in range(3))
    return tuple(sum(Mi[i][j] * cone[j] for j in range(3)) for i in range(3))

def tag_block(tags):
    items = sorted(tags.items())
    header = bytearray(128 + 4 + 12*len(items))
    header[36:40] = b"acsp"
    struct.pack_into(">I", header, 128, len(items))
    body = bytearray()
    pos = len(header)
    for i, (sig, val) in enumerate(items):
        pos = (pos + 3) & ~3
        while len(body) + len(header) < pos: body.append(0)
        struct.pack_into(">4sII", header, 132+i*12, sig, pos, len(val))
        body += val
        while len(body) % 4: body.append(0)
        pos = len(header) + len(body)
    return bytes(header + body)

def build_profile(BCS, RAW, OUT):
    rows = read_bcs(BCS)
    raw_tags = read_tags(RAW.read_bytes())
    assert rows and b"vcgt" in raw_tags, "BCS 或 raw ICC 缺少必要資料"

    white = max(rows, key=lambda r: sum(r[0]))[1]
    prim = []
    native_prim = []
    curves = []
    gray = sorted((r[0][0], r[1][1]) for r in rows if abs(r[0][0]-r[0][1]) < 1e-7 and abs(r[0][1]-r[0][2]) < 1e-7)
    black_y = gray[0][1]
    white_y = gray[-1][1]
    gray_curve = resample([(x, max(0.0, min(1.0, (y-black_y)/(white_y-black_y)))) for x, y in gray])
    for ch in range(3):
        candidates = [r for r in rows if sum(r[0][i] for i in range(3) if i != ch) < 1e-6]
        full = max(candidates, key=lambda r: r[0][ch])[1]
        native_prim.append(tuple(x / white[1] for x in full))
        adapted = bradford_to_d50(tuple(x / white[1] for x in full), tuple(x / white[1] for x in white))
        prim.append(adapted)
        curves.append(gray_curve)

    tags = {
        b"desc": description(OUT.name),
        b"cprt": raw_tags.get(b"cprt", b""),
        b"wtpt": xyz((0.96422, 1.0, 0.82521)),
        b"lumi": xyz(white),
        b"chad": struct.pack(">4s4x9i", b"sf32", *[round(x*65536) for x in (1,0,0,0,1,0,0,0,1)]),
        b"rXYZ": xyz(prim[0]), b"gXYZ": xyz(prim[1]), b"bXYZ": xyz(prim[2]),
        b"rTRC": curve(curves[0]), b"gTRC": curve(curves[1]), b"bTRC": curve(curves[2]),
        b"vcgt": raw_tags[b"vcgt"],
    }

    result = tag_block(tags)
    result = bytearray(result)
    struct.pack_into(">I", result, 0, len(result)); struct.pack_into(">I", result, 8, 0x02200000)
    result[12:16] = b"mntr"; result[16:20] = b"RGB "; result[20:24] = b"XYZ "; result[40:44] = b"MSFT"; result[48:52] = b"PyIC"
    struct.pack_into(">I", result, 64, 0)
    struct.pack_into(">iii", result, 68, 0x0000F6D6, 0x00010000, 0x0000D32D)
    struct.pack_into(">I", result, 80, 0x50794353)
    OUT.write_bytes(result)
