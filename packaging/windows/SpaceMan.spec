"""Windows x64 single-file build, following the verified 1.0.1 layout."""
from pathlib import Path
import PySide6

root = Path(SPECPATH).parents[1]
qt = Path(PySide6.__file__).parent
tool = root/'tools/mhc2gen/MHC2Gen.exe'
icon = root/'assets/icon-sp.ico'
for required in (tool,icon):
    if not required.is_file(): raise SystemExit(f'Missing build resource: {required}')
a = Analysis([str(root/'preview_v110.py')],pathex=[str(root)],
    binaries=[(str(qt/name),'.') for name in ('vcruntime140.dll','vcruntime140_1.dll')],
    datas=[(str(icon),'assets'),(str(root/'assets/icon-sp.png'),'assets'),
           (str(tool),'tools/mhc2gen'),
           (str(root/'LICENSE'),'licenses'),
           (str(root/'THIRD_PARTY_NOTICES.md'),'licenses')],
    hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],
    excludes=[],noarchive=False)
# Retain the previously validated defense against Poppler ICU on PATH.
a.binaries=[item for item in a.binaries if Path(item[0]).name.lower() not in {'icuuc.dll','icudt78.dll'}]
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='SpaceMan ICC Bridge',
    debug=False,bootloader_ignore_signals=False,strip=False,upx=False,
    console=False,icon=str(icon),version=str(root/'packaging/windows/version.txt'))
