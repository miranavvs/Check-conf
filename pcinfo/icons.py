from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_ACCENTS = {
    "system": "#4c8dff",
    "cpu": "#f0803c",
    "memory": "#9b6dff",
    "gpu": "#e05c8a",
    "sound": "#2fb6a8",
    "board": "#c9a227",
    "bios": "#7a8b99",
    "disk": "#3aa0d1",
    "partitions": "#5f9e6e",
    "network": "#4c8dff",
    "wifi": "#2fb6a8",
    "display": "#e05c8a",
    "battery": "#69c24a",
    "temp": "#ef6a4a",
    "usb": "#b58b2a",
    "load": "#8a94a6",
}

_SHAPES = {
    "system": '<rect x="2.5" y="3.5" width="19" height="13" rx="2"/><path d="M8 20.5h8"/><path d="M12 16.5v4"/>',
    "cpu": '<rect x="7" y="7" width="10" height="10" rx="1.5"/><rect x="10" y="10" width="4" height="4"/>'
    '<path d="M10 7V4M14 7V4M10 17v3M14 17v3M7 10H4M7 14H4M17 10h3M17 14h3"/>',
    "memory": '<rect x="2" y="7" width="20" height="9" rx="1.5"/>'
    '<path d="M6 7v9M9 7v9M12 7v9M15 7v9M18 7v9M4.5 16v2.5M19.5 16v2.5"/>',
    "gpu": '<rect x="2" y="5" width="20" height="12.5" rx="2"/><circle cx="8" cy="11.2" r="3.4"/>'
    '<path d="M14 8.5h6M14 11.2h6M14 13.9h6M5 17.5v2.5M9.5 17.5v2.5"/>',
    "sound": '<rect x="1.5" y="9" width="4.5" height="6" rx="1"/><path d="M6 9.6 11 5.6v12.8L6 14.4z"/>'
    '<path d="M14.4 8.6a5.6 5.6 0 0 1 0 6.8M17.4 5.8a9.4 9.4 0 0 1 0 12.4"/>',
    "board": '<rect x="3" y="3" width="18" height="18" rx="2"/><rect x="7.5" y="7.5" width="9" height="9" rx="1"/>'
    '<path d="M3 8.5h4.5M3 15.5h4.5M16.5 8.5H21M16.5 15.5H21M9 21v-4.5M15 21v-4.5"/>',
    "bios": '<rect x="4" y="6" width="16" height="12" rx="2"/><rect x="8.5" y="9.5" width="7" height="5" rx="1"/>'
    '<path d="M12 6V2.5M12 18v3.5M8 6V3.5M16 6V3.5M8 18v2.5M16 18v2.5"/>',
    "disk": '<rect x="2" y="5" width="20" height="14" rx="2.5"/><circle cx="12" cy="12" r="4"/>'
    '<path d="M2 9.2h20"/><circle cx="12" cy="12" r="0.9"/>',
    "partitions": '<circle cx="12" cy="12" r="9"/><path d="M12 12V3M12 12l7.8 4.5M12 12v9"/>',
    "network": '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3.4 9.2h17.2M3.4 14.8h17.2"/>',
    "wifi": '<path d="M2.6 8.6a13.4 13.4 0 0 1 18.8 0M5.8 12a8.6 8.6 0 0 1 12.4 0M9 15.4a3.8 3.8 0 0 1 6 0"/>'
    '<circle cx="12" cy="19" r="1.4"/>',
    "display": '<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "battery": '<rect x="2" y="7.5" width="16.5" height="9" rx="2"/><path d="M20.8 10.5v3"/>'
    '<rect x="4" y="9.5" width="7" height="5" rx="0.8"/>',
    "temp": '<path d="M10.4 13.6V5.4a1.8 1.8 0 0 1 3.6 0v8.2a4 4 0 1 1-3.6 0z"/><path d="M12 9.5v5.2"/>'
    '<path d="M17.5 6.5h3M17.5 10h3M17.5 13.5h3"/>',
    "usb": '<path d="M12 3.5v11"/><circle cx="12" cy="3" r="1.2"/>'
    '<path d="M12 8.5 8 12.5M12 11.5l4 4"/>'
    '<circle cx="7.6" cy="13.4" r="1.2"/><circle cx="16.4" cy="16.4" r="1.2"/>'
    '<rect x="9.5" y="15" width="5" height="5.5" rx="1"/>',
    "load": '<path d="M3.6 18.5a9 9 0 1 1 16.8 0"/><path d="M12 18.5 16.4 11.4"/><circle cx="12" cy="18.5" r="1.3"/>',
}

_CACHE = {}


def accent(name: str) -> str:
    return _ACCENTS.get(name, _ACCENTS["load"])


def svg_body(name: str, color: str, size: int = 64) -> bytes:
    shapes = _SHAPES.get(name, _SHAPES["load"])
    doc = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round">{shapes}</svg>'
    )
    return doc.encode("utf-8")


def icon(name: str, color: str = "#8a94a6", size: int = 64) -> QIcon:
    cache_key = (name, color, size)
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    pixmap = QPixmap()
    pixmap.loadFromData(QByteArray(svg_body(name, color, size)), "SVG")
    if pixmap.isNull():
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
    result = QIcon(pixmap)
    _CACHE[cache_key] = result
    return result


def app_pixmap(size: int = 256) -> QPixmap:
    key = ("__app__", size)
    if key in _CACHE:
        return _CACHE[key]
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    ratio = size / 64.0
    painter.scale(ratio, ratio)

    plate = QRectF(2, 2, 60, 60)
    path = QPainterPath()
    path.addRoundedRect(plate, 14, 14)
    painter.fillPath(path, QColor("#1b2331"))
    painter.setPen(QPen(QColor("#3d4b60"), 1.6))
    painter.drawPath(path)

    pen = QPen(QColor("#4c8dff"), 2.4)
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(QRectF(20, 20, 24, 24), 4, 4)
    painter.drawRoundedRect(QRectF(27, 27, 10, 10), 2, 2)
    for dx, dy in ((28, 20), (36, 20), (28, 44), (36, 44), (20, 28), (20, 36), (44, 28), (44, 36)):
        painter.drawLine(dx, dy, dx, dy)
    painter.setPen(QPen(QColor("#2fb6a8"), 2.0))
    painter.drawLine(52, 32, 58, 32)
    painter.drawLine(52, 32, 55, 28)
    painter.drawLine(52, 32, 55, 36)
    painter.end()
    _CACHE[key] = pixmap
    return pixmap
