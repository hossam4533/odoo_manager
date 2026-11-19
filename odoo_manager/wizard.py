"""Dialogs: new-server wizard (clone + venv + requirements + conf) and instance editor."""
from __future__ import annotations

import os
import secrets
import subprocess
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter,
                               QVBoxLayout, QWidget)

from . import core
from .core import CREATE_NO_WINDOW, Instance, find_free_port, find_pythons, python_version
from .i18n import tr
from .theme import PALETTES, icon

ODOO_GIT = "https://github.com/odoo/odoo.git"
ENT_GIT = "https://github.com/odoo/enterprise.git"


def path_row(edit: QLineEdit, mode: str, filt: str = "") -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    edit.setLayoutDirection(Qt.LeftToRight)
    h.addWidget(edit)
    b = QPushButton()
    b.setIcon(icon("folder", PALETTES["light"]["muted"]))
    b.setFixedWidth(40)
    b.setCursor(Qt.PointingHandCursor)

    def pick():
        if mode == "dir":
            p = QFileDialog.getExistingDirectory(w, tr("pick_dir"), edit.text())
        else:
            p, _ = QFileDialog.getOpenFileName(w, tr("pick_file"), edit.text(), filt)
        if p:
            edit.setText(os.path.normpath(p))
    b.clicked.connect(pick)
    h.addWidget(b)
    return w


def fit_to_screen(w: QWidget, width: int, height: int) -> None:
    """Size a window to (width, height) but never larger than 90% of the screen, centered."""
    from PySide6.QtGui import QGuiApplication
    scr = (w.parentWidget().screen() if w.parentWidget() else None) or QGuiApplication.primaryScreen()
    if not scr:
        w.resize(width, height)
        return
    a = scr.availableGeometry()
    ww = min(width, int(a.width() * 0.9))
    hh = min(height, int(a.height() * 0.9))
    w.resize(ww, hh)
    w.move(a.x() + (a.width() - ww) // 2, a.y() + (a.height() - hh) // 2)


def dialog_header(title: str, sub: str, ic: str, t: dict) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 6)
    h.setSpacing(14)
    il = QLabel()
    il.setFixedSize(48, 48)
    il.setAlignment(Qt.AlignCenter)
    il.setPixmap(icon(ic, t["primary"], 48).pixmap(24, 24))
    il.setStyleSheet(f"background:{t['primary_soft']}; border-radius:14px;")
    h.addWidget(il)
    v = QVBoxLayout()
    v.setSpacing(2)
    a = QLabel(title)
    a.setObjectName("DetailTitle")
    v.addWidget(a)
    if sub:
        b = QLabel(sub)
        b.setObjectName("Muted")
        v.addWidget(b)
    h.addLayout(v, 1)
    return w


class SetupWorker(QThread):
    line = Signal(str)
    done = Signal(bool, str)

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self._proc = None
        self._cancel = False

    def cancel(self):
        self._cancel = True
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass

    def sh(self, cmd: list[str], cwd: str | None = None):
        if self._cancel:
            raise RuntimeError(tr("cancelled"))
        self.line.emit("> " + " ".join(cmd))
        self._proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, encoding="utf-8", errors="replace",
                                      creationflags=CREATE_NO_WINDOW)
        buf = ""
        while True:
            ch = self._proc.stdout.read(1)
            if not ch:
                break
            if ch in "\r\n":
                if buf.strip():
                    self.line.emit(buf)
                buf = ""
            else:
                buf += ch
        if buf.strip():
            self.line.emit(buf)
        rc = self._proc.wait()
        if rc != 0:
            raise RuntimeError(tr("cmd_failed", c=rc))

    def run(self):
        c = self.cfg
        try:
            base = Path(c["base"])
            src = base / "src"
            for d in (base, base / "custom_addons", base / "data"):
                d.mkdir(parents=True, exist_ok=True)

            if c["clone"]:
                if (src / "odoo-bin").exists():
                    self.line.emit(tr("src_exists"))
                else:
                    if src.exists() and any(src.iterdir()):
                        import shutil, stat
                        self.line.emit(tr("cleaning_partial"))
                        shutil.rmtree(src, onerror=lambda f, p, _e: (os.chmod(p, stat.S_IWRITE), f(p)))
                    self.line.emit(tr("downloading", b=c["branch"]))
                    self.sh([core.find_git() or "git", "clone", "--progress", "--depth", "1", "-b", c["branch"],
                             ODOO_GIT, str(src)])
            else:
                src = Path(c["src"])
            if not (src / "odoo-bin").exists():
                raise RuntimeError(tr("no_odoo_bin", p=src))

            ent = None
            if c.get("edition") == "enterprise":
                if c.get("ent_src"):
                    ent = Path(c["ent_src"])
                else:
                    ent = base / "enterprise"
                    if not (ent / "web_enterprise").exists():
                        self.line.emit(tr("downloading_ent"))
                        self.sh([core.find_git() or "git", "clone", "--progress", "--depth", "1", "-b", c["branch"],
                                 c["ent_git"], str(ent)])
                if not (ent / "web_enterprise").exists():
                    raise RuntimeError(tr("no_enterprise", p=ent))

            py = c["python"]
            if c["venv"]:
                venv = base / "venv"
                if not (venv / "Scripts" / "python.exe").exists():
                    self.line.emit(tr("making_venv"))
                    self.sh([py, "-m", "venv", str(venv)])
                py = str(venv / "Scripts" / "python.exe")
                self.sh([py, "-m", "pip", "install", "-U", "pip", "wheel", "setuptools"])
                self.line.emit(tr("installing_req"))
                self.sh([py, "-m", "pip", "install", "-r", str(src / "requirements.txt")], cwd=str(src))

            conf = base / "odoo.conf"
            if conf.exists():
                self.line.emit(tr("conf_exists"))
            else:
                addons = ([str(ent)] if ent else []) + [str(src / "addons"), str(src / "odoo" / "addons"), str(base / "custom_addons")]
                conf.write_text("\n".join([
                    "[options]",
                    f"addons_path = {','.join(addons)}",
                    f"admin_passwd = {c['admin_passwd']}",
                    f"data_dir = {base / 'data'}",
                    f"db_host = {c['db_host']}",
                    f"db_port = {c['db_port']}",
                    f"db_user = {c['db_user']}",
                    f"db_password = {c['db_password']}",
                    f"http_port = {c['port']}",
                    f"gevent_port = {c['port'] + 3}",
                    "proxy_mode = False",
                    "list_db = True",
                    "",
                ]), "utf-8")
                self.line.emit(tr("conf_created", p=conf))

            self.result = Instance(name=c["name"], kind="bin", conf_path=str(conf),
                                   odoo_bin=str(src / "odoo-bin"), python_exe=py)
            self.done.emit(True, tr("setup_ok"))
        except Exception as e:
            self.done.emit(False, str(e))


class PgUserDialog(QDialog):
    """Database user for Odoo: name + password (+ superuser password when PostgreSQL already exists)."""

    def __init__(self, parent, install: bool, servers: list):
        super().__init__(parent)
        self.setWindowTitle("PostgreSQL")
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(10)
        head = QLabel(tr("pgu_head_install") if install else tr("pgu_head_setup"))
        head.setWordWrap(True)
        v.addWidget(head)
        f = QFormLayout()
        f.setSpacing(8)
        self.user = QLineEdit("odoo")
        self.user.setLayoutDirection(Qt.LeftToRight)
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.Password)
        self.su = QLineEdit()
        self.su.setEchoMode(QLineEdit.Password)
        f.addRow(tr("pgu_user"), self.user)
        f.addRow(tr("pgu_pw"), self.pw)
        f.addRow(tr("pgu_pw2"), self.pw2)
        if not install:
            f.addRow(tr("pgu_su"), self.su)
        v.addLayout(f)
        hint = QLabel(tr("pgu_hint_install") if install else tr("pgu_hint_setup"))
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.apply = QCheckBox(tr("pgu_apply", n=len(servers)))
        self.apply.setChecked(bool(servers))
        self.apply.setVisible(bool(servers))
        v.addWidget(self.apply)
        if servers:
            names = QLabel("  •  " + "\n  •  ".join(i.name for i in servers))
            names.setObjectName("Muted")
            v.addWidget(names)
        self.install = install
        h = QHBoxLayout()
        h.addStretch()
        c = QPushButton(tr("cancel"))
        c.clicked.connect(self.reject)
        ok = QPushButton(tr("install") if install else tr("save"))
        ok.setProperty("variant", "primary")
        ok.clicked.connect(self.validate)
        h.addWidget(c)
        h.addWidget(ok)
        v.addLayout(h)

    def validate(self):
        u = self.user.text().strip()
        if u == "postgres":
            return QMessageBox.warning(self, tr("err"), tr("no_postgres_user"))
        if not core.VALID_ROLE.match(u):
            return QMessageBox.warning(self, tr("err"), tr("pgu_bad_user"))
        if len(self.pw.text()) < 4:
            return QMessageBox.warning(self, tr("err"), tr("pgu_short"))
        if self.pw.text() != self.pw2.text():
            return QMessageBox.warning(self, tr("err"), tr("pgu_mismatch"))
        if not self.install and not self.su.text():
            return QMessageBox.warning(self, tr("err"), tr("pgu_need_su"))
        self.accept()

    def values(self):
        u, pw = self.user.text().strip(), self.pw.text()
        return (pw if self.install else self.su.text()), u, pw, self.apply.isChecked()


class ReqWorker(QThread):
    line = Signal(str)
    done = Signal(bool, str)
    progress = Signal(int, str)

    def __init__(self, what: str, pg: tuple | None = None):
        super().__init__()
        self.what, self.pg = what, pg

    def run(self):
        try:
            if self.what == "pguser":
                su, user, pw = self.pg
                pg_bin = core.find_pg_bin()
                if not pg_bin:
                    raise RuntimeError(tr("no_pgdump", p="PostgreSQL"))
                core.setup_postgres_user(pg_bin, su, user, pw, self.line.emit)
                self.done.emit(True, tr("pg_user_made", u=user))
                return
            if self.what == "postgres":
                su, user, pw = self.pg
                pg_bin = None
                # EnterpriseDB (winget's source) is blocked on some networks: fall back to GitHub binaries
                if core.has_winget() and core.edb_reachable():
                    # password goes in an option file (never on the command line, where any process can read it);
                    # pgAdmin and StackBuilder are skipped: they are most of the install time and Odoo needs neither
                    import tempfile
                    opt = os.path.join(tempfile.gettempdir(), f"om_pg_{secrets.token_hex(4)}.opt")
                    with open(opt, "w", encoding="utf-8") as f:
                        f.write(f"superpassword={su}\nserverport=5432\n")
                    try:
                        core.winget_install("postgres", self.line.emit, progress=self.progress.emit,
                                            override=f'--mode unattended --unattendedmodeui none '
                                                     f'--disable-components pgAdmin,stackbuilder '
                                                     f'--optionfile "{opt}"')
                        pg_bin = core.find_pg_bin()
                    except Exception as e:
                        self.line.emit(f"✗ {e}")
                    finally:
                        try:
                            os.remove(opt)
                        except OSError:
                            pass
                else:
                    self.line.emit(tr("edb_blocked"))
                if not (pg_bin and core.postgres_running()):
                    pg_bin = core.install_postgres_portable(su, self.line.emit, progress=self.progress.emit)
                core.setup_postgres_user(pg_bin, su, user, pw, self.line.emit)
            else:
                core.winget_install(self.what, self.line.emit, progress=self.progress.emit)
            self.done.emit(True, tr("installed_ok", n=self.what))
        except Exception as e:
            self.done.emit(False, str(e))


class NewServerWizard(QDialog):
    def __init__(self, parent, used_ports: set[int], defaults: dict, t: dict | None = None):
        super().__init__(parent)
        t = t or PALETTES["light"]
        self.setWindowTitle(tr("wiz_title"))
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.setMinimumSize(520, 420)
        fit_to_screen(self, 820, 760)
        self.result_instance: Instance | None = None
        self.worker: SetupWorker | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(dialog_header(tr("wiz_title"), tr("wiz_sub"), "server", t))

        # ---- requirements
        g0 = QGroupBox(tr("step_req"))
        rg = QGridLayout(g0)
        rg.setHorizontalSpacing(10)
        self.req_rows = {}
        names = {"git": "Git", "python": "Python 3.10 – 3.13", "postgres": "PostgreSQL"}
        urls = {"git": core.GIT_URL, "python": core.PY_URL, "postgres": core.PG_URL}
        for r, k in enumerate(("git", "python", "postgres")):
            st = QLabel()
            nm = QLabel(names[k])
            nm.setMinimumWidth(130)
            info = QLabel()
            info.setObjectName("Muted")
            info.setWordWrap(True)
            info.setLayoutDirection(Qt.LeftToRight)
            ib = QPushButton(tr("install"))
            ib.setProperty("variant", "primary")
            ib.clicked.connect(lambda _=False, k=k: self.install_req(
                "pguser" if (k == "postgres" and self.req.get("postgres")) else k))
            link = QLabel(f'<a href="{urls[k]}">{tr("download_page")}</a>')
            link.setOpenExternalLinks(True)
            for c, w in enumerate((st, nm, info, ib, link)):
                rg.addWidget(w, r, c)
            self.req_rows[k] = (st, info, ib)
        rg.setColumnStretch(2, 1)
        rb = QPushButton(tr("recheck"))
        rb.clicked.connect(lambda: self.check_reqs_async())
        rg.addWidget(rb, 3, 3, 1, 2)
        self.req_note = QLabel()
        self.req_note.setWordWrap(True)
        rg.addWidget(self.req_note, 3, 0, 1, 3)
        # live progress while a requirement installs
        from PySide6.QtWidgets import QProgressBar
        from PySide6.QtCore import QTimer
        self.req_bar = QProgressBar()
        self.req_bar.setRange(0, 0)          # busy animation
        self.req_bar.setTextVisible(False)
        self.req_bar.setFixedHeight(8)
        self.req_bar.setStyleSheet(f"QProgressBar{{border:0;border-radius:3px;background:{t['primary_soft']};}}"
                                   f"QProgressBar::chunk{{border-radius:3px;background:{t['primary']};}}")
        self.req_status = QLabel()
        self.req_status.setWordWrap(True)
        self.req_status.setStyleSheet(f"color:{t['primary']}; font-weight:600;")
        rg.addWidget(self.req_status, 4, 0, 1, 5)
        rg.addWidget(self.req_bar, 5, 0, 1, 5)
        self.req_bar.hide()
        self.req_status.hide()
        self.req_tick = QTimer(self, interval=1000, timeout=self._tick)
        self.req_started = 0.0
        self.req_what = ""
        self.req_last = ""
        self.req = {}
        self.req_worker = None

        # ---- source
        g1 = QGroupBox(tr("step_source"))
        f = QFormLayout(g1)
        f.setSpacing(10)
        self.name = QLineEdit("odoo19")
        self.branch = QComboBox()
        self.branch.setEditable(True)
        self.branch.addItems(["19.0", "18.0", "17.0", "16.0", "master"])
        self.base = QLineEdit(r"C:\Odoo\odoo19")
        self.name.textChanged.connect(lambda s: self.base.setText(rf"C:\Odoo\{s}"))
        self.clone = QCheckBox(tr("clone"))
        self.clone.setChecked(True)
        self.src = QLineEdit()
        self.src_row = path_row(self.src, "dir")
        self.src_row.setEnabled(False)
        self.clone.toggled.connect(lambda v: self.src_row.setEnabled(not v))
        self.edition = QComboBox()
        self.edition.addItem("Community", "community")
        self.edition.addItem("Enterprise", "enterprise")
        self.ent_git = QLineEdit(ENT_GIT)
        self.ent_git.setLayoutDirection(Qt.LeftToRight)
        self.ent_src = QLineEdit()
        self.ent_src.setPlaceholderText(tr("ent_src_hint"))
        self.ent_src_row = path_row(self.ent_src, "dir")
        self.ent_note = QLabel(tr("ent_note"))
        self.ent_note.setObjectName("Muted")
        self.ent_note.setWordWrap(True)
        f.addRow(tr("server_name"), self.name)
        f.addRow(tr("edition"), self.edition)
        f.addRow(tr("ent_git"), self.ent_git)
        f.addRow(tr("ent_folder"), self.ent_src_row)
        f.addRow("", self.ent_note)
        ent_rows = [self.ent_git, self.ent_src_row, self.ent_note]

        def on_ed(_=None):
            on = self.edition.currentData() == "enterprise"
            for w in ent_rows:
                f.setRowVisible(w, on)
        self.edition.currentIndexChanged.connect(on_ed)
        on_ed()
        f.addRow(tr("odoo_version"), self.branch)
        f.addRow(tr("server_folder"), path_row(self.base, "dir"))
        f.addRow("", self.clone)
        f.addRow(tr("existing_src"), self.src_row)

        # ---- environment
        g2 = QGroupBox(tr("step_env"))
        f2 = QFormLayout(g2)
        f2.setSpacing(10)
        self.python = QComboBox()
        self.python.setEditable(True)
        # filled by the background requirements check (keeps the dialog opening instantly)
        self.python.setLayoutDirection(Qt.LeftToRight)
        self.python.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.python.setMinimumContentsLength(12)
        pv = QPushButton(tr("check_ver"))
        pv.clicked.connect(self.check_py)
        prow = QWidget()
        ph = QHBoxLayout(prow)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.addWidget(self.python, 1)
        ph.addWidget(pv)
        self.venv = QCheckBox(tr("make_venv"))
        self.venv.setChecked(True)
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(find_free_port(8069, used_ports | {p + 3 for p in used_ports}))
        f2.addRow(tr("python"), prow)
        f2.addRow("", self.venv)
        f2.addRow(tr("http_port"), self.port)

        # ---- database
        g3 = QGroupBox(tr("step_db") + " (PostgreSQL)")
        gl = QGridLayout(g3)
        gl.setSpacing(10)
        self.db_host = QLineEdit(defaults.get("db_host", "localhost"))
        self.db_port = QLineEdit(str(defaults.get("db_port", "5432")))
        self.db_user = QLineEdit(defaults.get("db_user", "odoo"))
        self.db_pass = QLineEdit(defaults.get("db_password", ""))
        self.db_pass.setEchoMode(QLineEdit.Password)
        for n, (lbl, w) in enumerate([("Host", self.db_host), ("Port", self.db_port),
                                      ("User", self.db_user), ("Password", self.db_pass)]):
            gl.addWidget(QLabel(lbl), n // 2, (n % 2) * 2)
            gl.addWidget(w, n // 2, (n % 2) * 2 + 1)

        # form inside a scroll area so the dialog can shrink on small screens
        body = QWidget()
        body.setObjectName("ScrollBody")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 6, 0)
        bl.setSpacing(12)
        for g in (g0, g1, g2, g3):
            bl.addWidget(g)
        bl.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("Scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(body)

        logw = QWidget()
        lv = QVBoxLayout(logw)
        lv.setContentsMargins(0, 6, 0, 0)
        pl = QLabel(tr("progress").upper())
        pl.setObjectName("SectionTitle")
        lv.addWidget(pl)
        self.out = QPlainTextEdit()
        self.out.setObjectName("LogView")
        self.out.setReadOnly(True)
        self.out.setMaximumBlockCount(3000)
        self.out.setLayoutDirection(Qt.LeftToRight)
        self.out.setMinimumHeight(70)
        lv.addWidget(self.out)

        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        split.addWidget(scroll)
        split.addWidget(logw)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)

        h = QHBoxLayout()
        h.addStretch()
        self.cancel_btn = QPushButton(tr("cancel"))
        self.cancel_btn.clicked.connect(self.on_cancel)
        self.go = QPushButton(tr("begin_setup"))
        self.go.setProperty("variant", "primary")
        self.go.setIcon(icon("download", t["on_primary"]))
        self.go.setMinimumHeight(38)
        self.go.clicked.connect(self.start)
        h.addWidget(self.cancel_btn)
        h.addWidget(self.go)
        lay.addLayout(h)
        self.branch.currentTextChanged.connect(lambda *_: self.check_reqs_async())
        for st, info, ib in self.req_rows.values():
            st.setText("…")
            info.setText(tr("req_checking"))
            ib.hide()
        self.req_note.setText(tr("req_checking"))
        self._req_threads = []
        from PySide6.QtCore import QTimer as _QT
        _QT.singleShot(0, self.check_reqs_async)

    # ---- requirements
    def check_reqs_async(self):
        """Run the (slow) requirement probes off the UI thread, then refresh the panel."""
        branch = self.branch.currentText().strip()

        class _Probe(QThread):
            ready = Signal(dict)

            def run(self):
                self.ready.emit(core.check_requirements(branch))
        th = _Probe(self)
        th.ready.connect(self.check_reqs)
        th.finished.connect(lambda: self._req_threads.remove(th) if th in self._req_threads else None)
        self._req_threads.append(th)
        th.start()

    def check_reqs(self, data: dict | None = None):
        self.req = data if isinstance(data, dict) else core.check_requirements(self.branch.currentText().strip())
        for exe in self.req.get("pythons", []):
            if self.python.findText(exe) < 0:
                self.python.addItem(exe, exe)
        ok_c, bad_c = PALETTES["light"]["success"], PALETTES["light"]["danger"]
        lo, hi = core.py_range(self.branch.currentText().strip())
        tips = {"git": self.req["git"] or "", "python": self.req["python"][0] if self.req["python"] else "",
                "postgres": self.req["pg_bin"] or ""}
        texts = {
            "git": tr("req_installed") if self.req["git"] else tr("req_missing"),
            "python": (tr("req_py_found", v=self.req["python"][1]) if self.req["python"]
                       else tr("req_py_missing", lo="%d.%d" % lo, hi="%d.%d" % hi)),
            "postgres": (tr("req_pg_ok") if self.req["postgres"] else tr("req_pg_missing")),
        }
        winget = self.req.get("winget", True)
        busy = bool(self.req_worker and self.req_worker.isRunning())
        missing = []
        for k, (st, info, ib) in self.req_rows.items():
            ok = bool(self.req[k])
            st.setText("✅" if ok else "❌")
            info.setText(texts[k])
            info.setToolTip(tips[k])
            info.setStyleSheet("" if ok else f"color:{bad_c};")
            if k == "postgres" and ok:
                ib.setText(tr("pgu_btn"))
                ib.setVisible(True)
            else:
                ib.setText(tr("install"))
                ib.setVisible(not ok and winget)
            ib.setEnabled(not busy)
            if not ok:
                missing.append(k)
        if self.req["python"]:
            exe = self.req["python"][0]
            if self.python.findText(exe) < 0:
                self.python.insertItem(0, exe, exe)
            self.python.setCurrentText(exe)
        if not missing:
            self.req_note.setText(f'<span style="color:{ok_c}">{tr("req_all_ok")}</span>')
        else:
            self.req_note.setText(tr("req_some_missing") + ("" if winget else "  " + tr("req_no_winget")))
        return missing

    def install_req(self, what: str):
        pg = None
        apply_servers = False
        servers = self._existing_servers()
        if what in ("postgres", "pguser"):
            d = PgUserDialog(self, what == "postgres", servers)
            if not d.exec():
                return
            su, user, pw, apply_servers = d.values()
            pg = (su, user, pw)
        import time as _t
        names = {"git": "Git", "python": "Python 3.12", "postgres": "PostgreSQL", "pguser": tr("pgu_short_name")}
        row = "postgres" if what == "pguser" else what
        self.req_what, self.req_last, self.req_started = names[what], "", _t.time()
        self.out.appendPlainText(tr("installing_x", n=names[what]))
        st, info, ib = self.req_rows[row]
        st.setText("⏳")
        info.setText(tr("req_installing"))
        info.setStyleSheet(f"color:{PALETTES['light']['warning']};")
        self.req_bar.show()
        self.req_status.show()
        self._tick()
        self.req_tick.start()
        self.go.setEnabled(False)
        self.req_worker = ReqWorker(what, pg)

        def on_line(s):
            self.out.appendPlainText(s)
            s = s.strip()
            if s and not s.startswith(">"):
                self.req_last = s[:90]
                self._tick()
        self.req_worker.line.connect(on_line)
        self.req_pct, self.req_phase = -1, ""
        self.req_bar.setRange(0, 0)

        def on_progress(pct, phase):
            self.req_pct, self.req_phase = pct, phase
            if self.req_bar.maximum() == 0:
                self.req_bar.setRange(0, 100)
            self.req_bar.setValue(pct)
            self._tick()
        self.req_worker.progress.connect(on_progress)

        def fin(ok, msg):
            self.req_tick.stop()
            self.req_bar.hide()
            self.req_status.hide()
            self.go.setEnabled(True)
            self.out.appendPlainText(("✓ " if ok else "✗ ") + msg)
            applied = []
            if ok and pg:
                self.db_user.setText(pg[1])
                self.db_pass.setText(pg[2])
                self.db_host.setText("localhost")
                self.db_port.setText("5432")
                if apply_servers:
                    applied = self._apply_to_servers(servers, pg[1], pg[2])
            if ok and what == "python":
                for exe in find_pythons():
                    if self.python.findText(exe) < 0:
                        self.python.addItem(exe, exe)
            self.req_worker = None
            self.check_reqs()
            if ok and pg:
                QMessageBox.information(self, "PostgreSQL", tr("pgu_done", u=pg[1])
                                        + (("\n\n" + tr("pgu_applied", n="، ".join(applied) if self.layoutDirection() == Qt.RightToLeft else ", ".join(applied))) if applied else ""))
            elif ok:
                QMessageBox.information(self, tr("step_req"), tr("install_done_msg", n=names[what]))
            else:
                QMessageBox.warning(self, tr("err"), tr("install_fail_msg", n=names[what], e=msg))
        self.req_worker.done.connect(fin)
        self.req_worker.start()
        self.check_reqs()

    def _existing_servers(self):
        reg = getattr(self.parent(), "reg", None)
        return [i for i in (reg.instances if reg else []) if i.conf_path and os.path.exists(i.conf_path)]

    def _apply_to_servers(self, servers, user, pw):
        """Write the new database user into every server's odoo.conf and restart the running ones."""
        done = []
        main = self.parent()
        for i in servers:
            try:
                core.set_conf_values(i.conf_path, {"db_host": "localhost", "db_port": "5432",
                                                   "db_user": user, "db_password": pw})
                done.append(i.name)
                self.out.appendPlainText(tr("pgu_conf_updated", n=i.name))
                if main is not None and hasattr(main, "control") and i.status() in ("running", "starting"):
                    main.control("restart", i)
            except Exception as e:
                self.out.appendPlainText(f"✗ {i.name}: {e}")
        return done

    def _tick(self):
        import time as _t
        sec = int(_t.time() - self.req_started)
        pct = getattr(self, "req_pct", -1)
        txt = tr("req_progress", n=self.req_what, t=f"{sec // 60}:{sec % 60:02d}")
        if pct >= 0:
            txt = f"{pct}% · {getattr(self, 'req_phase', '')} — " + txt
        if self.req_last:
            txt += "\n" + self.req_last
        self.req_status.setText(txt)

    def check_py(self):
        v = python_version(self.python.currentText())
        hint = ""
        if self.branch.currentText().startswith("19") and not any(x in v for x in ("3.10", "3.11", "3.12", "3.13")):
            hint = tr("py_hint")
        QMessageBox.information(self, tr("python"), v + hint)

    def start(self):
        if not self.name.text().strip() or not self.base.text().strip():
            return QMessageBox.warning(self, tr("err"), tr("need_name_folder"))
        missing = self.check_reqs()
        need = [k for k in missing if (k == "git" and (self.clone.isChecked() or
                                                       self.edition.currentData() == "enterprise"))
                or (k == "python" and self.venv.isChecked() and not self.python.currentText().strip())]
        if "python" in missing and self.venv.isChecked():
            v = core.py_tuple(self.python.currentText().strip()) if self.python.currentText().strip() else None
            lo, hi = core.py_range(self.branch.currentText().strip())
            if not (v and lo <= v <= hi):
                need.append("python")
        if need:
            return QMessageBox.warning(self, tr("err"), tr("req_block", n=", ".join(sorted(set(need)))))
        if "postgres" in missing and QMessageBox.question(self, "PostgreSQL", tr("req_pg_continue")) != QMessageBox.Yes:
            return
        if self.db_user.text().strip().lower() == "postgres":
            return QMessageBox.warning(self, tr("err"), tr("no_postgres_user"))
        cfg = dict(name=self.name.text().strip(), branch=self.branch.currentText().strip(),
                   base=self.base.text().strip(), clone=self.clone.isChecked(), src=self.src.text().strip(),
                   python=self.python.currentText().strip(), venv=self.venv.isChecked(),
                   port=self.port.value(), db_host=self.db_host.text().strip(),
                   db_port=self.db_port.text().strip(), db_user=self.db_user.text().strip(),
                   db_password=self.db_pass.text(),
                   edition=self.edition.currentData(), ent_git=self.ent_git.text().strip(),
                   ent_src=self.ent_src.text().strip(), admin_passwd=secrets.token_urlsafe(12))
        self.go.setEnabled(False)
        self.worker = SetupWorker(cfg)
        self.worker.line.connect(self.out.appendPlainText)
        self.worker.done.connect(self.finished_setup)
        self.worker.start()

    def finished_setup(self, ok: bool, msg: str):
        self.out.appendPlainText(("\n✓ " if ok else "\n✗ ") + msg)
        if ok:
            self.result_instance = self.worker.result
            QMessageBox.information(self, tr("wiz_title"), msg + tr("setup_ok_note"))
            self.accept()
        else:
            self.go.setEnabled(True)

    def on_cancel(self):
        if self.req_worker and self.req_worker.isRunning():
            return QMessageBox.information(self, tr("wiz_title"), tr("wait_install"))
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
        self.reject()


class InstanceDialog(QDialog):
    """Add an existing server / edit an instance."""

    def __init__(self, parent, inst: Instance | None = None, t: dict | None = None):
        super().__init__(parent)
        t = t or PALETTES["light"]
        self.setWindowTitle(tr("server_details"))
        self.setMinimumWidth(460)
        fit_to_screen(self, 680, 520)
        self.inst = inst or Instance(name="")
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 20)
        v.setSpacing(14)
        v.addWidget(dialog_header(tr("server_details"), "", "edit" if inst else "import", t))
        box = QFrame()
        box.setObjectName("Card")
        f = QFormLayout(box)
        f.setContentsMargins(16, 16, 16, 16)
        f.setSpacing(10)
        self.name = QLineEdit(self.inst.name)
        self.kind = QComboBox()
        self.kind.addItem(tr("kind_bin"), "bin")
        self.kind.addItem(tr("kind_service"), "service")
        self.kind.setCurrentIndex(0 if self.inst.kind == "bin" else 1)
        self.service = QLineEdit(self.inst.service_name)
        self.python = QLineEdit(self.inst.python_exe)
        self.odoo_bin = QLineEdit(self.inst.odoo_bin)
        self.conf = QLineEdit(self.inst.conf_path)
        self.autostart = QCheckBox(tr("autostart_short"))
        self.autostart.setChecked(self.inst.autostart)
        f.addRow(tr("name"), self.name)
        f.addRow(tr("type"), self.kind)
        f.addRow(tr("service_name"), self.service)
        f.addRow("Python", path_row(self.python, "file", "python.exe (*.exe)"))
        f.addRow("odoo-bin", path_row(self.odoo_bin, "file", "odoo-bin (odoo-bin*)"))
        f.addRow("odoo.conf", path_row(self.conf, "file", "Config (*.conf *.cfg);;All (*)"))
        f.addRow("", self.autostart)
        v.addWidget(box)
        h = QHBoxLayout()
        h.addStretch()
        c = QPushButton(tr("cancel"))
        c.clicked.connect(self.reject)
        s = QPushButton(tr("save"))
        s.setProperty("variant", "primary")
        s.clicked.connect(self.save)
        h.addWidget(c)
        h.addWidget(s)
        v.addLayout(h)
        self.kind.currentIndexChanged.connect(self._toggle)
        self._toggle()

    def _toggle(self):
        self.service.setEnabled(self.kind.currentData() == "service")

    def save(self):
        if not self.name.text().strip():
            return QMessageBox.warning(self, tr("err"), tr("need_name"))
        i = self.inst
        i.name = self.name.text().strip()
        i.kind = self.kind.currentData()
        i.service_name = self.service.text().strip()
        i.python_exe = self.python.text().strip()
        i.odoo_bin = self.odoo_bin.text().strip()
        i.conf_path = self.conf.text().strip()
        i.autostart = self.autostart.isChecked()
        self.accept()
