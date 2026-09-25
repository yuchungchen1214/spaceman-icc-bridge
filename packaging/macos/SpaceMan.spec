# macOS 1.1.0: isolated build, preserving earlier release artifacts.
from pathlib import Path
root = Path(SPECPATH).parents[1]
a = Analysis([str(root/'preview_v110.py')], pathex=[str(root)],
             binaries=[], datas=[(str(root/'assets'),'assets'),
                                  (str(root/'tools/mhc2gen/MHC2Gen'),'tools/mhc2gen'),
                                  (str(root/'tools/mhc2gen/runtime/MHC2Gen'),'tools/mhc2gen/runtime'),
                                  (str(root/'LICENSE'),'licenses'),
                                  (str(root/'THIRD_PARTY_NOTICES.md'),'licenses')],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='SpaceMan ICC Bridge',
          debug=False,bootloader_ignore_signals=False,strip=False,upx=False,
          console=False,argv_emulation=False,target_arch='arm64',
          codesign_identity=None,entitlements_file=None)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='SpaceMan ICC Bridge')
app = BUNDLE(coll,name='SpaceMan ICC Bridge.app',icon=str(root/'assets/icon-sp.icns'),
             bundle_identifier='com.spaceman.iccbridge',
             info_plist={'CFBundleShortVersionString':'1.1.0',
                         'CFBundleVersion':'1.1.0',
                         'UIDesignRequiresCompatibility':True,
                         'NSHighResolutionCapable':True})
