"""Colours and the stylesheet.

A console that is read in daylight, under a canopy, for half an hour at a
time. Dark so the screen is not the brightest thing in the tent, high
contrast, and only four status colours so they mean something: green
nominal, amber degraded, red fault, blue manual.
"""

BG = '#0e1116'
PANEL = '#161b22'
PANEL_HI = '#1c2430'
EDGE = '#2a3441'
TEXT = '#dbe3ed'
DIM = '#8b99ab'

OK = '#3fb950'
WARN = '#d6a132'
FAULT = '#f2564a'
INFO = '#58a6ff'
IDLE_GREY = '#6b7785'

STATE_COLORS = {'ok': OK, 'warn': WARN, 'fault': FAULT, 'info': INFO,
                'stale': WARN, 'idle': IDLE_GREY}

MONO = 'DejaVu Sans Mono'

STYLESHEET = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-family: 'DejaVu Sans'; font-size: 13px; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid {EDGE}; border-radius: 6px; }}
QLabel#panelTitle {{ color: {DIM}; font-size: 11px; font-weight: 600; letter-spacing: 1.4px; }}
QLabel#tileTitle {{ color: {DIM}; font-size: 10px; font-weight: 600; letter-spacing: 1.2px; }}
QLabel#tileValue {{ font-family: '{MONO}'; font-size: 23px; font-weight: 700; }}
QLabel#tileSub {{ color: {DIM}; font-size: 10px; font-family: '{MONO}'; }}
QLabel#bannerTitle {{ font-size: 17px; font-weight: 700; letter-spacing: 1.5px; }}
QLabel#clock {{ font-family: '{MONO}'; font-size: 26px; font-weight: 700; }}

QPushButton {{
    background: {PANEL_HI}; border: 1px solid {EDGE}; border-radius: 5px;
    padding: 9px 14px; font-weight: 600; letter-spacing: 0.6px;
}}
QPushButton:hover {{ background: #24303e; border-color: #3a4757; }}
QPushButton:pressed {{ background: #2d3b4c; }}
QPushButton:disabled {{ color: #4d5867; border-color: #202834; }}
QPushButton#abort {{
    background: #5c1b17; border: 1px solid {FAULT}; color: #ffd9d6;
    font-size: 16px; font-weight: 800; letter-spacing: 2px; padding: 16px;
}}
QPushButton#abort:hover {{ background: #7a221c; }}
QPushButton#primary {{ background: #16361f; border-color: {OK}; color: #c6f0cf; }}
QPushButton#primary:hover {{ background: #1d4a2a; }}

QTableWidget {{
    background: {PANEL}; gridline-color: {EDGE}; border: none;
    font-family: '{MONO}'; font-size: 12px; selection-background-color: #23384f;
}}
QHeaderView::section {{
    background: {PANEL}; color: {DIM}; border: none; border-bottom: 1px solid {EDGE};
    padding: 6px; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}}
QPlainTextEdit {{
    background: #0b0e13; border: 1px solid {EDGE}; border-radius: 6px;
    font-family: '{MONO}'; font-size: 12px;
}}
QSlider::groove:horizontal {{ height: 5px; background: {EDGE}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {INFO}; width: 15px; margin: -6px 0; border-radius: 7px;
}}
QSlider::sub-page:horizontal {{ background: {INFO}; border-radius: 2px; }}
"""
