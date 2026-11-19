"""Main window: header, server sidebar, detail panel (overview / logs / config / databases), tray."""
from __future__ import annotations

import os
import re
import subprocess
import time
import webbrowser

import psutil
from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
                               QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
                               QPushButton, QStackedWidget, QSystemTrayIcon, QTableWidget,
                               QTableWidgetItem, QTabWidget, QToolButton, QVBoxLayout, QWidget)

from . import db, i18n, updater
from .core import (APP_AUTHOR, APP_VERSION, add_custom_dir, write_conf_text, custom_addons_dir, install_module,
                   suggest_custom_dir, update_module)
from .core import (Instance, Registry, conf_value, resolve_pg_bin, discover_services, is_admin, load_settings,
                   port_owner, save_settings, set_start_with_windows)
from .i18n import tr
from .theme import PALETTES, app_icon, icon, stylesheet
from .wizard import InstanceDialog, NewServerWizard, fit_to_screen, path_row

STATUS_TONE = {"running": "success", "stopped": "danger", "starting": "warning",
               "stopping": "warning", "missing": "faint"}


# ============================================================================ helpers
def btn(text="", ic=None, variant=None, tip="", t=None, color=None) -> QPushButton:
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    if ic and t:
        c = color or {"primary": t["on_primary"], "success": "#FFFFFF", "danger": t["danger"]}.get(variant, t["text"])
        b.setIcon(icon(ic, c))
        b.setIconSize(QSize(16, 16))
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    return b


def fmt_uptime(sec: float) -> str:
    sec = int(sec)
    d, sec = divmod(sec, 86400)
    h, sec = divmod(sec, 3600)
    m, s = divmod(sec, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m {s}s"


def fmt_mem(b: int) -> str:
    return f"{b / 1024 / 1024:.0f} MB" if b < 1024 ** 3 else f"{b / 1024 ** 3:.2f} GB"


class Task(QThread):
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(self, fn, ok_msg=""):
        super().__init__()
        self.fn, self.ok_msg = fn, ok_msg

    def run(self):
        try:
            r = self.fn(self.log.emit)
            self.done.emit(True, self.ok_msg or (r if isinstance(r, str) else ""))
        except Exception as e:
            self.done.emit(False, str(e))


class UpdateCheck(QThread):
    found = Signal(dict)
    failed = Signal(str)

    def run(self):
        try:
            m = updater.check()
            self.found.emit(m or {})
        except Exception as e:
            self.failed.emit(str(e))


class UpdateDownload(QThread):
    progress = Signal(int)
    done = Signal(bool, str)

    def __init__(self, manifest):
        super().__init__()
        self.m, self.stop = manifest, False

    def run(self):
        try:
            path = updater.download(self.m, self.progress.emit, lambda: self.stop)
            self.done.emit(True, path)
        except Exception as e:
            self.done.emit(False, str(e))


class StatusPoller(QThread):
    result = Signal(dict)

    def __init__(self, instances):
        super().__init__()
        self.instances = instances

    def run(self):
        res = {}
        for i in list(self.instances):
            info = {"status": "missing", "pid": None, "port": 0, "uptime": None, "mem": None}
            try:
                info["status"] = i.status()
                info["port"] = i.port
                pid = i.pid if i.kind == "bin" else None
                if i.kind == "service" and info["status"] == "running":
                    try:
                        pid = psutil.win_service_get(i.service_name).pid()
                    except Exception:
                        pass
                info["pid"] = pid
                if pid and info["status"] == "running":
                    p = psutil.Process(pid)
                    info["uptime"] = time.time() - p.create_time()
                    mem = p.memory_info().rss
                    for c in p.children(recursive=True):
                        try:
                            mem += c.memory_info().rss
                        except psutil.Error:
                            pass
                    info["mem"] = mem
            except Exception:
                pass
            res[i.id] = info
        self.result.emit(res)


# ============================================================================ widgets
class Pill(QLabel):
    def __init__(self, t):
        super().__init__()
        self.t = t
        self.setAlignment(Qt.AlignCenter)

    def set_status(self, st: str):
        tone = STATUS_TONE.get(st, "faint")
        fg = self.t.get(tone, self.t["muted"])
        bg = self.t.get(f"{tone}_soft", self.t["surface2"])
        self.setText(f"●  {tr('s_' + st) if st in STATUS_TONE else tr('s_unknown')}")
        self.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:11px; padding:3px 12px;"
                           f"font-size:8.5pt; font-weight:700;")


class ServerCard(QWidget):
    def __init__(self, inst: Instance, t: dict):
        super().__init__()
        self.t = t
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 10, 12, 10)
        h.setSpacing(10)
        self.ic = QLabel()
        self.ic.setFixedSize(36, 36)
        self.ic.setAlignment(Qt.AlignCenter)
        h.addWidget(self.ic)
        v = QVBoxLayout()
        v.setSpacing(1)
        self.name = QLabel(inst.name)
        self.name.setObjectName("CardName")
        self.sub = QLabel()
        self.sub.setObjectName("CardSub")
        v.addWidget(self.name)
        v.addWidget(self.sub)
        h.addLayout(v, 1)
        self.pill = Pill(t)
        h.addWidget(self.pill)
        self.update_data(inst, {"status": "?", "port": inst.port})

    def update_data(self, inst: Instance, info: dict):
        st = info.get("status", "?")
        tone = STATUS_TONE.get(st, "faint")
        self.name.setText(inst.name)
        kind = tr("kind_service") if inst.kind == "service" else tr("kind_bin")
        self.sub.setText(f"{kind}  ·  :{info.get('port') or inst.port}")
        self.pill.set_status(st)
        c = self.t.get(tone, self.t["muted"])
        self.ic.setPixmap(icon("server", c, 40).pixmap(22, 22))
        self.ic.setStyleSheet(f"background:{self.t.get(tone + '_soft', self.t['surface2'])}; border-radius:10px;")


class StatCard(QFrame):
    def __init__(self, ic: str, label: str, tone: str, t: dict):
        super().__init__()
        self.setObjectName("StatCard")
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 14, 16, 14)
        h.setSpacing(14)
        il = QLabel()
        il.setFixedSize(42, 42)
        il.setAlignment(Qt.AlignCenter)
        il.setPixmap(icon(ic, t[tone], 44).pixmap(22, 22))
        il.setStyleSheet(f"background:{t[tone + '_soft'] if tone + '_soft' in t else t['surface2']}; border-radius:12px;")
        h.addWidget(il)
        v = QVBoxLayout()
        v.setSpacing(0)
        self.value = QLabel("0")
        self.value.setObjectName("StatValue")
        lb = QLabel(label)
        lb.setObjectName("StatLabel")
        v.addWidget(self.value)
        v.addWidget(lb)
        h.addLayout(v, 1)


class Tile(QFrame):
    def __init__(self, ic: str, label: str, t: dict):
        super().__init__()
        self.setObjectName("Card")
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(4)
        top = QHBoxLayout()
        il = QLabel()
        il.setPixmap(icon(ic, t["muted"], 32).pixmap(14, 14))
        lb = QLabel(label)
        lb.setObjectName("TileLabel")
        top.addWidget(il)
        top.addWidget(lb, 1)
        v.addLayout(top)
        self.value = QLabel("—")
        self.value.setObjectName("TileValue")
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.value)


# ============================================================================ settings dialog
class SettingsDialog(QDialog):
    def __init__(self, parent, s: dict):
        super().__init__(parent)
        self.setWindowTitle(tr("settings"))
        self.setMinimumWidth(420)
        fit_to_screen(self, 640, 640)
        self.s = s
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)
        title = QLabel(tr("settings"))
        title.setObjectName("DetailTitle")
        v.addWidget(title)

        from PySide6.QtWidgets import QGroupBox, QSpinBox
        g1 = QGroupBox(tr("general"))
        f = QFormLayout(g1)
        f.setSpacing(10)
        self.pg = QLineEdit(s["pg_bin"])
        self.bk = QLineEdit(s["backup_dir"])
        self.tray = QCheckBox(tr("min_tray"))
        self.tray.setChecked(s["minimize_to_tray"])
        self.win = QCheckBox(tr("with_windows"))
        self.win.setChecked(s["start_with_windows"])
        f.addRow(tr("pg_bin"), path_row(self.pg, "dir"))
        f.addRow(tr("backup_dir"), path_row(self.bk, "dir"))
        f.addRow("", self.tray)
        f.addRow("", self.win)
        v.addWidget(g1)

        g3 = QGroupBox(tr("automation"))
        f3 = QFormLayout(g3)
        self.ab = QCheckBox(tr("auto_backup"))
        self.ab.setChecked(s.get("auto_backup", False))
        self.keep = QSpinBox()
        self.keep.setRange(1, 90)
        self.keep.setValue(int(s.get("auto_backup_keep", 7)))
        self.notify = QCheckBox(tr("notify_stop"))
        self.notify.setChecked(s.get("notify_stop", True))
        f3.addRow("", self.ab)
        f3.addRow(tr("keep_copies"), self.keep)
        f3.addRow("", self.notify)
        v.addWidget(g3)

        g2 = QGroupBox(tr("appearance"))
        f2 = QFormLayout(g2)
        self.lang = QComboBox()
        self.lang.addItem("العربية", "ar")
        self.lang.addItem("English", "en")
        self.lang.setCurrentIndex(0 if s.get("language", "ar") == "ar" else 1)
        self.theme = QComboBox()
        self.theme.addItem(tr("theme_light"), "light")
        self.theme.addItem(tr("theme_dark"), "dark")
        self.theme.setCurrentIndex(0 if s.get("theme", "light") == "light" else 1)
        f2.addRow(tr("language"), self.lang)
        f2.addRow(tr("theme"), self.theme)
        v.addWidget(g2)

        h = QHBoxLayout()
        h.addStretch()
        c = QPushButton(tr("cancel"))
        c.clicked.connect(self.reject)
        ok = QPushButton(tr("save"))
        ok.setProperty("variant", "primary")
        ok.clicked.connect(self.accept)
        h.addWidget(c)
        h.addWidget(ok)
        v.addLayout(h)

    def values(self) -> dict:
        return dict(self.s, pg_bin=self.pg.text().strip(), backup_dir=self.bk.text().strip(),
                    minimize_to_tray=self.tray.isChecked(), start_with_windows=self.win.isChecked(),
                    language=self.lang.currentData(), theme=self.theme.currentData(),
                    auto_backup=self.ab.isChecked(), auto_backup_keep=self.keep.value(),
                    notify_stop=self.notify.isChecked())


class WelcomeDialog(QDialog):
    PAGES = [("welcome_1_t", "welcome_1_b", "server"),
             ("welcome_2_t", "welcome_2_b", "add"),
             ("welcome_3_t", "welcome_3_b", "pulse")]

    def __init__(self, parent, t):
        super().__init__(parent)
        self.setWindowTitle(tr("welcome"))
        self.setMinimumSize(460, 420)
        fit_to_screen(self, 620, 520)
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 26, 28, 20)
        v.setSpacing(14)
        self.stack = QStackedWidget()
        for tk, bk, ic in self.PAGES:
            pg = QWidget()
            pv = QVBoxLayout(pg)
            pv.setSpacing(12)
            il = QLabel()
            il.setFixedSize(64, 64)
            il.setAlignment(Qt.AlignCenter)
            il.setPixmap(icon(ic, t["primary"], 64).pixmap(32, 32))
            il.setStyleSheet(f"background:{t['primary_soft']}; border-radius:18px;")
            pv.addWidget(il, 0, Qt.AlignHCenter)
            tl = QLabel(tr(tk))
            tl.setObjectName("DetailTitle")
            tl.setAlignment(Qt.AlignCenter)
            tl.setWordWrap(True)
            pv.addWidget(tl)
            bl = QLabel(tr(bk))
            bl.setWordWrap(True)
            bl.setTextFormat(Qt.RichText)
            bl.setStyleSheet("font-size:14px; line-height:150%;")
            pv.addWidget(bl, 1, Qt.AlignTop)
            self.stack.addWidget(pg)
        v.addWidget(self.stack, 1)
        self.dots = QLabel()
        self.dots.setAlignment(Qt.AlignCenter)
        v.addWidget(self.dots)
        h = QHBoxLayout()
        self.skip = QPushButton(tr("skip"))
        self.skip.setProperty("variant", "ghost")
        self.skip.clicked.connect(self.accept)
        self.back = QPushButton(tr("back"))
        self.back.clicked.connect(lambda: self.go(-1))
        self.next = QPushButton(tr("next"))
        self.next.setProperty("variant", "primary")
        self.next.clicked.connect(lambda: self.go(1))
        h.addWidget(self.skip)
        h.addStretch()
        h.addWidget(self.back)
        h.addWidget(self.next)
        v.addLayout(h)
        self.t = t
        self.go(0)

    def go(self, d):
        i = self.stack.currentIndex() + d
        if i >= self.stack.count():
            return self.accept()
        self.stack.setCurrentIndex(max(0, i))
        i = self.stack.currentIndex()
        self.back.setEnabled(i > 0)
        last = i == self.stack.count() - 1
        self.next.setText(tr("start_using") if last else tr("next"))
        self.skip.setVisible(not last)
        self.dots.setText("  ".join(
            f'<span style="color:{self.t["primary"] if n == i else self.t["faint"]}; font-size:18px">●</span>'
            for n in range(self.stack.count())))


class AboutDialog(QDialog):
    def __init__(self, parent, t):
        super().__init__(parent)
        self.setWindowTitle(tr("about"))
        self.setFixedWidth(420)
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 28, 28, 22)
        v.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(app_icon(t["primary"]).pixmap(72, 72))
        logo.setAlignment(Qt.AlignCenter)
        v.addWidget(logo)
        for txt, name in ((tr("app_title"), "DetailTitle"), (tr("version_lbl", v=APP_VERSION), "Muted"),
                          (tr("app_sub"), None)):
            lb = QLabel(txt)
            lb.setAlignment(Qt.AlignCenter)
            if name:
                lb.setObjectName(name)
            v.addWidget(lb)
        v.addSpacing(10)
        by = QLabel(f"Powered by <b>{APP_AUTHOR}</b>")
        by.setAlignment(Qt.AlignCenter)
        v.addWidget(by)
        feats = QLabel(tr("about_feats"))
        feats.setObjectName("Muted")
        feats.setWordWrap(True)
        feats.setAlignment(Qt.AlignCenter)
        v.addWidget(feats)
        v.addSpacing(10)
        upd = QPushButton(tr("check_updates"))
        upd.clicked.connect(lambda: (self.accept(), parent.check_updates(manual=True)))
        upd.setVisible(updater.enabled())
        v.addWidget(upd)
        guide = QPushButton(tr("welcome_again"))
        guide.clicked.connect(lambda: WelcomeDialog(self, t).exec())
        v.addWidget(guide)
        ok = QPushButton(tr("close"))
        ok.setProperty("variant", "primary")
        ok.clicked.connect(self.accept)
        v.addWidget(ok)


def _dbfilter_match(inst: Instance, name: str):
    """True/False if the instance has a usable dbfilter, else None."""
    f = conf_value(inst.conf, "dbfilter")
    if not f or "%" in f:
        return None
    try:
        return re.match(f, name) is not None
    except re.error:
        return None


class RemoveDialog(QDialog):
    def __init__(self, parent, inst: Instance, all_instances):
        super().__init__(parent)
        self.setWindowTitle(tr("rm_title", n=inst.name))
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("rm_info")))
        lay.addWidget(QLabel("<b>" + tr("rm_dbs") + "</b>"))
        self.db_boxes = []
        others = [o for o in all_instances if o.id != inst.id]
        try:
            names = [n for n, _ in db.list_databases(inst)]
            mine = []
            for n in names:
                own = _dbfilter_match(inst, n)
                if own is False:
                    continue
                if own is None and any(_dbfilter_match(o, n) for o in others):
                    continue  # another server explicitly owns it
                mine.append(n)
            for n in mine:
                cb = QCheckBox(n)
                self.db_boxes.append(cb)
                lay.addWidget(cb)
            if not mine:
                lay.addWidget(QLabel(tr("rm_no_dbs")))
        except Exception as e:
            lay.addWidget(QLabel(tr("rm_db_err", e=e)))
        self.folder = None
        self.folder_box = None
        if inst.kind == "bin" and inst.conf_path:
            f = os.path.normpath(os.path.dirname(inst.conf_path))
            inside = lambda p: p and os.path.normcase(os.path.abspath(p)).startswith(os.path.normcase(f) + os.sep)
            safe = (len(f) > 3 and "program files" not in f.lower()
                    and not any(inside(o.conf_path) or inside(o.odoo_bin) for o in others))
            if safe and os.path.isdir(f):
                self.folder = f
                self.folder_box = QCheckBox(tr("rm_folder", p=f))
                lay.addSpacing(8)
                lay.addWidget(self.folder_box)
        lay.addSpacing(8)
        warn = QLabel(tr("rm_warn"))
        warn.setWordWrap(True)
        lay.addWidget(warn)
        row = QHBoxLayout()
        row.addStretch()
        ok = QPushButton(tr("remove"))
        ok.setProperty("variant", "danger")
        cancel = QPushButton(tr("cancel"))
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

    def choice(self):
        dbs = [cb.text() for cb in self.db_boxes if cb.isChecked()]
        folder = self.folder if self.folder_box and self.folder_box.isChecked() else None
        return dbs, folder


# ============================================================================ main window
class MainWindow(QMainWindow):
    relaunch = Signal()

    def __init__(self, start_in_tray=False):
        super().__init__()
        self.settings = load_settings()
        i18n.set_lang(self.settings.get("language", "ar"))
        self.t = PALETTES.get(self.settings.get("theme", "light"), PALETTES["light"])
        app = QApplication.instance()
        app.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        app.setStyleSheet(stylesheet(self.t, i18n.is_rtl()))

        self.reg = Registry()
        self.tasks: list[QThread] = []
        self.statuses: dict[str, dict] = {}
        self.cards: dict[str, ServerCard] = {}
        self.poller: StatusPoller | None = None
        self.tail_path, self.tail_pos = None, 0
        self._quitting = False
        self.expected_stop: set[str] = set()

        self.setWindowTitle(tr("app_title"))
        self.setWindowIcon(app_icon())
        self.setMinimumSize(760, 500)
        fit_to_screen(self, 1320, 820)
        self._build_ui()
        self._build_tray()

        known = {i.service_name for i in self.reg.instances if i.kind == "service"}
        for inst in discover_services():
            if inst.service_name not in known:
                self.reg.add(inst)

        self.refresh_list()
        self.poll_timer = QTimer(self, interval=2500, timeout=self.poll)
        self.poll_timer.start()
        self.tail_timer = QTimer(self, interval=1000, timeout=self.tail_log)
        self.tail_timer.start()
        self.poll()
        QTimer.singleShot(1500, self.autostart_instances)
        self._upd_thread = None
        self._upd_dl = None
        self.update_timer = QTimer(self, interval=12 * 3600 * 1000, timeout=self.check_updates)
        self.update_timer.start()
        QTimer.singleShot(20 * 1000, self.check_updates)
        self.backup_timer = QTimer(self, interval=30 * 60 * 1000, timeout=self.auto_backup)
        self.backup_timer.start()
        QTimer.singleShot(90 * 1000, self.auto_backup)
        if not start_in_tray:
            self.show()
            if not self.settings.get("welcome_done"):
                QTimer.singleShot(600, self.show_welcome)

    # ------------------------------------------------------------------ build
    def _build_ui(self):
        t = self.t
        root = QWidget()
        root.setObjectName("Root")
        rv = QVBoxLayout(root)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        rv.addWidget(self._header())
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        from PySide6.QtWidgets import QSplitter
        sp = QSplitter(Qt.Horizontal)
        sp.setChildrenCollapsible(False)
        sp.setHandleWidth(4)
        sp.addWidget(self._sidebar())
        sp.addWidget(self._content())
        sp.setStretchFactor(1, 1)
        sp.setSizes([320, 1000])
        body.addWidget(sp, 1)
        rv.addLayout(body, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage(tr("ready"))
        credit = QLabel("Powered by <b>Hossam Ramadan</b>")
        credit.setStyleSheet("color:%s; padding:0 12px;" % t["muted"])
        self.statusBar().addPermanentWidget(credit)

    def _header(self):
        t = self.t
        hd = QFrame()
        hd.setObjectName("Header")
        hd.setFixedHeight(68)
        h = QHBoxLayout(hd)
        h.setContentsMargins(20, 0, 16, 0)
        h.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(app_icon(t["primary"]).pixmap(38, 38))
        h.addWidget(logo)
        tv = QVBoxLayout()
        tv.setSpacing(0)
        a = QLabel(tr("app_title"))
        a.setObjectName("AppTitle")
        b = QLabel(tr("app_sub"))
        b.setObjectName("AppSub")
        tv.addStretch()
        tv.addWidget(a)
        tv.addWidget(b)
        tv.addStretch()
        h.addLayout(tv)
        h.addStretch()
        if is_admin():
            ad = QLabel(tr("admin"))
            ad.setObjectName("AdminBadge")
            h.addWidget(ad)
        lang = btn(tr("lang_btn"), "lang", "ghost", t=t)
        lang.clicked.connect(self.toggle_lang)
        dark = self.settings.get("theme") == "dark"
        th = btn("", "sun" if dark else "moon", "ghost", tr("theme_light") if dark else tr("theme_dark"), t=t)
        th.clicked.connect(self.toggle_theme)
        st = btn("", "settings", "ghost", tr("settings"), t=t)
        st.clicked.connect(self.open_settings)
        ab = btn("", "info", "ghost", tr("about"), t=t)
        ab.clicked.connect(lambda: AboutDialog(self, self.t).exec())
        for w in (lang, th, st, ab):
            w.setObjectName("HeaderBtn")
            w.setIconSize(QSize(20, 20))
            h.addWidget(w)
        return hd

    def _sidebar(self):
        t = self.t
        sb = QFrame()
        sb.setObjectName("Sidebar")
        sb.setMinimumWidth(230)
        sb.setMaximumWidth(460)
        v = QVBoxLayout(sb)
        v.setContentsMargins(16, 18, 16, 16)
        v.setSpacing(12)
        top = QHBoxLayout()
        lb = QLabel(tr("servers").upper())
        lb.setObjectName("SectionTitle")
        self.count_lbl = QLabel("0")
        self.count_lbl.setObjectName("CountBadge")
        top.addWidget(lb)
        top.addWidget(self.count_lbl)
        top.addStretch()
        more = QToolButton()
        more.setProperty("variant", "ghost")
        more.setIcon(icon("more", t["text"]))
        more.setToolTip(tr("more"))
        more.setPopupMode(QToolButton.InstantPopup)
        m = QMenu(more)
        m.addAction(icon("import", t["text"]), tr("add_existing"), self.add_existing)
        m.addAction(icon("detect", t["text"]), tr("detect_services"), self.detect_services)
        m.addSeparator()
        m.addAction(icon("play", t["success"]), tr("start_all"), lambda: self.control_all("start"))
        m.addAction(icon("stop", t["danger"]), tr("stop_all"), lambda: self.control_all("stop"))
        more.setMenu(m)
        top.addWidget(more)
        v.addLayout(top)

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText(tr("search"))
        self.search.addAction(icon("search", t["faint"]), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self.filter_list)
        v.addWidget(self.search)

        self.list = QListWidget()
        self.list.setObjectName("ServerList")
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.currentItemChanged.connect(lambda *_: self.on_select())
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.list_menu)
        self.list.itemDoubleClicked.connect(lambda *_: self.open_browser())
        v.addWidget(self.list, 1)

        self.empty_lbl = QLabel(tr("no_servers"))
        self.empty_lbl.setObjectName("Empty")
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.empty_lbl.setWordWrap(True)
        v.addWidget(self.empty_lbl, 1)

        nb = btn(tr("new_server"), "add", "primary", t=t)
        nb.setMinimumHeight(42)
        nb.clicked.connect(self.new_server)
        v.addWidget(nb)
        return sb

    def _content(self):
        t = self.t
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 20, 24, 12)
        v.setSpacing(18)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.stat_total = StatCard("server", tr("st_total"), "info", t)
        self.stat_run = StatCard("pulse", tr("st_running"), "success", t)
        self.stat_stop = StatCard("stop", tr("st_stopped"), "danger", t)
        for s in (self.stat_total, self.stat_run, self.stat_stop):
            stats.addWidget(s)
        v.addLayout(stats)

        self.stack = QStackedWidget()
        empty = QLabel(tr("select_server"))
        empty.setObjectName("Empty")
        empty.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(empty)
        self.stack.addWidget(self._detail())
        v.addWidget(self.stack, 1)
        return w

    def _detail(self):
        t = self.t
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        tv = QVBoxLayout()
        tv.setSpacing(6)
        r1 = QHBoxLayout()
        r1.setSpacing(10)
        self.d_title = QLabel()
        self.d_title.setObjectName("DetailTitle")
        self.d_pill = Pill(t)
        self.d_kind = QLabel()
        self.d_kind.setObjectName("Chip")
        r1.addWidget(self.d_title)
        r1.addWidget(self.d_pill)
        r1.addWidget(self.d_kind)
        r1.addStretch()
        tv.addLayout(r1)
        self.d_url = QLabel()
        self.d_url.setObjectName("Link")
        self.d_url.setOpenExternalLinks(True)
        self.d_url.setTextFormat(Qt.RichText)
        tv.addWidget(self.d_url)
        top.addLayout(tv, 1)

        self.b_start = btn(tr("start"), "play", "success", t=t)
        self.b_stop = btn(tr("stop"), "stop", "danger", t=t)
        self.b_restart = btn(tr("restart"), "restart", t=t)
        self.b_open = btn(tr("open_browser"), "globe", "primary", t=t)
        self.b_start.clicked.connect(lambda: self.control("start"))
        self.b_stop.clicked.connect(lambda: self.control("stop"))
        self.b_restart.clicked.connect(lambda: self.control("restart"))
        self.b_open.clicked.connect(self.open_browser)
        more = QToolButton()
        more.setIcon(icon("more", t["text"]))
        more.setPopupMode(QToolButton.InstantPopup)
        m = QMenu(more)
        m.addAction(icon("edit", t["text"]), tr("edit"), self.edit_instance)
        m.addAction(icon("folder", t["text"]), tr("open_folder"),
                    lambda: self.reveal(self.current() and self.current().conf_path))
        m.addSeparator()
        m.addAction(icon("add", t["text"]), tr("add_module"), self.add_module)
        m.addAction(icon("restart", t["text"]), tr("upd_module"), self.upgrade_module)
        m.addAction(icon("folder", t["text"]), tr("open_custom"), self.open_custom)
        m.addAction(icon("copy", t["text"]), tr("copy_master"), self.copy_master)
        m.addSeparator()
        m.addAction(icon("delete", t["danger"]), tr("remove"), self.remove_instance)
        more.setMenu(m)
        for b in (self.b_start, self.b_stop, self.b_restart, self.b_open, more):
            top.addWidget(b, 0, Qt.AlignTop)
        v.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._overview_tab(), icon("info", t["muted"]), tr("tab_overview"))
        self.tabs.addTab(self._log_tab(), icon("log", t["muted"]), tr("tab_logs"))
        self.tabs.addTab(self._conf_tab(), icon("code", t["muted"]), tr("tab_config"))
        self.tabs.addTab(self._db_tab(), icon("db", t["muted"]), tr("tab_db"))
        self.tabs.currentChanged.connect(self.on_tab)
        v.addWidget(self.tabs, 1)
        return w

    def _overview_tab(self):
        t = self.t
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 16, 0, 0)
        v.setSpacing(14)
        g = QGridLayout()
        g.setSpacing(12)
        self.tiles = {
            "status": Tile("pulse", tr("status"), t), "port": Tile("port", tr("port"), t),
            "pid": Tile("tag", tr("pid"), t), "uptime": Tile("clock", tr("uptime"), t),
            "memory": Tile("memory", tr("memory"), t), "type": Tile("server", tr("type"), t),
        }
        for n, k in enumerate(self.tiles):
            g.addWidget(self.tiles[k], n // 3, n % 3)
        v.addLayout(g)

        card = QFrame()
        card.setObjectName("Card")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(16, 14, 16, 14)
        cv.setSpacing(8)
        h = QLabel(tr("paths").upper())
        h.setObjectName("SectionTitle")
        cv.addWidget(h)
        self.path_grid = QGridLayout()
        self.path_grid.setHorizontalSpacing(12)
        self.path_grid.setVerticalSpacing(6)
        self.path_grid.setColumnStretch(1, 1)
        cv.addLayout(self.path_grid)
        v.addWidget(card)

        row = QHBoxLayout()
        self.auto_cb = QCheckBox()
        self.auto_cb.clicked.connect(self.toggle_autostart)
        row.addWidget(self.auto_cb, 1)
        cp = btn(tr("check_ports"), "port", t=t)
        cp.clicked.connect(self.check_ports)
        row.addWidget(cp)
        v.addLayout(row)
        v.addStretch()
        from PySide6.QtWidgets import QScrollArea
        sc = QScrollArea()
        sc.setObjectName("Scroll")
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        w.setObjectName("ScrollBody")
        sc.setWidget(w)
        return sc

    def _log_tab(self):
        t = self.t
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 14, 0, 0)
        h = QHBoxLayout()
        self.log_filter = QLineEdit()
        self.log_filter.setPlaceholderText(tr("filter"))
        self.log_filter.addAction(icon("search", t["faint"]), QLineEdit.LeadingPosition)
        self.log_filter.textChanged.connect(lambda: self.load_log(full=True))
        self.follow = QCheckBox(tr("follow"))
        self.follow.setChecked(True)
        b1 = btn(tr("clear"), "clear", "ghost", t=t)
        b1.clicked.connect(lambda: self.log_view.clear())
        b2 = btn(tr("open_log"), "open", "ghost", t=t)
        b2.clicked.connect(self.open_log_file)
        h.addWidget(self.log_filter, 1)
        for x in (self.follow, b1, b2):
            h.addWidget(x)
        v.addLayout(h)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_view.setLayoutDirection(Qt.LeftToRight)
        v.addWidget(self.log_view)
        return w

    def _conf_tab(self):
        t = self.t
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 14, 0, 0)
        h = QHBoxLayout()
        self.conf_label = QLabel()
        self.conf_label.setObjectName("Mono")
        b3 = btn(tr("open_folder"), "folder", "ghost", t=t)
        b3.clicked.connect(lambda: self.reveal(self.current() and self.current().conf_path))
        b2 = btn(tr("reload"), "refresh", t=t)
        b2.clicked.connect(self.load_conf)
        b1 = btn(tr("save"), "save", "primary", t=t)
        b1.clicked.connect(self.save_conf)
        h.addWidget(self.conf_label, 1)
        for b in (b3, b2, b1):
            h.addWidget(b)
        v.addLayout(h)
        self.conf_edit = QPlainTextEdit()
        self.conf_edit.setObjectName("Code")
        self.conf_edit.setLayoutDirection(Qt.LeftToRight)
        v.addWidget(self.conf_edit)
        n = QLabel("ⓘ  " + tr("conf_note"))
        n.setObjectName("Hint")
        v.addWidget(n)
        return w

    def _db_tab(self):
        t = self.t
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 14, 0, 0)
        h = QHBoxLayout()
        items = [("refresh", "refresh", None, self.load_dbs), ("open", "globe", None, self.open_db),
                 ("backup", "download", "primary", self.backup_db), ("restore", "upload", None, self.restore_db),
                 ("delete", "delete", "danger", self.drop_db)]
        for key, ic, var, fn in items:
            b = btn(tr(key), ic, var, t=t)
            b.clicked.connect(fn)
            h.addWidget(b)
        h.addStretch()
        bf = btn(tr("backups_folder"), "folder", "ghost", t=t)
        bf.clicked.connect(lambda: self.reveal(self.settings["backup_dir"], is_dir=True))
        h.addWidget(bf)
        v.addLayout(h)
        self.db_table = QTableWidget(0, 3)
        self.db_table.setHorizontalHeaderLabels([tr("db_name"), tr("db_size"), ""])
        self.db_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.db_table.setColumnWidth(2, 120)
        self.db_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.db_table.horizontalHeader().setDefaultAlignment(Qt.AlignVCenter | (Qt.AlignRight if i18n.is_rtl() else Qt.AlignLeft))
        self.db_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.db_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.db_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.db_table.setShowGrid(False)
        self.db_table.verticalHeader().hide()
        self.db_table.verticalHeader().setDefaultSectionSize(42)
        self.db_table.doubleClicked.connect(lambda *_: self.open_db())
        v.addWidget(self.db_table, 2)
        self.db_log = QPlainTextEdit()
        self.db_log.setObjectName("Code")
        self.db_log.setReadOnly(True)
        self.db_log.setMaximumHeight(130)
        self.db_log.setLayoutDirection(Qt.LeftToRight)
        v.addWidget(self.db_log, 1)
        return w

    def _build_tray(self):
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(tr("app_title"))
        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(self.fill_tray_menu)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(lambda r: self.show_window() if r in (
            QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
        self.tray.show()

    def fill_tray_menu(self):
        t = self.t
        m = self.tray_menu
        m.clear()
        m.addAction(app_icon(), tr("tray_open"), self.show_window)
        m.addSeparator()
        for i in self.reg.instances:
            st = self.statuses.get(i.id, {}).get("status")
            sub = m.addMenu(icon("server", t["success"] if st == "running" else t["danger"]), f"{i.name}   :{i.port}")
            sub.addAction(icon("play", t["success"]), tr("start"), lambda i=i: self.control("start", i))
            sub.addAction(icon("stop", t["danger"]), tr("stop"), lambda i=i: self.control("stop", i))
            sub.addAction(icon("restart", t["text"]), tr("restart"), lambda i=i: self.control("restart", i))
            sub.addAction(icon("globe", t["text"]), tr("open_browser"), lambda i=i: webbrowser.open(i.url))
        m.addSeparator()
        m.addAction(icon("play", t["success"]), tr("start_all"), lambda: self.control_all("start"))
        m.addAction(icon("stop", t["danger"]), tr("stop_all"), lambda: self.control_all("stop"))
        m.addSeparator()
        m.addAction(tr("quit"), self.quit_app)

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------ appearance
    def toggle_lang(self):
        self.settings["language"] = "en" if self.settings.get("language", "ar") == "ar" else "ar"
        save_settings(self.settings)
        self.relaunch.emit()

    def toggle_theme(self):
        self.settings["theme"] = "light" if self.settings.get("theme") == "dark" else "dark"
        save_settings(self.settings)
        self.relaunch.emit()

    # ------------------------------------------------------------------ list
    def current(self) -> Instance | None:
        it = self.list.currentItem()
        return self.reg.get(it.data(Qt.UserRole)) if it else None

    def refresh_list(self, keep: str | None = None):
        cur = keep or (self.current().id if self.current() else None)
        self.list.blockSignals(True)
        self.list.clear()
        self.cards = {}
        sel = None
        for i in self.reg.instances:
            it = QListWidgetItem()
            it.setData(Qt.UserRole, i.id)
            card = ServerCard(i, self.t)
            if i.id in self.statuses:
                card.update_data(i, self.statuses[i.id])
            it.setSizeHint(QSize(0, 64))
            self.list.addItem(it)
            self.list.setItemWidget(it, card)
            self.cards[i.id] = card
            if i.id == cur:
                sel = it
        self.list.blockSignals(False)
        has = bool(self.reg.instances)
        self.list.setVisible(has)
        self.empty_lbl.setVisible(not has)
        self.count_lbl.setText(str(len(self.reg.instances)))
        if has:
            self.list.setCurrentItem(sel or self.list.item(0))
        self.filter_list()
        self.apply_statuses()
        self.on_select()

    def filter_list(self):
        q = self.search.text().strip().lower()
        for r in range(self.list.count()):
            it = self.list.item(r)
            inst = self.reg.get(it.data(Qt.UserRole))
            it.setHidden(bool(q) and q not in (inst.name.lower() + str(inst.port)))

    def apply_statuses(self):
        for i in self.reg.instances:
            info = self.statuses.get(i.id)
            if info and i.id in self.cards:
                self.cards[i.id].update_data(i, info)
        total = len(self.reg.instances)
        running = sum(1 for s in self.statuses.values() if s.get("status") == "running")
        self.stat_total.value.setText(str(total))
        self.stat_run.value.setText(str(running))
        self.stat_stop.value.setText(str(max(0, total - running)))
        self.tray.setToolTip(tr("tray_tip", r=running, t=total))
        self.update_header()

    def poll(self):
        if self.poller and self.poller.isRunning():
            return
        self.poller = StatusPoller(self.reg.instances)
        self.poller.result.connect(self.on_statuses)
        self.poller.start()

    def on_statuses(self, res):
        if self.settings.get("notify_stop", True):
            for iid, info in res.items():
                old = self.statuses.get(iid, {}).get("status")
                if old == "running" and info.get("status") == "stopped" and iid not in self.expected_stop:
                    inst = self.reg.get(iid)
                    if inst:
                        self.tray.showMessage(tr("app_title"), tr("stopped_alone", n=inst.name),
                                              QSystemTrayIcon.Warning, 8000)
                if info.get("status") == "stopped":
                    self.expected_stop.discard(iid)
        self.statuses = res
        self.apply_statuses()
        if self.tabs.currentIndex() == 0:
            self.update_overview(light=True)

    def list_menu(self, pos):
        i = self.current()
        if not i:
            return
        t = self.t
        m = QMenu(self)
        m.addAction(icon("play", t["success"]), tr("start"), lambda: self.control("start"))
        m.addAction(icon("stop", t["danger"]), tr("stop"), lambda: self.control("stop"))
        m.addAction(icon("restart", t["text"]), tr("restart"), lambda: self.control("restart"))
        m.addAction(icon("globe", t["text"]), tr("open_browser"), self.open_browser)
        m.addSeparator()
        m.addAction(icon("folder", t["text"]), tr("open_folder"), lambda: self.reveal(i.conf_path))
        m.addAction(icon("edit", t["text"]), tr("edit"), self.edit_instance)
        m.addAction(icon("delete", t["danger"]), tr("remove"), self.remove_instance)
        m.exec(self.list.viewport().mapToGlobal(pos))

    def on_select(self):
        self.tail_path, self.tail_pos = None, 0
        self.log_view.clear()
        i = self.current()
        self.stack.setCurrentIndex(1 if i else 0)
        if i:
            self.update_header()
            self.on_tab(self.tabs.currentIndex())

    def update_header(self):
        i = self.current()
        if not i:
            return
        info = self.statuses.get(i.id, {})
        st = info.get("status", "?")
        self.d_title.setText(i.name)
        self.d_pill.set_status(st)
        self.d_kind.setText(tr("kind_service") if i.kind == "service" else tr("kind_bin"))
        self.d_url.setText(f'<a style="color:{self.t["primary"]}; text-decoration:none" href="{i.url}">{i.url}  ↗</a>')
        self.b_start.setEnabled(st not in ("running", "starting"))
        self.b_stop.setEnabled(st in ("running", "starting"))
        for b, ic, var in ((self.b_start, "play", "success"), (self.b_stop, "stop", "danger")):
            c = ({"success": "#FFFFFF", "danger": self.t["danger"]}[var] if b.isEnabled() else self.t["faint"])
            b.setIcon(icon(ic, c))

    def on_tab(self, idx):
        if not self.current():
            return
        [self.update_overview, lambda: self.load_log(full=True), self.load_conf, self.load_dbs][idx]()

    # ------------------------------------------------------------------ actions
    def run_task(self, fn, ok_msg="", on_done=None, log=None):
        t = Task(fn, ok_msg)
        t.log.connect(log or (lambda s: self.statusBar().showMessage(s)))

        def finished(ok, msg):
            if ok:
                if msg:
                    self.statusBar().showMessage("✓  " + msg, 6000)
            else:
                QMessageBox.warning(self, tr("err"), msg)
                self.statusBar().showMessage(tr("failed", m=msg), 8000)
            if on_done:
                on_done(ok, msg)
            self.reg.save()
            self.poll()
            self.tasks.remove(t)
        t.done.connect(finished)
        self.tasks.append(t)
        t.start()

    def control(self, what: str, inst: Instance | None = None):
        i = inst or self.current()
        if not i:
            return
        a = tr(what)
        if what in ("stop", "restart"):
            self.expected_stop.add(i.id)
        self.statusBar().showMessage(tr("doing_action", a=a, n=i.name))
        self.run_task(lambda log: getattr(i, what)(), tr("done_action", a=a, n=i.name))

    def control_all(self, what: str):
        for i in self.reg.instances:
            self.control(what, i)

    def autostart_instances(self):
        for i in self.reg.instances:
            if i.autostart and i.kind == "bin" and self.statuses.get(i.id, {}).get("status") != "running":
                self.control("start", i)

    # ------------------------------------------------------------------ updates
    def check_updates(self, manual=False):
        if not updater.enabled() or (self._upd_thread and self._upd_thread.isRunning()):
            return
        th = UpdateCheck()
        th.found.connect(lambda m: self.on_update_found(m, manual))
        th.failed.connect(lambda e: manual and QMessageBox.warning(self, tr("check_updates"), tr("upd_check_failed", e=e)))
        self._upd_thread = th
        th.start()

    def on_update_found(self, m: dict, manual: bool):
        if not m:
            if manual:
                QMessageBox.information(self, tr("check_updates"), tr("upd_latest", v=APP_VERSION))
            return
        if not manual and not m.get("mandatory") and self.settings.get("skip_version") == m["version"]:
            return
        self.show_window()
        box = QMessageBox(self)
        box.setWindowTitle(tr("upd_title"))
        box.setIcon(QMessageBox.Information)
        notes = (m.get("notes_ar") if i18n.is_rtl() else m.get("notes")) or m.get("notes") or ""
        box.setText(tr("upd_available", v=m["version"], c=APP_VERSION)
                    + (("\n\n" + notes) if notes else "")
                    + (("\n\n" + tr("upd_mandatory")) if m.get("mandatory") else ""))
        now = box.addButton(tr("upd_now"), QMessageBox.AcceptRole)
        later = skip = None
        if m.get("mandatory"):
            box.addButton(tr("quit"), QMessageBox.RejectRole)
        else:
            later = box.addButton(tr("upd_later"), QMessageBox.RejectRole)
            skip = box.addButton(tr("upd_skip"), QMessageBox.ActionRole)
        box.exec()
        if box.clickedButton() is now:
            self.download_update(m)
        elif box.clickedButton() is skip:
            self.settings["skip_version"] = m["version"]
            save_settings(self.settings)
        elif m.get("mandatory") and box.clickedButton() is not later:
            self.quit_app()

    def download_update(self, m: dict):
        from PySide6.QtWidgets import QProgressDialog
        dlg = QProgressDialog(tr("upd_downloading", v=m["version"]), tr("cancel"), 0, 100, self)
        dlg.setWindowTitle(tr("upd_title"))
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setValue(0)
        th = UpdateDownload(m)
        th.progress.connect(dlg.setValue)
        dlg.canceled.connect(lambda: setattr(th, "stop", True))

        def fin(ok, res):
            dlg.close()
            if not ok:
                if res != tr("cancelled"):
                    QMessageBox.warning(self, tr("upd_title"), tr("upd_failed", e=res))
                return
            QMessageBox.information(self, tr("upd_title"), tr("upd_installing"))
            updater.launch_installer(res)
            self.quit_app()
        th.done.connect(fin)
        self._upd_dl = th
        th.start()

    def pg_bin(self) -> str:
        """PostgreSQL tools folder, re-detected whenever the saved one is missing or empty."""
        p = resolve_pg_bin(self.settings.get("pg_bin", ""))
        if p != self.settings.get("pg_bin"):
            self.settings["pg_bin"] = p
            save_settings(self.settings)
        return p

    def show_welcome(self):
        WelcomeDialog(self, self.t).exec()
        self.settings["welcome_done"] = True
        save_settings(self.settings)

    # ------------------------------------------------------------------ modules
    def open_custom(self):
        i = self.current()
        d = i and (custom_addons_dir(i) or self.ensure_custom_dir(i))
        if d:
            os.startfile(d)

    def ensure_custom_dir(self, i: Instance) -> str | None:
        """No custom addons folder yet: offer to create one and add it to addons_path."""
        if not i.conf_path or not os.path.exists(i.conf_path):
            QMessageBox.warning(self, tr("err"), tr("no_custom_dir"))
            return None
        sug = suggest_custom_dir(i)
        m = QMessageBox(self)
        m.setWindowTitle(tr("add_module"))
        m.setIcon(QMessageBox.Question)
        m.setText(tr("make_custom_q", p=sug))
        b_ok = m.addButton(tr("make_here"), QMessageBox.AcceptRole)
        b_pick = m.addButton(tr("pick_other"), QMessageBox.ActionRole)
        m.addButton(tr("cancel"), QMessageBox.RejectRole)
        m.exec()
        if m.clickedButton() is b_pick:
            sug = QFileDialog.getExistingDirectory(self, tr("pick_other"), os.path.dirname(sug))
        elif m.clickedButton() is not b_ok:
            return None
        if not sug:
            return None
        try:
            add_custom_dir(i, os.path.normpath(sug))
        except Exception as e:
            QMessageBox.warning(self, tr("err"), str(e))
            return None
        if self.statuses.get(i.id, {}).get("status") == "running":
            self.expected_stop.add(i.id)
            self.control("restart", i)
        if self.tabs.currentIndex() == 2:
            self.load_conf()
        self.statusBar().showMessage("✓  " + tr("custom_made", p=sug), 8000)
        return custom_addons_dir(i)

    def add_module(self):
        i = self.current()
        if not i:
            return
        if not (custom_addons_dir(i) or self.ensure_custom_dir(i)):
            return
        m = QMessageBox(self)
        m.setWindowTitle(tr("add_module"))
        m.setText(tr("add_module_q", p=custom_addons_dir(i)))
        bf = m.addButton(tr("pick_folder"), QMessageBox.AcceptRole)
        bz = m.addButton(tr("pick_zip"), QMessageBox.AcceptRole)
        m.addButton(tr("cancel"), QMessageBox.RejectRole)
        m.exec()
        if m.clickedButton() is bf:
            src = QFileDialog.getExistingDirectory(self, tr("add_module"))
        elif m.clickedButton() is bz:
            src = QFileDialog.getOpenFileName(self, tr("add_module"), "", "Zip (*.zip)")[0]
        else:
            return
        if not src:
            return
        res = {}

        def work(log):
            res["n"] = install_module(i, src, log)
            if i.status() == "running":
                i.restart()

        def done(ok, _m):
            if ok:
                QMessageBox.information(self, tr("add_module"), tr("mod_added", n=", ".join(res["n"])))
        self.expected_stop.add(i.id)
        self.run_task(work, tr("add_module"), on_done=done)

    def upgrade_module(self):
        i = self.current()
        if not i:
            return
        try:
            dbs = [n for n, _ in db.list_databases(i)]
        except Exception as e:
            return QMessageBox.warning(self, tr("err"), str(e))
        if not dbs:
            return QMessageBox.information(self, tr("upd_module"), tr("rm_no_dbs"))
        dname, ok = QInputDialog.getItem(self, tr("upd_module"), tr("pick_db_for"), dbs, 0, False)
        if not ok:
            return
        mods, ok = QInputDialog.getText(self, tr("upd_module"), tr("mod_names"))
        mods = ",".join(x.strip() for x in mods.split(",") if x.strip())
        if not (ok and mods):
            return
        was_running = i.status() == "running"

        def work(log):
            update_module(i, dname, mods, log)
            if was_running:
                i.restart()
        self.expected_stop.add(i.id)
        self.run_task(work, tr("upd_done", n=mods))

    def copy_master(self):
        i = self.current()
        if not i:
            return
        pw = conf_value(i.conf, "admin_passwd") or ""
        if not pw:
            return QMessageBox.information(self, tr("copy_master"), tr("master_none"))
        if pw.startswith("$pbkdf2"):
            return QMessageBox.information(self, tr("copy_master"), tr("master_hashed"))
        QGuiApplication.clipboard().setText(pw)
        self.statusBar().showMessage("✓  " + tr("master_copied"), 5000)

    # ------------------------------------------------------------------ auto backup
    def auto_backup(self):
        s = self.settings
        if not s.get("auto_backup") or getattr(self, "_auto_busy", False):
            return
        last = dict(s.get("auto_backup_last") or {})
        now = time.time()
        keep = int(s.get("auto_backup_keep", 7))
        insts = [i for i in self.reg.instances if self.statuses.get(i.id, {}).get("status") == "running"]
        if not insts:
            return
        pg = self.pg_bin()
        root = os.path.join(s.get("backup_dir"), "auto")

        def work(log):
            for i in insts:
                for n, _ in db.list_databases(i):
                    key = f"{i.id}:{n}"
                    if now - last.get(key, 0) < 23 * 3600:
                        continue
                    d = os.path.join(root, n)
                    db.backup(i, n, pg, d, log)
                    last[key] = time.time()
                    zips = sorted(f for f in os.listdir(d) if f.endswith(".zip"))
                    for old in zips[:-keep]:
                        os.remove(os.path.join(d, old))

        def done(ok, _m):
            self._auto_busy = False
            self.settings["auto_backup_last"] = last
            save_settings(self.settings)
        self._auto_busy = True
        self.run_task(work, tr("auto_backup_done"), on_done=done)

    def open_browser(self):
        i = self.current()
        if i:
            webbrowser.open(i.url)

    def new_server(self):
        defaults = {}
        for i in self.reg.instances:
            c = i.conf
            if conf_value(c, "db_user"):
                defaults = dict(db_host=conf_value(c, "db_host", "localhost"),
                                db_port=conf_value(c, "db_port", "5432"),
                                db_user=conf_value(c, "db_user"), db_password=conf_value(c, "db_password", ""))
                break
        d = NewServerWizard(self, self.reg.used_ports(), defaults, self.t)
        if d.exec() and d.result_instance:
            self.reg.add(d.result_instance)
            self.refresh_list(keep=d.result_instance.id)

    def add_existing(self):
        d = InstanceDialog(self, None, self.t)
        if d.exec():
            self.reg.add(d.inst)
            self.refresh_list(keep=d.inst.id)

    def detect_services(self):
        known = {i.service_name for i in self.reg.instances if i.kind == "service"}
        new = [s for s in discover_services() if s.service_name not in known]
        for s in new:
            self.reg.add(s)
        QMessageBox.information(self, tr("detect_services"),
                                tr("detect_added", c=len(new)) if new else tr("detect_none"))
        self.refresh_list()

    def edit_instance(self):
        i = self.current()
        if i and InstanceDialog(self, i, self.t).exec():
            self.reg.save()
            self.refresh_list(keep=i.id)

    def remove_instance(self):
        i = self.current()
        if not i:
            return
        d = RemoveDialog(self, i, self.reg.instances)
        if not d.exec():
            return
        dbs, folder = d.choice()
        if dbs or folder:
            items = "\n".join(["• " + n for n in dbs] + (["• " + folder] if folder else []))
            if QMessageBox.warning(self, tr("remove"), tr("rm_confirm", x=items),
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
        if not (dbs or folder):
            self.reg.remove(i)
            return self.refresh_list()
        pg = self.pg_bin()

        def work(log):
            if i.status() in ("running", "starting"):
                i.stop()
                for _ in range(30):
                    if i.status() == "stopped":
                        break
                    time.sleep(1)
            for n in dbs:
                db.drop(i, n, pg, log)
            if folder:
                import shutil, stat
                shutil.rmtree(folder, onerror=lambda f, p, _e: (os.chmod(p, stat.S_IWRITE), f(p)))

        def done(ok, _msg):
            if ok:
                self.reg.remove(i)
                self.refresh_list()

        self.run_task(work, tr("rm_done"), on_done=done)

    def open_settings(self):
        old = (self.settings.get("language"), self.settings.get("theme"))
        d = SettingsDialog(self, self.settings)
        if d.exec():
            self.settings = d.values()
            save_settings(self.settings)
            try:
                set_start_with_windows(self.settings["start_with_windows"])
            except Exception as e:
                QMessageBox.warning(self, tr("err"), str(e))
            if (self.settings.get("language"), self.settings.get("theme")) != old:
                self.relaunch.emit()

    def reveal(self, path, is_dir=False):
        if not path:
            return
        if is_dir:
            os.makedirs(path, exist_ok=True)
            os.startfile(path)
        elif os.path.exists(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])

    # ------------------------------------------------------------------ overview
    def update_overview(self, light=False):
        i = self.current()
        if not i:
            return
        info = self.statuses.get(i.id, {})
        st = info.get("status", "?")
        tone = STATUS_TONE.get(st, "faint")
        self.tiles["status"].value.setText(tr("s_" + st) if st in STATUS_TONE else "…")
        self.tiles["status"].value.setStyleSheet(f"color:{self.t.get(tone, self.t['muted'])}")
        self.tiles["port"].value.setText(str(info.get("port") or i.port))
        self.tiles["pid"].value.setText(str(info.get("pid") or "—"))
        self.tiles["uptime"].value.setText(fmt_uptime(info["uptime"]) if info.get("uptime") else "—")
        self.tiles["memory"].value.setText(fmt_mem(info["mem"]) if info.get("mem") else "—")
        self.tiles["type"].value.setText(tr("kind_service") if i.kind == "service" else tr("kind_bin"))
        if light:
            return
        while self.path_grid.count():
            w = self.path_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        rows = []
        if i.kind == "service":
            rows += [(tr("service_name"), i.service_name, False), (tr("start_type"), i.service_start_type(), False)]
        rows += [("Python", i.python_exe, True), ("odoo-bin", i.odoo_bin, True), ("odoo.conf", i.conf_path, True),
                 (tr("log_file"), i.log_path or "—", True), ("data_dir", i.data_dir, True)]
        for r, (k, val, is_path) in enumerate(rows):
            kl = QLabel(k)
            kl.setObjectName("Muted")
            vl = QLabel(val or "—")
            vl.setObjectName("Mono")
            vl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            vl.setLayoutDirection(Qt.LeftToRight)
            vl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            vl.setToolTip(val or "")
            vl.setMinimumWidth(60)
            from PySide6.QtWidgets import QSizePolicy
            vl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            self.path_grid.addWidget(kl, r, 0)
            self.path_grid.addWidget(vl, r, 1)
            if is_path and val and val != "—":
                cb = QToolButton()
                cb.setProperty("variant", "ghost")
                cb.setIcon(icon("copy", self.t["muted"]))
                cb.setToolTip(tr("copy"))
                cb.clicked.connect(lambda _=False, v=val: (QGuiApplication.clipboard().setText(v),
                                                            self.statusBar().showMessage(tr("copied"), 2000)))
                ob = QToolButton()
                ob.setProperty("variant", "ghost")
                ob.setIcon(icon("folder", self.t["muted"]))
                ob.setToolTip(tr("open_folder"))
                ob.clicked.connect(lambda _=False, v=val: self.reveal(v))
                self.path_grid.addWidget(cb, r, 2)
                self.path_grid.addWidget(ob, r, 3)
        if i.kind == "service":
            self.auto_cb.setText(tr("autostart_svc"))
            self.auto_cb.setChecked(i.service_start_type() == "automatic")
        else:
            self.auto_cb.setText(tr("autostart_bin"))
            self.auto_cb.setChecked(i.autostart)

    def toggle_autostart(self, checked):
        i = self.current()
        if not i:
            return
        if i.kind == "service":
            self.run_task(lambda log: i.set_service_autostart(checked), on_done=lambda *_: self.update_overview())
        else:
            i.autostart = checked
            self.reg.save()

    def check_ports(self):
        lines = []
        for i in self.reg.instances:
            o = port_owner(i.port)
            mine = self.statuses.get(i.id, {}).get("pid")
            own = set()
            if mine and psutil.pid_exists(mine):
                try:
                    own = {mine} | {c.pid for c in psutil.Process(mine).children(recursive=True)}
                except psutil.Error:
                    own = {mine}
            if not o:
                lines.append(tr("port_free", n=i.name, p=i.port))
            elif isinstance(o, psutil.Process) and o.pid in own:
                lines.append(tr("port_self", n=i.name, p=i.port))
            else:
                who = f"{o.name()} (PID {o.pid})" if isinstance(o, psutil.Process) else tr("unknown")
                lines.append(tr("port_other", n=i.name, p=i.port, w=who))
        dup = {}
        for i in self.reg.instances:
            dup.setdefault(i.port, []).append(i.name)
        for p, names in dup.items():
            if len(names) > 1:
                lines.append(tr("port_dup", ns=", ".join(names), p=p))
        QMessageBox.information(self, tr("ports_title"), "\n".join(lines) or "—")

    # ------------------------------------------------------------------ log
    def open_log_file(self):
        i = self.current()
        if i and i.log_path and os.path.exists(i.log_path):
            os.startfile(i.log_path)

    def _append_log(self, text: str):
        flt = self.log_filter.text().strip().lower()
        cur = QTextCursor(self.log_view.document())
        cur.movePosition(QTextCursor.End)
        added = False
        for line in text.splitlines():
            if flt and flt not in line.lower():
                continue
            color = "#D0D5DD"
            if " ERROR " in line or " CRITICAL " in line or "Traceback" in line:
                color = "#F97066"
            elif " WARNING " in line:
                color = "#FDB022"
            elif "=====" in line:
                color = "#53B1FD"
            elif " INFO " in line:
                color = "#B9C0CC"
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if not self.log_view.document().isEmpty() or added:
                cur.insertBlock()
            cur.insertText(line, fmt)
            added = True
        if added and self.follow.isChecked():
            sb = self.log_view.verticalScrollBar()
            sb.setValue(sb.maximum())

    def load_log(self, full=False):
        i = self.current()
        if full:
            self.log_view.clear()
            self.tail_path, self.tail_pos = None, 0
        if not i:
            return
        p = i.log_path
        if not p:
            self.log_view.setPlainText(tr("no_log"))
            return
        if not os.path.exists(p):
            self.log_view.setPlainText(tr("log_missing", p=p))
            self.tail_path = p
            self._log_placeholder = True
            return
        size = os.path.getsize(p)
        self.tail_path, self.tail_pos = p, max(0, size - 200_000)
        self.tail_log()

    def tail_log(self):
        if self.tabs.currentIndex() != 1 or not self.tail_path:
            return
        p = self.tail_path
        try:
            size = os.path.getsize(p)
        except OSError:
            return
        if size < self.tail_pos:
            self.tail_pos = 0
        if size == self.tail_pos:
            return
        if getattr(self, "_log_placeholder", False):
            self.log_view.clear()
            self._log_placeholder = False
        with open(p, "rb") as f:
            f.seek(self.tail_pos)
            data = f.read(min(size - self.tail_pos, 2_000_000))
        self.tail_pos += len(data)
        self._append_log(data.decode("utf-8", "replace"))

    # ------------------------------------------------------------------ conf
    def load_conf(self):
        i = self.current()
        self.conf_edit.clear()
        if not i:
            return
        self.conf_label.setText(i.conf_path)
        try:
            with open(i.conf_path, encoding="utf-8-sig", errors="replace") as f:
                self.conf_edit.setPlainText(f.read())
        except Exception as e:
            self.conf_edit.setPlainText(tr("cant_open", e=e))

    def save_conf(self):
        i = self.current()
        if not i:
            return
        try:
            write_conf_text(i.conf_path, self.conf_edit.toPlainText())
        except Exception as e:
            return QMessageBox.warning(self, tr("err"), str(e))
        if self.statuses.get(i.id, {}).get("status") == "running" and QMessageBox.question(
                self, tr("save"), tr("conf_restart_q")) == QMessageBox.Yes:
            self.control("restart", i)
        else:
            self.statusBar().showMessage("✓  " + tr("conf_saved"), 5000)
        self.refresh_list(keep=i.id)

    # ------------------------------------------------------------------ databases
    def load_dbs(self):
        i = self.current()
        self.db_table.setRowCount(0)
        if not i:
            return
        res = {}

        def fetch(log):
            res["v"] = db.list_databases(i)

        t = Task(fetch)

        def fin(ok, msg):
            self.tasks.remove(t)
            if not ok:
                self.db_log.appendPlainText("✗ " + msg)
                return
            rows = res.get("v", [])
            self.db_table.setRowCount(len(rows))
            for r, (n, s) in enumerate(rows):
                a = QTableWidgetItem(icon("db", self.t["primary"]), "  " + n)
                a.setData(Qt.UserRole, n)
                self.db_table.setItem(r, 0, a)
                self.db_table.setItem(r, 1, QTableWidgetItem(s))
                b = QPushButton(icon("delete", self.t["danger"]), " " + tr("delete"))
                b.setProperty("variant", "ghost")
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet("QPushButton{color:%s; padding:2px 10px; min-height:26px;}" % self.t["danger"])
                b.clicked.connect(lambda _=False, n=n: self.drop_db(n))
                cell = QWidget()
                cl = QHBoxLayout(cell)
                cl.setContentsMargins(6, 4, 6, 4)
                cl.addWidget(b)
                self.db_table.setCellWidget(r, 2, cell)
        t.done.connect(fin)
        self.tasks.append(t)
        t.start()

    def selected_db(self) -> str | None:
        rows = self.db_table.selectionModel().selectedRows()
        return self.db_table.item(rows[0].row(), 0).data(Qt.UserRole) if rows else None

    def open_db(self):
        i, n = self.current(), self.selected_db()
        if i and n:
            webbrowser.open(f"{i.url}/web?db={n}")

    def backup_db(self):
        i, n = self.current(), self.selected_db()
        if not (i and n):
            return QMessageBox.information(self, tr("backup"), tr("pick_db"))
        self.db_log.appendPlainText(tr("backing_up", n=n))
        self.run_task(lambda log: db.backup(i, n, self.pg_bin(), self.settings["backup_dir"], log),
                      tr("backup_done", n=n), log=self.db_log.appendPlainText)

    def restore_db(self):
        i = self.current()
        if not i:
            return
        f, _ = QFileDialog.getOpenFileName(self, tr("pick_backup"), self.settings["backup_dir"],
                                           "Backup (*.zip *.dump *.backup *.sql);;All (*)")
        if not f:
            return
        name, ok = QInputDialog.getText(self, tr("restore"), tr("new_db_name"),
                                        text=re.sub(r"_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$", "",
                                                    os.path.splitext(os.path.basename(f))[0]) + "_restored")
        if not (ok and name.strip()):
            return
        self.run_task(lambda log: db.restore(i, f, name.strip(), self.pg_bin(), log),
                      tr("restore_done", n=name), on_done=lambda *_: self.load_dbs(),
                      log=self.db_log.appendPlainText)

    def drop_db(self, name=None):
        i, n = self.current(), (name or self.selected_db())
        if not (i and n):
            return QMessageBox.information(self, tr("delete"), tr("pick_db"))
        txt, ok = QInputDialog.getText(self, tr("delete"), tr("drop_confirm", n=n))
        if ok and txt.strip() != n:
            return QMessageBox.information(self, tr("delete"), tr("drop_mismatch"))
        if ok:
            self.run_task(lambda log: db.drop(i, n, self.pg_bin(), log), tr("drop_done", n=n),
                          on_done=lambda *_: self.load_dbs(), log=self.db_log.appendPlainText)

    # ------------------------------------------------------------------ responsive
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not hasattr(self, "b_start"):
            return
        compact = self.width() < 1200
        for b, key in ((self.b_start, "start"), (self.b_stop, "stop"),
                       (self.b_restart, "restart"), (self.b_open, "open_browser")):
            b.setText("" if compact else tr(key))
            b.setToolTip(tr(key))
        self.d_kind.setVisible(self.width() >= 1000)
        show_stats = self.height() >= 720
        for s in (self.stat_total, self.stat_run, self.stat_stop):
            s.setVisible(show_stats)

    # ------------------------------------------------------------------ close
    def closeEvent(self, e):
        if self.settings.get("minimize_to_tray") and not self._quitting:
            e.ignore()
            self.hide()
            self.tray.showMessage(tr("app_title"), tr("tray_still"), QSystemTrayIcon.Information, 2500)
        else:
            e.accept()

    def dispose(self):
        """Tear down before a relaunch (language/theme switch)."""
        self._quitting = True
        self.poll_timer.stop()
        self.tail_timer.stop()
        self.backup_timer.stop()
        self.update_timer.stop()
        for t in list(self.tasks) + ([self.poller] if self.poller else []):
            t.wait(5000)
        self.reg.save()
        self.tray.hide()
        self.close()
        self.deleteLater()

    def quit_app(self):
        self._quitting = True
        self.reg.save()
        self.tray.hide()
        QApplication.quit()
