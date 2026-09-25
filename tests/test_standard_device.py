"""Device calibration, verified-reference regression, and pair safety tests."""
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.build_standard import (
    build_standard_device, build_standard_pair, curve_reader, read_tags,
    rgb_matrix, adaptation, mul, vec, inv, xyz, xyz_tag, serialize, decode,
    D50, D65, SRGB,
)

ROOT = Path(__file__).resolve().parents[1]
ADOBE = Path('/System/Library/ColorSync/Profiles/AdobeRGB1998.icc')
if not ADOBE.exists(): ADOBE = ROOT/'tests/fixtures/AdobeRGB1998.icc'


def readxyz(payload):
    return [v/65536 for v in struct.unpack_from('>3i',payload,8)]


def ramps(tags):
    payload = tags[b'vcgt']
    kind, channels, count, size = struct.unpack_from('>IHHH',payload,8)
    assert (kind,channels,size) == (0,3,2)
    values = struct.unpack_from('>'+str(3*count)+'H',payload,18)
    return [[v/65535 for v in values[i*count:(i+1)*count]] for i in range(3)]


def synthesize(path, white=D65, gamma=2.2, version=4):
    native = rgb_matrix(((.64,.33),(.21,.71),(.15,.06)),white)
    pcswhite = [.9642,1,.8249]
    chad = adaptation(xyz(white),pcswhite)
    pcs = mul(chad,native)
    header = bytearray(128)
    header[8] = version
    header[12:24] = b'mntrRGB XYZ '
    header[36:40] = b'acsp'
    header[68:80] = xyz_tag(pcswhite)[8:]
    struct.pack_into('>6H',header,24,2026,9,25,0,0,0)
    tags = {b'wtpt':xyz_tag(pcswhite), b'lumi':xyz_tag([0,120,0])}
    tags[b'chad'] = b'sf32'+bytes(4)+struct.pack('>9i',*[round(x*65536) for row in chad for x in row])
    for j,s in enumerate((b'rXYZ',b'gXYZ',b'bXYZ')):
        tags[s] = xyz_tag([pcs[i][j] for i in range(3)])
    for s in (b'rTRC',b'gTRC',b'bTRC'):
        tags[s] = b'para'+bytes(4)+struct.pack('>HHi',0,0,round(gamma*65536))
    path.write_bytes(serialize(header,tags))


class DeviceTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'darwin','macOS ColorSync required')
    def test_native_colorsync(self):
        import ctypes as c
        cf = c.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        cs = c.CDLL('/System/Library/Frameworks/ColorSync.framework/ColorSync')
        cf.CFDataCreate.argtypes = [c.c_void_p,c.c_void_p,c.c_long]
        cf.CFDataCreate.restype = c.c_void_p
        cf.CFRelease.argtypes = [c.c_void_p]
        cf.CFStringGetCString.argtypes = [c.c_void_p,c.c_void_p,c.c_long,c.c_uint32]
        cf.CFStringGetCString.restype = c.c_bool
        cs.ColorSyncProfileCreate.argtypes = [c.c_void_p,c.c_void_p]
        cs.ColorSyncProfileCreate.restype = c.c_void_p
        cs.ColorSyncProfileVerify.argtypes = [c.c_void_p,c.c_void_p,c.c_void_p]
        cs.ColorSyncProfileVerify.restype = c.c_bool
        cs.ColorSyncProfileCopyDescriptionString.argtypes = [c.c_void_p]
        cs.ColorSyncProfileCopyDescriptionString.restype = c.c_void_p
        cs.ColorSyncProfileCreateDisplayTransferTablesFromVCGT.argtypes = [c.c_void_p,c.POINTER(c.c_size_t)]
        cs.ColorSyncProfileCreateDisplayTransferTablesFromVCGT.restype = c.c_void_p
        with tempfile.TemporaryDirectory() as tmp:
            for version in (2,4):
                source = Path(tmp)/'source.icc'; synthesize(source,version=version)
                out = Path(tmp)/f'螢幕 D50-v{version}.icc'
                build_standard_device(source,out,white=D50)
                raw = out.read_bytes(); buf = c.create_string_buffer(raw)
                data = cf.CFDataCreate(None,buf,len(raw))
                profile = cs.ColorSyncProfileCreate(data,None)
                self.assertTrue(profile)
                try:
                    self.assertTrue(cs.ColorSyncProfileVerify(profile,None,None))
                    desc = cs.ColorSyncProfileCopyDescriptionString(profile)
                    self.assertTrue(desc)
                    try:
                        text = c.create_string_buffer(1024)
                        self.assertTrue(cf.CFStringGetCString(desc,text,1024,0x08000100))
                        self.assertEqual(text.value.decode('utf-8'),out.name)
                    finally: cf.CFRelease(desc)
                    count = c.c_size_t()
                    table = cs.ColorSyncProfileCreateDisplayTransferTablesFromVCGT(profile,c.byref(count))
                    self.assertTrue(table)
                    try: self.assertGreater(count.value,0)
                    finally: cf.CFRelease(table)
                finally:
                    cf.CFRelease(profile); cf.CFRelease(data)

    @unittest.skipUnless(ADOBE.exists(),'Adobe reference profile required')
    def test_verified_v6mac(self):
        ref = ROOT/'output/AdobeRGB1998-mhc2-windows-test-v6mac.icc'
        if not ref.exists(): ref = ROOT/'tests/fixtures'/ref.name
        if not ref.exists(): self.skipTest('User-verified v6mac required')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'v6.icc'
            build_standard_device(ADOBE,out,white=D50,gamma=2.19921875)
            actual, expected = read_tags(out.read_bytes()), read_tags(ref.read_bytes())
            for sig in (b'rXYZ',b'gXYZ',b'bXYZ',b'rTRC',b'gTRC',b'bTRC',b'wtpt',b'chad',b'vcgt'):
                self.assertEqual(actual[sig],expected[sig],sig)

    def test_calibrated_response_and_real_gamut(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for native_white in (D65,D50):
                source = tmp/'source.icc'; synthesize(source,white=native_white)
                source_tags = read_tags(source.read_bytes())
                ch = struct.unpack_from('>9i',source_tags[b'chad'],8)
                ch = [[v/65536 for v in ch[i:i+3]] for i in (0,3,6)]
                pcs = list(map(list,zip(*(readxyz(source_tags[s]) for s in (b'rXYZ',b'gXYZ',b'bXYZ')))))
                native = mul(inv(ch),pcs)
                for target_white in (D65,D50,(.33,.34)):
                    for gamma in (2.2,2.4,None):
                        out = tmp/f'{native_white}-{target_white}-{gamma}.icc'
                        info = build_standard_device(source,out,white=target_white,gamma=gamma)
                        data = out.read_bytes(); tags = read_tags(data)
                        self.assertEqual(struct.unpack_from('>I',data,0)[0],len(data))
                        self.assertNotIn(b'MHC2',tags)
                        self.assertNotIn(b'A2B0',tags)
                        self.assertEqual(tags[b'desc'][28:].decode('utf-16-be'),out.name)
                        rr = ramps(tags)
                        original_curves = [curve_reader(source_tags[s]) for s in (b'rTRC',b'gTRC',b'bTRC')]
                        white = vec(native,[f(r[-1]) for f,r in zip(original_curves,rr)])
                        xy = [white[0]/sum(white),white[1]/sum(white)]
                        for a,b in zip(xy,target_white): self.assertAlmostEqual(a,b,places=4)
                        self.assertAlmostEqual(readxyz(tags[b'lumi'])[1],120*info['relative_brightness'],places=4)
                        for s,curve,ramp in zip((b'rTRC',b'gTRC',b'bTRC'),original_curves,rr):
                            self.assertTrue(all(a<=b for a,b in zip(ramp,ramp[1:])))
                            trc = curve_reader(tags[s])
                            gain = curve(ramp[-1])
                            for i,value in enumerate(ramp):
                                x = i/(len(ramp)-1)
                                expected = decode(x) if gamma is None else x**gamma
                                self.assertLess(abs(curve(value)/gain-expected),.00015)
                                self.assertLess(abs(trc(x)-expected),.00003)
                        values = struct.unpack_from('>9i',tags[b'chad'],8)
                        new_chad = [[v/65536 for v in values[i:i+3]] for i in (0,3,6)]
                        new_pcs = list(map(list,zip(*(readxyz(tags[s]) for s in (b'rXYZ',b'gXYZ',b'bXYZ')))))
                        new_native = mul(inv(new_chad),new_pcs)
                        for j in range(3):
                            old = [native[i][j] for i in range(3)]
                            new = [new_native[i][j] for i in range(3)]
                            for a,b in zip(old,new): self.assertLess(abs(a/sum(old)-b/sum(new)),.0001)

    def test_reject_and_preserve_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'source.icc'; synthesize(source)
            for args in ({'white':(.8,.8)}, {'gamma':math.nan}, {'gamma':0}, {'white':(.9,.05)}):
                out = Path(tmp)/'bad.icc'
                with self.assertRaises(ValueError): build_standard_device(source,out,**args)
                self.assertFalse(out.exists())
            out = Path(tmp)/'existing.icc'; out.write_bytes(b'keep')
            with self.assertRaises(ValueError): build_standard_device(source,out)
            self.assertEqual(out.read_bytes(),b'keep')

    def test_v2_unicode_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'source.icc'; synthesize(source,version=2)
            out = Path(tmp)/'螢幕 D50.icc'
            build_standard_device(source,out,white=D50)
            data = out.read_bytes(); desc = read_tags(data)[b'desc']
            length = struct.unpack_from('>I',desc,8)[0]
            count = struct.unpack_from('>I',desc,12+length+4)[0]
            self.assertEqual(desc[20+length:20+length+2*count].decode('utf-16-be').rstrip('\0'),out.name)
            self.assertEqual(data[84:100],bytes(16))

    def test_pair_failure_leaves_no_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = tmp/'source.icc'; synthesize(source)
            out, mhc = tmp/'pair.icc',tmp/'pair-mhc2.icc'
            def fake_windows(source,output,*args): output.write_bytes(b'staged')
            with patch('src.build_standard.build_standard',side_effect=fake_windows), patch('src.build_standard.build_standard_device',side_effect=ValueError('failure')):
                with self.assertRaises(ValueError): build_standard_pair(source,out,mhc,tmp/'tool')
            self.assertFalse(out.exists()); self.assertFalse(mhc.exists())
            mhc.write_bytes(b'keep')
            with self.assertRaises(ValueError): build_standard_pair(source,out,mhc,tmp/'tool')
            self.assertFalse(out.exists()); self.assertEqual(mhc.read_bytes(),b'keep')


if __name__ == '__main__': unittest.main()
