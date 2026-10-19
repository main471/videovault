"""Thème inspiré de Yaru (Ubuntu) pour l'application."""

# Palette Yaru.
YARU_ORANGE = "#E95420"
YARU_ORANGE_DARK = "#C7431A"
YARU_PURPLE = "#772953"
BG = "#FAFAFA"
CARD = "#FFFFFF"
BORDER = "#DCDCDC"
TEXT = "#1A1A1A"
TEXT_MUTED = "#5E5E5E"
LOG_BG = "#2D2D2D"
LOG_TEXT = "#E0E0E0"

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: "Ubuntu", "Noto Sans", "Cantarell", sans-serif;
    font-size: 14px;
}}
QLabel#Title {{
    font-size: 22px;
    font-weight: 700;
}}
QLabel#Subtitle {{
    color: {TEXT_MUTED};
    font-size: 13px;
}}
QLabel#StepLabel {{
    font-weight: 600;
    font-size: 13px;
}}
QFrame#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLineEdit {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 9px;
}}
QLineEdit:focus {{
    border: 1px solid {YARU_ORANGE};
}}
QPushButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    border: 1px solid {YARU_ORANGE};
}}
QPushButton#Primary {{
    background: {YARU_ORANGE};
    color: white;
    border: none;
    font-weight: 600;
    padding: 10px 18px;
}}
QPushButton#Primary:hover {{
    background: {YARU_ORANGE_DARK};
}}
QPushButton#Primary:disabled {{
    background: #E8B9A8;
    color: #FFF3EE;
}}
QCheckBox {{
    spacing: 8px;
}}
QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background: {CARD};
    height: 18px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {YARU_ORANGE};
    border-radius: 5px;
}}
QPlainTextEdit#Log {{
    background: {LOG_BG};
    color: {LOG_TEXT};
    border: none;
    border-radius: 8px;
    font-family: "Ubuntu Mono", "DejaVu Sans Mono", monospace;
    font-size: 12px;
    padding: 8px;
}}
QStatusBar {{
    color: {TEXT_MUTED};
}}
"""
