"""Run with QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests."""
import os
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest.mock import patch

from src.build_standard import build_standard, read_tags, D50, D65

ROOT = Path(__file__).resolve().parents[1]
ADOBE = Path('/System/Library/ColorSync/Profiles/AdobeRGB1998.icc')
if not ADOBE.exists():
    ADOBE = ROOT/'tests/fixtures/AdobeRGB1998.icc'
EXE = ROOT/'tools/mhc2gen'/('MHC2Gen.exe' if os.name == 'nt' else 'MHC2Gen')


class StandardTests(unittest.TestCase):
    @unittest.skipUnless(ADOBE.exists(), 'macOS reference profile required')
    def test_verified_reference_transforms(self):
        with tempfile.TemporaryDirectory() as tmp:
            for version, white, gamma in ((2,D65,None),(3,D65,2.2),(4,D50,2.2)):
                ref=ROOT/f'output/AdobeRGB1998-mhc2-windows-test-v{version}.icc'
                if not ref.exists(): ref=ROOT/'tests/fixtures'/ref.name
                if not ref.exists(): self.skipTest('User-verified reference files required')
                out=Path(tmp)/f'測試 v{version}.icc'
                build_standard(ADOBE,out,EXE,white=white,gamma=gamma)
                data=out.read_bytes(); a=read_tags(data); b=read_tags(ref.read_bytes())
                self.assertEqual(a[b'desc'][28:].decode('utf-16-be'),out.name)
                self.assertEqual(a[b'MHC2'][36:84],b[b'MHC2'][36:84])
                for off in struct.unpack_from('>3I',a[b'MHC2'],24):
                    av=struct.unpack_from('>1024i',a[b'MHC2'],off+8)
                    bv=struct.unpack_from('>1024i',b[b'MHC2'],off+8)
                    self.assertLessEqual(max(abs(x-y) for x,y in zip(av,bv)),1)
                with self.assertRaises(ValueError): build_standard(ADOBE,out,EXE)
                self.assertEqual(out.read_bytes(),data)

    @unittest.skipUnless(ADOBE.exists(), 'macOS reference profile required')
    def test_invalid_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'bad.icc'
            for args in ({'white':(.8,.8)}, {'gamma':float('nan')}, {'primaries':((.64,.33),)*3}, {'primaries':((.68,.32),(.265,.69),(.15,.06))}):
                with self.assertRaises(ValueError): build_standard(ADOBE,out,EXE,**args)
                self.assertFalse(out.exists())


class UiTests(unittest.TestCase):
    @unittest.skipUnless(ADOBE.exists(), 'macOS reference profile required')
    def test_both_generate_buttons(self):
        from PySide6.QtWidgets import QApplication
        import preview_v110 as ui
        from src.build_icc_from_bcs import tag_block
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp, patch.object(ui.existing,'save'), patch.object(ui.QMessageBox,'information') as done, patch.object(ui.QMessageBox,'critical') as error:
            tmp=Path(tmp)
            w=ui.PreviewWindow(); w.timer.stop(); w.show(); app.processEvents()
            try:
                w.mode_buttons[1].click()
                w.drop_source('icc_dir',('.icc','.icm'),[str(ADOBE)])
                w.set_output(str(tmp)); w.name.setText('standard'); w.white.setCurrentText('D50')
                w.generate.click()
                deadline=time.monotonic()+15
                while w.busy and time.monotonic()<deadline:
                    app.processEvents(); time.sleep(.01)
                self.assertFalse(w.busy)
                self.assertFalse(error.called,error.call_args)
                self.assertIn(b'MHC2',read_tags((tmp/'standard-mhc2.icc').read_bytes()))
                ref=ROOT/'output/AdobeRGB1998-mhc2-windows-test-v4.icc'
                if not ref.exists(): ref=ROOT/'tests/fixtures'/ref.name
                if ref.exists():
                    self.assertEqual(read_tags((tmp/'standard-mhc2.icc').read_bytes())[b'MHC2'],read_tags(ref.read_bytes())[b'MHC2'])
                self.assertIn(b'vcgt',read_tags((tmp/'standard.icc').read_bytes()))
                self.assertNotIn(b'MHC2',read_tags((tmp/'standard.icc').read_bytes()))
                self.assertIn(str(tmp/'standard.icc'),done.call_args.args[2])
                self.assertIn(str(tmp/'standard-mhc2.icc'),done.call_args.args[2])
                # A collision in either member blocks the whole pair before work.
                before=(tmp/'standard.icc').read_bytes()
                w.generate.click()
                self.assertTrue(error.called)
                self.assertEqual((tmp/'standard.icc').read_bytes(),before)
                error.reset_mock()
                w.timer.stop()

                raw=tmp/'raw.icc'
                vcgt=struct.pack('>4s4xIHHH',b'vcgt',0,3,2,2)+struct.pack('>6H',*([0,65535]*3))
                raw.write_bytes(tag_block({b'vcgt':vcgt,b'cprt':b'text\0\0\0\0Synthetic test\0'}))
                rows=[(0,0,0,0,0,0),(255,255,255,95.047,100,108.883),(255,0,0,41.24564,21.26729,1.93339),(0,255,0,35.75761,71.51522,11.91920),(0,0,255,18.04375,7.21750,95.03041),(128,128,128,20.52,21.59,23.50)]
                csv=tmp/'synthetic.csv'; csv.write_text('R,G,B,X,Y,Z\n'+'\n'.join(','.join(map(str,r)) for r in rows))
                cube=tmp/'identity.cube'; cube.write_text('LUT_1D_SIZE 2\n0 0 0\n1 1 1\n')
                w.mode_buttons[0].click()
                for key,ext,p in [('bcs_dir',('.csv',),csv),('cube_dir',('.cube',),cube),('icc_dir',('.icc',),raw)]: w.drop_source(key,ext,[str(p)])
                w.name.setText('measurement'); w.generate.click()
                self.assertFalse(error.called,error.call_args)
                self.assertIn(b'vcgt',read_tags((tmp/'measurement.icc').read_bytes()))
                self.assertIn(b'MHC2',read_tags((tmp/'measurement-mhc2.icc').read_bytes()))
                self.assertEqual(done.call_count,2)
                self.assertEqual((w.width(),w.height()),(560,560))
            finally:
                if hasattr(w,'worker'): w.worker.wait()
                w.busy=False; w.close()


if __name__=='__main__': unittest.main()
