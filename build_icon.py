"""Convert the existing artwork into a multi-resolution Windows icon."""
import struct
from pathlib import Path
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage

root = Path(__file__).resolve().parent
source = QImage(str(root / 'assets/icon-sp.png'))
if source.isNull():
    raise RuntimeError('Cannot read assets/icon-sp.png')
sizes = (16, 24, 32, 48, 64, 128, 256)
images = []
for size in sizes:
    scaled = source.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not scaled.save(buffer, 'PNG'):
        raise RuntimeError('Cannot encode icon')
    images.append(bytes(data))
offset = 6 + 16 * len(sizes)
header = struct.pack('<HHH', 0, 1, len(sizes))
for size, data in zip(sizes, images):
    header += struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0,
                          1, 32, len(data), offset)
    offset += len(data)
(root / 'assets/icon-sp.ico').write_bytes(header + b''.join(images))
