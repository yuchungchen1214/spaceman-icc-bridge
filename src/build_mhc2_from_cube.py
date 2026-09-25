import hashlib, struct
from pathlib import Path

def apply_cube_gray_to_mhc2(profile, cube, output):
    vals=[]
    lut_1d_size = None
    lut_3d_size = None
    for line in Path(cube).read_text(encoding='ascii',errors='replace').splitlines():
        header = line.strip().split()
        if len(header) == 2 and header[0].upper() == 'LUT_1D_SIZE':
            try: lut_1d_size = int(header[1])
            except ValueError: pass
        elif len(header) == 2 and header[0].upper() == 'LUT_3D_SIZE':
            try: lut_3d_size = int(header[1])
            except ValueError: pass
        p=line.strip().split()
        if len(p)==3:
            try: vals.append(tuple(map(float,p)))
            except ValueError: pass
    if lut_1d_size is not None:
        if lut_1d_size < 2 or len(vals) != lut_1d_size:
            raise ValueError('LUT.cube 1D data count does not match LUT_1D_SIZE.')
        # ColourSpace 1D exports already contain the three RGB regamma curves.
        gray = vals
        n = lut_1d_size
    else:
        n = lut_3d_size or round(len(vals)**(1/3))
        if n < 2 or n**3 != len(vals):
            raise ValueError('LUT.cube is not a valid 1D or cubic 3D LUT.')
        gray=[vals[i*n*n+i*n+i] for i in range(n)]
    def interp(c,x):
        z=max(0,min(1,x))*(n-1); i=min(int(z),n-2); f=z-i
        return gray[i][c]*(1-f)+gray[i+1][c]*f
    b=bytearray(Path(profile).read_bytes()); count=struct.unpack_from('>I',b,128)[0]; found=None
    for i in range(count):
        s,o,z=struct.unpack_from('>4sII',b,132+i*12)
        if s==b'MHC2': found=(o,z); break
    if not found: raise ValueError('MHC2 tag is missing from the intermediate profile.')
    o,z=found; mh=bytearray(b[o:o+z]); offs=struct.unpack_from('>4I',mh,20)
    for c,off in enumerate(offs[1:]):
        for j in range(1023): struct.pack_into('>i',mh,off+12+j*4,round(interp(c,j/1022)*65536))
    b[o:o+z]=mh; b[84:100]=b'\0'*16; b[84:100]=hashlib.md5(b).digest(); Path(output).write_bytes(b)
