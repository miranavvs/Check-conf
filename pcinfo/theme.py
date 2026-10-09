from __future__ import annotations

BG = "#121821"
SURFACE = "#1b2331"
SURFACE_ALT = "#222d3e"
BORDER = "#2c3a4e"
TEXT = "#e6ecf5"
MUTED = "#8a94a6"
FAINT = "#5d6a7d"
ACCENT = "#4c8dff"
OK = "#69c24a"
WARN = "#f0a83c"
BAD = "#ef6a4a"

LEVEL_COLORS = {"info": TEXT, "warn": WARN, "bad": BAD}

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}

QFrame#Header {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}
QLabel#AppTitle {{
    font-size: 19px;
    font-weight: 600;
}}
QLabel#AppSubtitle {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#HostInfo {{
    color: {MUTED};
    font-size: 12px;
}}

QFrame#Toolbar {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}
QLineEdit#Search {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 11px;
    selection-background-color: {ACCENT};
}}
QLineEdit#Search:focus {{
    border: 1px solid {ACCENT};
}}

QPushButton {{
    background: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    border: 1px solid {ACCENT};
    color: #ffffff;
}}
QPushButton:pressed {{
    background: {BORDER};
}}
QPushButton:disabled {{
    color: {FAINT};
    border: 1px solid {BORDER};
    background: {SURFACE};
}}
QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#Primary:hover {{
    background: #3d7ded;
    border: 1px solid #3d7ded;
}}
QPushButton#Primary:disabled {{
    background: #2b4a80;
    border: 1px solid #2b4a80;
    color: {FAINT};
}}

QCheckBox {{
    spacing: 7px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {BG};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
}}

QComboBox {{
    background: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 6px 10px;
    min-width: 96px;
}}
QComboBox:hover {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_ALT};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    outline: none;
}}

QListWidget#Sections {{
    background: {SURFACE};
    border: none;
    border-right: 1px solid {BORDER};
    outline: none;
    padding: 8px 0;
}}
QListWidget#Sections::item {{
    padding: 0px;
    margin: 1px 8px;
    border-radius: 7px;
    color: {MUTED};
}}
QListWidget#Sections::item:hover {{
    background: {SURFACE_ALT};
    color: {TEXT};
}}
QListWidget#Sections::item:selected {{
    background: {SURFACE_ALT};
    color: #ffffff;
}}

QScrollArea {{
    border: none;
    background: {BG};
}}
QScrollArea > QWidget > QWidget {{
    background: {BG};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {MUTED};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
    width: 0px;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}

QFrame#Summary {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}
QFrame#Chip {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 9px;
}}
QLabel#ChipKey {{
    color: {MUTED};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#ChipValue {{
    color: {TEXT};
    font-size: 13px;
    font-weight: 600;
}}
QFrame#Card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 11px;
}}
QLabel#CardTitle {{
    font-size: 14px;
    font-weight: 600;
}}
QLabel#CardCount {{
    color: {MUTED};
    font-size: 11px;
    background: {SURFACE_ALT};
    border-radius: 8px;
    padding: 2px 8px;
}}
QFrame#CardRule {{
    background: {BORDER};
    border: none;
}}
QLabel#GroupTitle {{
    color: {ACCENT};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    padding-top: 9px;
    padding-bottom: 1px;
}}
QLabel#CardEmpty {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#FieldKey {{
    color: {MUTED};
}}
QLabel#FieldValue {{
    color: {TEXT};
    font-weight: 500;
}}
QLabel#CardError {{
    color: {WARN};
    font-size: 11px;
}}
QLabel#Empty {{
    color: {MUTED};
    font-size: 14px;
}}

QStatusBar {{
    background: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {MUTED};
}}
QStatusBar::item {{
    border: none;
}}
QProgressBar {{
    background: {SURFACE_ALT};
    border: none;
    border-radius: 3px;
    height: 5px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}

QToolTip {{
    background: {SURFACE_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 5px;
}}
"""


def level_color(level: str) -> str:
    return LEVEL_COLORS.get(level, TEXT)
