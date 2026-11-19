"""Design tokens, Qt stylesheet and Windows Fluent icon glyphs."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap

PALETTES = {
    "light": dict(
        bg="#F4F5F8", surface="#FFFFFF", surface2="#F8F9FB", border="#E4E7EC", border2="#D0D5DD",
        text="#101828", muted="#667085", faint="#98A2B3",
        primary="#714B67", primary_hover="#5F3E57", primary_soft="#F4EDF2", on_primary="#FFFFFF",
        success="#12B76A", success_soft="#ECFDF3", danger="#F04438", danger_soft="#FEF3F2",
        warning="#F79009", warning_soft="#FFFAEB", info="#2E90FA", info_soft="#EFF8FF",
        log_bg="#0F1117", log_text="#D0D5DD", selection="#EDE3EB",
    ),
    "dark": dict(
        bg="#0B0D12", surface="#14171F", surface2="#1A1E28", border="#252A36", border2="#323847",
        text="#F2F4F7", muted="#98A2B3", faint="#667085",
        primary="#B47FA6", primary_hover="#C795BA", primary_soft="#2A2030", on_primary="#0B0D12",
        success="#32D583", success_soft="#0E2A1C", danger="#F97066", danger_soft="#2D1414",
        warning="#FDB022", warning_soft="#2B2210", info="#53B1FD", info_soft="#0F2234",
        log_bg="#07080C", log_text="#D0D5DD", selection="#2A2030",
    ),
}

# Segoe Fluent Icons / Segoe MDL2 Assets code points
GLYPHS = {
    "play": "", "stop": "", "restart": "", "globe": "", "add": "",
    "settings": "", "delete": "", "edit": "", "folder": "", "save": "",
    "db": "", "download": "", "upload": "", "search": "", "server": "",
    "more": "", "copy": "", "info": "", "log": "", "code": "",
    "moon": "", "sun": "", "lang": "", "shield": "", "check": "",
    "link": "", "refresh": "", "open": "", "playall": "", "stopall": "",
    "clear": "", "plug": "", "port": "", "clock": "", "memory": "",
    "chip": "", "tag": "", "pulse": "", "import": "", "detect": "",
}

_icon_font: str | None = None
_cache: dict = {}


def icon_font() -> str:
    global _icon_font
    if _icon_font is None:
        fams = set(QFontDatabase.families())
        _icon_font = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in fams), "")
    return _icon_font


def icon(name: str, color: str, size: int = 32) -> QIcon:
    key = (name, color, size)
    if key in _cache:
        return _cache[key]
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    fam = icon_font()
    if fam:
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        f = QFont(fam)
        f.setPixelSize(int(size * 0.62))
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(pm.rect(), Qt.AlignCenter, GLYPHS.get(name, "?"))
        p.end()
    ic = QIcon(pm)
    _cache[key] = ic
    return ic


def app_icon(color: str = "#714B67") -> QIcon:
    pm = QPixmap(256, 256)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(8, 8, 240, 240, 56, 56)
    pen = p.pen()
    from PySide6.QtGui import QPen
    p.setPen(QPen(QColor("white"), 30))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(64, 64, 128, 128)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#7EE2B8"))
    p.drawEllipse(170, 170, 50, 50)
    p.end()
    return QIcon(pm)


def stylesheet(t: dict, rtl: bool) -> str:
    font = "'Segoe UI', 'Segoe UI Variable Text', Tahoma"
    return f"""
* {{ font-family: {font}; font-size: 10pt; color: {t['text']}; outline: none; }}
QMainWindow, QDialog {{ background: {t['bg']}; }}
QWidget#Root {{ background: {t['bg']}; }}
QToolTip {{ background: {t['text']}; color: {t['surface']}; border: none; padding: 6px 8px; border-radius: 6px; }}

/* ---------- header ---------- */
QFrame#Header {{ background: {t['surface']}; border-bottom: 1px solid {t['border']}; }}
QLabel#AppTitle {{ font-size: 14pt; font-weight: 700; }}
QLabel#AppSub {{ color: {t['muted']}; font-size: 9pt; }}
QLabel#AdminBadge {{ background: {t['warning_soft']}; color: {t['warning']}; border-radius: 10px;
                     padding: 3px 10px; font-size: 8.5pt; font-weight: 600; }}

/* ---------- sidebar ---------- */
QFrame#Sidebar {{ background: {t['surface']}; border-{'left' if rtl else 'right'}: 1px solid {t['border']}; }}
QLabel#SectionTitle {{ font-size: 8.5pt; font-weight: 700; color: {t['muted']}; letter-spacing: 1px; }}
QLabel#CountBadge {{ background: {t['surface2']}; border: 1px solid {t['border']}; color: {t['muted']};
                     border-radius: 9px; padding: 1px 8px; font-size: 8.5pt; }}
QListWidget#ServerList {{ background: transparent; border: none; }}
QListWidget#ServerList::item {{ border: 1px solid transparent; border-radius: 10px; margin: 2px 0; }}
QListWidget#ServerList::item:hover {{ background: {t['surface2']}; border-color: {t['border']}; }}
QListWidget#ServerList::item:selected {{ background: {t['primary_soft']}; border-color: {t['primary']}; }}
QLabel#CardName {{ font-weight: 600; font-size: 10.5pt; background: transparent; }}
QLabel#CardSub {{ color: {t['muted']}; font-size: 8.5pt; background: transparent; }}
QLabel#Empty {{ color: {t['muted']}; font-size: 10pt; }}

/* ---------- cards ---------- */
QFrame#Card, QFrame#StatCard {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 12px; }}
QLabel#StatValue {{ font-size: 20pt; font-weight: 700; background: transparent; }}
QLabel#StatLabel {{ color: {t['muted']}; font-size: 9pt; background: transparent; }}
QLabel#TileLabel {{ color: {t['muted']}; font-size: 8.5pt; background: transparent; }}
QLabel#TileValue {{ font-size: 12pt; font-weight: 600; background: transparent; }}
QLabel#DetailTitle {{ font-size: 17pt; font-weight: 700; }}
QLabel#Chip {{ background: {t['surface2']}; border: 1px solid {t['border']}; border-radius: 10px;
               padding: 2px 10px; color: {t['muted']}; font-size: 8.5pt; }}
QLabel#Link {{ color: {t['primary']}; }}
QLabel#Mono, QLineEdit#Mono {{ font-family: 'Cascadia Mono', Consolas, monospace; font-size: 9pt; color: {t['muted']}; }}
QLabel#Muted {{ color: {t['muted']}; }}
QLabel#Hint {{ color: {t['muted']}; font-size: 9pt; }}

/* ---------- buttons ---------- */
QPushButton, QToolButton {{ background: {t['surface']}; border: 1px solid {t['border2']}; border-radius: 8px;
    padding: 7px 14px; font-weight: 600; }}
QPushButton:hover, QToolButton:hover {{ background: {t['surface2']}; border-color: {t['faint']}; }}
QPushButton:pressed {{ background: {t['border']}; }}
QPushButton:disabled {{ color: {t['faint']}; background: {t['surface2']}; border-color: {t['border']}; }}
QPushButton[variant="primary"] {{ background: {t['primary']}; color: {t['on_primary']}; border: 1px solid {t['primary']}; }}
QPushButton[variant="primary"]:hover {{ background: {t['primary_hover']}; border-color: {t['primary_hover']}; }}
QPushButton[variant="success"] {{ background: {t['success']}; color: white; border: 1px solid {t['success']}; }}
QPushButton[variant="success"]:hover {{ background: {t['success']}; border-color: {t['text']}; }}
QPushButton[variant="danger"] {{ background: {t['surface']}; color: {t['danger']}; border: 1px solid {t['danger']}; }}
QPushButton[variant="danger"]:hover {{ background: {t['danger_soft']}; }}
QPushButton[variant="ghost"], QToolButton[variant="ghost"] {{ background: transparent; border: 1px solid transparent; padding: 6px 10px; }}
QPushButton[variant="ghost"]:hover, QToolButton[variant="ghost"]:hover {{ background: {t['surface2']}; border-color: {t['border']}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QPushButton[variant]:disabled {{ background: {t['surface2']}; color: {t['faint']}; border: 1px solid {t['border']}; }}
QPushButton#HeaderBtn {{ background: transparent; border: 1px solid transparent; padding: 8px 12px; font-size: 10pt; }}
QPushButton#HeaderBtn:hover {{ background: {t['surface2']}; border-color: {t['border']}; }}

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QSpinBox {{ background: {t['surface']}; border: 1px solid {t['border2']}; border-radius: 8px;
    padding: 6px 10px; selection-background-color: {t['primary']}; selection-color: white; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {t['primary']}; }}
QLineEdit#Search {{ background: {t['surface2']}; border-color: {t['border']}; padding-{'right' if rtl else 'left'}: 30px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {t['surface']}; border: 1px solid {t['border']}; selection-background-color: {t['primary_soft']}; selection-color: {t['text']}; padding: 4px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {t['border2']}; background: {t['surface']}; }}
QCheckBox::indicator:checked {{ background: {t['primary']}; border-color: {t['primary']}; }}
QPlainTextEdit {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; padding: 8px;
    selection-background-color: {t['primary']}; selection-color: white; }}
QPlainTextEdit#Code {{ font-family: 'Cascadia Mono', Consolas, monospace; font-size: 10pt; }}
QPlainTextEdit#LogView {{ background: {t['log_bg']}; color: {t['log_text']}; border: 1px solid {t['border']};
    font-family: 'Cascadia Mono', Consolas, monospace; font-size: 9pt; }}
QGroupBox {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 12px; margin-top: 14px; padding: 16px 12px 12px 12px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top {'right' if rtl else 'left'}; padding: 0 8px; margin: 0 10px; color: {t['muted']}; }}

/* ---------- tabs ---------- */
QTabWidget::pane {{ border: none; background: transparent; top: -1px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; border: none; border-bottom: 2px solid transparent; padding: 10px 16px;
    margin-{'left' if rtl else 'right'}: 4px; color: {t['muted']}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {t['text']}; }}
QTabBar::tab:selected {{ color: {t['primary']}; border-bottom: 2px solid {t['primary']}; }}
QFrame#TabLine {{ background: {t['border']}; max-height: 1px; min-height: 1px; }}

/* ---------- tables ---------- */
QTableWidget {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; gridline-color: transparent;
    selection-background-color: {t['primary_soft']}; selection-color: {t['text']}; alternate-background-color: {t['surface2']}; }}
QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {t['border']}; }}
QHeaderView::section {{ background: {t['surface2']}; color: {t['muted']}; border: none; border-bottom: 1px solid {t['border']};
    padding: 8px; font-weight: 700; font-size: 8.5pt; }}

/* ---------- menus / scrollbars ---------- */
QMenu {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 8px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {t['primary_soft']}; color: {t['text']}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 4px 8px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['border2']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t['faint']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['border2']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: none; width: 0; height: 0; }}
QStatusBar {{ background: {t['surface']}; border-top: 1px solid {t['border']}; color: {t['muted']}; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: transparent; }}
QScrollArea#Scroll, QWidget#ScrollBody {{ background: transparent; }}
QMessageBox QLabel {{ min-width: 280px; }}
"""
