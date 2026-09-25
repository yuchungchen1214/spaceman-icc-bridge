# Third-party software notices

SpaceMan ICC Bridge uses and redistributes the following third-party software.

## MHC2Gen

The MHC2 profile-generation helper is from [dantmnf/MHC2](https://github.com/dantmnf/MHC2), released under the [Unlicense](https://github.com/dantmnf/MHC2/blob/master/LICENSE).

The Windows helper in `tools/mhc2gen/MHC2Gen.exe` is upstream development build `1.0.0+82ebd2726afde770627cf45456ef55c83392c840`. Its original archive SHA-256 is recorded in [`tools/mhc2gen/SOURCE.txt`](tools/mhc2gen/SOURCE.txt).

The macOS arm64 helper in `tools/mhc2gen/runtime/MHC2Gen` is the self-contained .NET 8 build used by this application. It includes the .NET runtime; see [Microsoft .NET licensing](https://dotnet.microsoft.com/en-us/dotnet). Its SHA-256 is recorded in `tools/mhc2gen/SOURCE-MACOS.txt`.

## Qt for Python (PySide6) and Qt

The graphical interface uses PySide6 and Qt. These components are available under LGPLv3/GPLv3 and commercial terms. See the [Qt for Python licensing page](https://doc.qt.io/qtforpython-6/licenses.html) and the license files included with the corresponding distributions.

## PyInstaller

PyInstaller is used to package the desktop applications. It is distributed under the GNU General Public License with a special exception; see the [PyInstaller license](https://pyinstaller.org/en/stable/license.html).

## Python

Packaged applications include the Python interpreter. See the [Python license](https://docs.python.org/3/license.html).

The dependency versions used for a source install and Windows packaging are listed in [`requirements.txt`](requirements.txt) and [`requirements-windows-lock.txt`](requirements-windows-lock.txt).
