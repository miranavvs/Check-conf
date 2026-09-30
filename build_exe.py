"""Build a single-file Windows executable with PyInstaller.

    .venv\\Scripts\\python.exe -m pip install pyinstaller
    .venv\\Scripts\\python.exe build_exe.py

Output: dist\\check-conf.exe
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "check-conf"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


_app = None


def _png(size: int) -> bytes:
    global _app

    from PySide6.QtCore import QBuffer, QByteArray
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from pcinfo.icons import app_pixmap

    if _app is None:
        _app = QApplication([])

    store = QByteArray()
    buf = QBuffer(store)
    buf.open(QBuffer.WriteOnly)
    app_pixmap(size).toImage().save(buf, "PNG")
    buf.close()
    return bytes(store)


def build_icon() -> str:
    """Render the .ico from the same code the window uses, so both match."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    images = [_png(s) for s in ICON_SIZES]
    count = len(images)
    offset = 6 + 16 * count
    header = struct.pack("<HHH", 0, 1, count)
    entries, blobs = b"", b""
    for size, data in zip(ICON_SIZES, images):
        entries += struct.pack(
            "<BBBBHHII",
            size % 256,
            size % 256,
            0,
            0,
            1,
            32,
            len(data),
            offset,
        )
        blobs += data
        offset += len(data)
    path = os.path.join(ROOT, "build", "deepcode.ico")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(header + entries + blobs)
    return path


def main() -> int:
    icon = build_icon()
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        NAME,
        "--icon",
        icon,
        "--hidden-import",
        "pcinfo.collectors.windows",
        os.path.join(ROOT, "main.py"),
    ]
    print(" ".join(cmd))
    code = subprocess.call(cmd, cwd=ROOT)
    if code == 0:
        exe = os.path.join(ROOT, "dist", NAME + ".exe")
        size = os.path.getsize(exe) / (1024 * 1024)
        print(f"\nOK -> {exe} ({size:.1f} Mo)")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
