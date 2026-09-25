"""Standard display ICC outputs: calibrated device profile and Windows MHC2."""
import hashlib
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import os

SRGB = ((.64, .33), (.30, .60), (.15, .06))
D65 = (.3127, .3290)
D50 = (.3457, .3585)


def read_tags(b):
    if len(b) < 132 or b[36:40] != b'acsp':
        raise ValueError('Not a valid ICC profile.')
    count = struct.unpack_from('>I', b, 128)[0]
    if count > (len(b)-132)//12:
        raise ValueError('Invalid ICC tag table.')
    result = {}
    for i in range(count):
        sig, off, size = struct.unpack_from('>4sII', b, 132+12*i)
        if off < 132+12*count or off+size > len(b) or size < 8 or sig in result:
            raise ValueError('Invalid ICC tag data.')
        result[sig] = b[off:off+size]
    return result


def mul(a, b):
    return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]


def vec(a, v):
    return [sum(x*y for x,y in zip(row,v)) for row in a]


def inv(a):
    t = [list(row)+[float(i==j) for j in range(3)] for i,row in enumerate(a)]
    for i in range(3):
        k = max(range(i,3), key=lambda k: abs(t[k][i]))
        t[i],t[k] = t[k],t[i]
        p = t[i][i]
        if abs(p) < 1e-10:
            raise ValueError('The primary coordinates do not define a usable gamut.')
        t[i] = [x/p for x in t[i]]
        for j in range(3):
            if j != i:
                p = t[j][i]
                t[j] = [x-p*y for x,y in zip(t[j],t[i])]
    return [r[3:] for r in t]


def xyz(xy):
    x,y = xy
    if not all(math.isfinite(v) for v in xy) or not (0 <= x <= 1 and 0 < y <= 1 and x+y <= 1.000001):
        raise ValueError('Each xy point must satisfy x ≥ 0, y > 0 and x + y ≤ 1.')
    return [x/y, 1, (1-x-y)/y]


def rgb_matrix(prim, white):
    p = list(map(list, zip(*(xyz(xy) for xy in prim))))
    gains = vec(inv(p), xyz(white))
    if min(gains) <= 0:
        raise ValueError('The white point must be inside the RGB primary triangle.')
    return [[p[i][j]*gains[j] for j in range(3)] for i in range(3)]


def adaptation(source, target):
    m = [[.8951,.2664,-.1614],[-.7502,1.7135,.0367],[.0389,-.0685,1.0296]]
    a,b = vec(m,source),vec(m,target)
    return mul(inv(m), [[m[i][j]*b[i]/a[i] for j in range(3)] for i in range(3)])


def decode(x):
    return x/12.92 if x <= .04045 else ((x+.055)/1.055)**2.4


def curve_reader(data):
    if data[:4] == b'curv':
        n = struct.unpack_from('>I',data,8)[0]
        if len(data) < 12+2*n:
            raise ValueError('Truncated ICC curve.')
        values = struct.unpack_from('>'+str(n)+'H',data,12)
        if n == 0:
            return lambda x: x
        if n == 1:
            g = values[0]/256
            if g <= 0: raise ValueError('Invalid ICC gamma.')
            return lambda x: x**g
        def table(x):
            t = min(1,max(0,x))*(n-1); i = min(int(t),n-2); f = t-i
            return (values[i]*(1-f)+values[i+1]*f)/65535
        return table
    if data[:4] == b'para':
        kind = struct.unpack_from('>H',data,8)[0]
        sizes = (1,3,4,5,7)
        if kind > 4: raise ValueError('Unsupported ICC parametric curve.')
        p = [v/65536 for v in struct.unpack_from('>'+str(sizes[kind])+'i',data,12)]
        def param(x):
            g = p[0]
            if kind == 0: return x**g
            a,b = p[1:3]
            if kind == 1: return max(0,a*x+b)**g if x >= -b/a else 0
            c = p[3]
            if kind == 2: return (max(0,a*x+b)**g if x >= -b/a else 0)+c
            d = p[4]
            if kind == 3: return max(0,a*x+b)**g if x >= d else c*x
            e,f = p[5:7]
            return max(0,a*x+b)**g+e if x >= d else c*x+f
        return param
    raise ValueError('Standard mode requires RGB matrix/TRC curves.')


def fixed(v): return round(v*65536)
def xyz_tag(v): return b'XYZ '+bytes(4)+struct.pack('>3i',*map(fixed,v))


def serialize(header, tags):
    out = bytearray(header[:128])+struct.pack('>I',len(tags))+bytes(12*len(tags))
    for i,(sig,data) in enumerate(tags.items()):
        out.extend(bytes((-len(out))%4))
        struct.pack_into('>4sII',out,132+12*i,sig,len(out),len(data))
        out.extend(data)
    out.extend(bytes((-len(out))%4))
    struct.pack_into('>I',out,0,len(out)); out[84:100] = bytes(16)
    d = bytearray(out); d[44:48] = bytes(4); d[64:68] = bytes(4)
    out[84:100] = hashlib.md5(d).digest()
    read_tags(out)
    return out


def build_standard_device(source, output, white=D65, gamma=2.2):
    """Describe the real display after VCGT, not the MHC2 virtual target gamut.

    Follows the user-verified v6mac calibration. The source must describe the
    display's current hardware mode. No target-gamut matrix belongs in VCGT.
    """
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError('Output already exists. Choose a new output name.')
    target_white = xyz(white)
    if gamma is not None and (not math.isfinite(gamma) or not .1 <= gamma <= 10):
        raise ValueError('Gamma must be between 0.1 and 10.')
    raw = source.read_bytes()
    tags = read_tags(raw)
    if raw[12:24] != b'mntrRGB XYZ ':
        raise ValueError('Select an RGB/XYZ display ICC profile.')
    if any(s in tags for s in (b'A2B0', b'B2A0', b'MHC2', b'vcgt')):
        raise ValueError('Standard mode requires an uncalibrated matrix/TRC display profile.')
    required = (b'rXYZ', b'gXYZ', b'bXYZ', b'wtpt', b'rTRC', b'gTRC', b'bTRC')
    if not all(s in tags for s in required):
        raise ValueError('The ICC is missing RGB colorants, curves or white-point data.')
    def read_xyz(payload):
        if payload[:4] != b'XYZ ' or len(payload) < 20:
            raise ValueError('Invalid ICC XYZ tag.')
        return [v/65536 for v in struct.unpack_from('>3i', payload, 8)]
    pcs_white = [v/65536 for v in struct.unpack_from('>3i', raw, 68)]
    if max(abs(a-b) for a,b in zip(pcs_white, (.9642, 1, .8249))) > .002:
        raise ValueError('The source ICC must use D50 PCS.')
    matrix = list(map(list, zip(*(read_xyz(tags[s]) for s in required[:3]))))
    if b'chad' in tags:
        payload = tags[b'chad']
        if payload[:4] != b'sf32' or len(payload) < 44:
            raise ValueError('Invalid ICC chromatic-adaptation tag.')
        values = [v/65536 for v in struct.unpack_from('>9i', payload, 8)]
        native = mul(inv([values[i:i+3] for i in (0,3,6)]), matrix)
    else:
        # Legacy v2 profiles (including Apple's AdobeRGB1998) store the actual
        # white in wtpt, but their RGB colorants are already D50-adapted.
        native_white = read_xyz(tags[b'wtpt'])
        if native_white[1] <= 0:
            raise ValueError('Invalid display white point.')
        native_white = [v/native_white[1] for v in native_white]
        native = mul(adaptation(pcs_white, native_white), matrix)
    gains = vec(inv(native), target_white)
    if not all(math.isfinite(g) and g > 0 for g in gains):
        raise ValueError('The white point must be inside the display gamut.')
    scale = 1/max(1, max(gains))
    gains = [g*scale for g in gains]
    calibrated = [[native[i][j]*gains[j]/scale for j in range(3)] for i in range(3)]
    chad = adaptation(target_white, pcs_white)
    calibrated_pcs = mul(chad, calibrated)
    target_curve = decode if gamma is None else lambda x: x**gamma
    source_curves = [curve_reader(tags[s]) for s in required[4:]]
    matching = True
    for curve in source_curves:
        samples = [curve(i/4096) for i in range(4097)]
        if (not all(math.isfinite(v) for v in samples)
                or any(a>b+1e-8 for a,b in zip(samples,samples[1:]))
                or abs(samples[0])>1e-5 or abs(samples[-1]-1)>1e-4):
            raise ValueError('The display TRCs must be monotonic and normalized from 0 to 1.')
        matching &= all(abs(v-target_curve(i/4096)) < 1e-12 for i,v in enumerate(samples))
    # ColorSync's transfer-table API accepts the verified v6 256-entry format;
    # it returns no table for 4096-entry VCGT on the tested macOS system.
    # The profile TRCs can still use 4096 samples independently of VCGT.
    count = 256
    ramps = []
    for curve, gain in zip(source_curves, gains):
        ramp = []
        for i in range(count):
            y = gain*target_curve(i/(count-1))
            lo, hi = 0., 1.
            for _ in range(40):
                mid = (lo+hi)/2
                if curve(mid) < y: lo = mid
                else: hi = mid
            ramp.append(round(65535*(lo+hi)/2))
        if any(a>b for a,b in zip(ramp,ramp[1:])):
            raise ValueError('Generated calibration is not monotonic.')
        ramps.extend(ramp)
    # Retain only relevant characterization/copyright tags. Never carry over
    # source characterization metadata or transforms describing the old state.
    result = {s: tags[s] for s in (b'cprt', b'bkpt') if s in tags}
    for j,s in enumerate(required[:3]):
        result[s] = xyz_tag([calibrated_pcs[i][j] for i in range(3)])
    result[b'wtpt'] = xyz_tag(pcs_white)
    result[b'chad'] = b'sf32'+bytes(4)+struct.pack('>9i',*[fixed(x) for row in chad for x in row])
    for s in required[4:]:
        if matching:
            result[s] = tags[s]
        else:
            values = [round(65535*target_curve(i/4095)) for i in range(4096)]
            result[s] = b'curv'+bytes(4)+struct.pack('>I4096H',4096,*values)
    result[b'vcgt'] = b'vcgt'+bytes(4)+struct.pack('>IHHH',0,3,count,2)+struct.pack('>'+str(len(ramps))+'H',*ramps)
    if b'lumi' in tags:
        luminance = read_xyz(tags[b'lumi'])[1]
        if not math.isfinite(luminance) or luminance <= 0:
            raise ValueError('Invalid source luminance.')
        result[b'lumi'] = xyz_tag([0,luminance*scale,0])
    header = bytearray(raw[:128])
    if raw[8] == 2:
        # v2 Unicode/ScriptCode records are present even when unused.
        ascii_name = output.name.encode('ascii', errors='replace')+b'\0'
        unicode_name = (output.name+'\0').encode('utf-16-be')
        result[b'desc'] = (b'desc'+bytes(4)+struct.pack('>I',len(ascii_name))+ascii_name
                           +struct.pack('>II',0,len(unicode_name)//2)+unicode_name+bytes(70))
    elif raw[8] == 4:
        name = output.name.encode('utf-16-be')
        result[b'desc'] = b'mluc'+bytes(4)+struct.pack('>II2s2sII',1,12,b'en',b'US',len(name),28)+name
    else:
        raise ValueError('Only ICC v2 and v4 display profiles are supported.')
    header[80:84] = b'    '  # Do not claim Apple authored the recalculated profile.
    data = serialize(header,result)
    if raw[8] == 2: data[84:100] = bytes(16)  # Reserved, not a profile ID in v2.
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as f: f.write(data)
    return {'relative_brightness':scale}


def build_standard_pair(source, output, mhc2_output, exe, primaries=SRGB, white=D65, gamma=2.2):
    """Stage both profiles before publishing; never overwrite an existing file."""
    output, mhc2_output = Path(output), Path(mhc2_output)
    if output.resolve() == mhc2_output.resolve():
        raise ValueError('The two output paths must be different.')
    if any(p.exists() for p in (output,mhc2_output)):
        raise ValueError('Output already exists. Choose a new output name.')
    with tempfile.TemporaryDirectory(prefix='sp-standard-pair-') as temp:
        # Separate folders also allow equal filenames with different destinations.
        device = Path(temp)/'device'/output.name
        windows = Path(temp)/'windows'/mhc2_output.name
        windows.parent.mkdir()
        mhc2_info = build_standard(source,windows,exe,primaries,white,gamma)
        device_info = build_standard_device(source,device,white,gamma)
        created = []
        try:
            for staged,destination in ((device,output),(windows,mhc2_output)):
                destination.parent.mkdir(parents=True,exist_ok=True)
                with destination.open('xb') as f:
                    created.append(destination)
                    f.write(staged.read_bytes())
        except Exception:
            for destination in created: destination.unlink()
            raise
    return {'device':device_info,'mhc2':mhc2_info}


def build_standard(source, output, exe, primaries=SRGB, white=D65, gamma=2.2):
    source,output,exe = map(Path,(source,output,exe))
    if output.exists(): raise ValueError('Output already exists. Choose a new output name.')
    target = rgb_matrix(primaries,white)
    if gamma is not None and (not math.isfinite(gamma) or not .1 <= gamma <= 10):
        raise ValueError('Gamma must be between 0.1 and 10.')
    original = source.read_bytes(); inputs = read_tags(original)
    if original[12:24] != b'mntrRGB XYZ ':
        raise ValueError('Select an RGB/XYZ display ICC profile.')
    if any(s in inputs for s in (b'A2B0',b'B2A0',b'MHC2',b'vcgt')):
        raise ValueError('Standard mode requires an uncalibrated matrix/TRC display description without LUT, MHC2 or VCGT tags. Use Measurement mode for SpaceMan profiles.')
    if not all(s in inputs for s in (b'rXYZ',b'gXYZ',b'bXYZ',b'wtpt',b'rTRC',b'gTRC',b'bTRC')):
        raise ValueError('The ICC is missing RGB colorants, curves or white-point data.')
    curves = [curve_reader(inputs[s]) for s in (b'rTRC',b'gTRC',b'bTRC')]
    for curve in curves:
        samples = [curve(i/4096) for i in range(4097)]
        if not all(math.isfinite(v) for v in samples) or any(a>b+1e-8 for a,b in zip(samples,samples[1:])) or abs(samples[0])>1e-5 or abs(samples[-1]-1)>1e-4:
            raise ValueError('The display TRCs must be monotonic and normalized from 0 to 1.')
    if not exe.is_file(): raise FileNotFoundError('MHC2Gen is missing from the application tools folder.')
    with tempfile.TemporaryDirectory(prefix='sp-icc-') as temp:
        baseline = Path(temp)/'baseline.icc'
        result = subprocess.run([str(exe.resolve()),'sdr-csc','--source-gamut=sRGB','--keep-whitepoint=Bradford','--profile-desc',output.name,str(source.resolve()),str(baseline)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode: raise RuntimeError(result.stderr or result.stdout or 'MHC2Gen failed.')
        base = baseline.read_bytes()
    tags = read_tags(base); mh = bytearray(tags[b'MHC2'])
    n = struct.unpack_from('>I',mh,8)[0]
    mo,*offsets = struct.unpack_from('>4I',mh,20)
    h = struct.unpack_from('>12i',mh,mo)
    H = [[h[i*4+j]/65536 for j in range(3)] for i in range(3)]
    S = rgb_matrix(SRGB,D65)
    native_white = [v/65536 for v in struct.unpack_from('>3i',inputs[b'wtpt'],8)]
    if b'chad' in inputs and original[80:84] != b'appl':
        ch = struct.unpack_from('>9i',inputs[b'chad'],8)
        native_white = vec(inv([[ch[i*3+j]/65536 for j in range(3)] for i in range(3)]),native_white)
    native_white = [x/native_white[1] for x in native_white]
    A = mul(inv(H),S)
    # Recover non-D65 device white that --keep-whitepoint adapted to D65.
    if max(abs(a-b) for a,b in zip(native_white,xyz(D65))) > .0001:
        A = mul(adaptation(xyz(D65),native_white),A)
    C = mul(inv(A),target)
    if min(map(min,C)) < -.0001:
        raise ValueError('The target gamut is outside the display gamut. Choose a smaller target gamut.')
    C = [[max(0,x) for x in row] for row in C]
    scale = min(1,1/max(map(sum,C)))
    gains = [sum(row)*scale for row in C]
    # Keep the exact tested v2/v3 matrix for the original sRGB/D65 scenario.
    native_d65 = max(abs(a-b) for a,b in zip(native_white,xyz(D65))) < .0001
    if tuple(map(tuple,primaries)) == SRGB and tuple(white) == D65 and native_d65:
        gains = [1,1,1]; scale = 1
    else:
        N = [[x/sum(row) for x in row] for row in C]
        matrix = mul(mul(S,N),inv(S))
        struct.pack_into('>12i',mh,mo,*[fixed(x) for row in matrix for x in (*row,0)])
    for off,gain,curve in zip(offsets,gains,curves):
        vals=[]
        for i in range(n):
            x=i/(n-1); y=gain*(decode(x) if gamma is None else x**gamma)
            lo,hi=0.,1.
            for _ in range(40):
                mid=(lo+hi)/2
                if curve(mid)<y: lo=mid
                else: hi=mid
            vals.append(fixed((lo+hi)/2))
        if any(a>b for a,b in zip(vals,vals[1:])): raise ValueError('Generated curve is not monotonic.')
        struct.pack_into('>'+str(n)+'i',mh,off+8,*vals)
    peak=struct.unpack_from('>i',mh,16)[0]/65536*scale
    struct.pack_into('>i',mh,16,fixed(peak))
    tags[b'MHC2']=bytes(mh)
    if gamma is not None:
        for s in (b'rTRC',b'gTRC',b'bTRC'):
            tags[s]=b'para'+bytes(4)+struct.pack('>HHI',0,0,fixed(gamma))
    chad=adaptation(xyz(white),xyz(D50))
    pcs=mul(chad,target)
    tags[b'chad']=b'sf32'+bytes(4)+struct.pack('>9i',*[fixed(x) for row in chad for x in row])
    tags[b'wtpt']=xyz_tag(xyz(D50))
    for j,s in enumerate((b'rXYZ',b'gXYZ',b'bXYZ')): tags[s]=xyz_tag([pcs[i][j] for i in range(3)])
    tags[b'chrm']=b'chrm'+bytes(4)+struct.pack('>HH6I',3,0,*[fixed(x) for pair in primaries for x in pair])
    tags[b'lumi']=xyz_tag([0,peak,0])
    name=output.name.encode('utf-16-be')
    tags[b'desc']=b'mluc'+bytes(4)+struct.pack('>II2s2sII',1,12,b'en',b'US',len(name),28)+name
    data=serialize(base,tags)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f: f.write(data)
    return {'relative_brightness':scale}
