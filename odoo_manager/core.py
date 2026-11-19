"""Core logic: instance registry, process/service control, ports, conf files."""
from __future__ import annotations

import configparser
import ctypes
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import psutil

from .i18n import tr

APP_NAME = "OdooManager"
APP_VERSION = "1.1.1"
APP_AUTHOR = "Hossam Ramadan"
APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
LOG_DIR = APP_DIR / "logs"
STATE_FILE = APP_DIR / "instances.json"
SETTINGS_FILE = APP_DIR / "settings.json"

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200

for _d in (APP_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- helpers
def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_elevated(exe: str, args: str, wait: bool = True) -> bool:
    """Run a command with UAC elevation (hidden window). Returns True if launched."""
    if is_admin():
        r = subprocess.run(f'"{exe}" {args}', shell=True, creationflags=CREATE_NO_WINDOW,
                           capture_output=True, text=True)
        return r.returncode == 0
    # PowerShell Start-Process lets us wait for the elevated child.
    ps = (f"Start-Process -FilePath '{exe}' -ArgumentList '{args.replace(chr(39), chr(39) * 2)}' "
          f"-Verb RunAs -WindowStyle Hidden{' -Wait' if wait else ''}")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       creationflags=CREATE_NO_WINDOW, capture_output=True, text=True)
    return r.returncode == 0


def port_owner(port: int) -> psutil.Process | None | bool:
    """Return the Process listening on port, True if listening by unknown pid, None if free."""
    try:
        conns = psutil.net_connections(kind="tcp")
    except Exception:
        conns = []
    for c in conns:
        if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port:
            if c.pid:
                try:
                    return psutil.Process(c.pid)
                except psutil.Error:
                    return True
            return True
    return None


def listening_ports() -> set[int]:
    try:
        return {c.laddr.port for c in psutil.net_connections(kind="tcp")
                if c.status == psutil.CONN_LISTEN and c.laddr}
    except Exception:
        return set()


def find_free_port(start: int = 8069, exclude: set[int] | None = None) -> int:
    used = listening_ports() | (exclude or set())
    p = start
    while p in used:
        p += 1
    return p


def find_pythons() -> list[str]:
    """Python interpreters known to the py launcher + PATH."""
    found: list[str] = []
    try:
        out = subprocess.run(["py", "-0p"], capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW).stdout
        for line in out.splitlines():
            m = re.search(r"([A-Za-z]:\\.*python(w)?\.exe)", line, re.I)
            if m:
                found.append(m.group(1).strip())
    except Exception:
        pass
    w = shutil.which("python")
    if w and "WindowsApps" not in w:
        found.append(w)
    for pat in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python3*", "python.exe"),
                r"C:\Program Files\Python3*\python.exe", r"C:\Python3*\python.exe"):
        found += sorted(glob.glob(pat), reverse=True)
    found += glob.glob(r"C:\Program Files\Odoo*\python\python.exe")
    seen, res = set(), []
    for f in found:
        k = os.path.normcase(f)
        if k not in seen and os.path.exists(f):
            seen.add(k)
            res.append(f)
    return res


def python_version(exe: str) -> str:
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10,
                           creationflags=CREATE_NO_WINDOW)
        return (r.stdout or r.stderr).strip()
    except Exception:
        return "?"


def find_pg_bin() -> str:
    cands = sorted(glob.glob(r"C:\Program Files\PostgreSQL\*\bin"), reverse=True)
    cands += glob.glob(r"C:\Program Files\Odoo*\PostgreSQL\bin")
    for c in cands:
        if os.path.exists(os.path.join(c, "pg_dump.exe")):
            return c
    w = shutil.which("pg_dump")
    return os.path.dirname(w) if w else ""


# --------------------------------------------------------------------------- settings
DEFAULT_SETTINGS = {
    "pg_bin": "",
    "backup_dir": str(Path.home() / "OdooBackups"),
    "minimize_to_tray": True,
    "language": "ar",
    "theme": "light",
    "start_with_windows": False,
    "auto_backup": False,
    "auto_backup_keep": 7,
    "auto_backup_last": {},
    "notify_stop": True,
}


def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    if SETTINGS_FILE.exists():
        try:
            s.update(json.loads(SETTINGS_FILE.read_text("utf-8")))
        except Exception:
            pass
    s["pg_bin"] = resolve_pg_bin(s.get("pg_bin", ""))
    return s


def resolve_pg_bin(current: str) -> str:
    """Keep the configured folder while it really holds pg_dump; otherwise look again
    (PostgreSQL may have been installed, moved or removed since the path was saved)."""
    if current and os.path.exists(os.path.join(current, "pg_dump.exe")):
        return current
    return find_pg_bin() or current


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def save_settings(s: dict) -> None:
    _atomic_write(SETTINGS_FILE, json.dumps(s, indent=2, ensure_ascii=False))


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    script = Path(__file__).resolve().parent.parent / "app.py"
    return f'"{exe}" "{script}" --tray'


def set_start_with_windows(enable: bool) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enable:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


# --------------------------------------------------------------------------- conf
def read_conf(path: str) -> dict:
    cp = configparser.ConfigParser(interpolation=None)
    try:
        cp.read(path, encoding="utf-8-sig")
    except Exception:
        try:
            cp.read(path, encoding="cp1252")
        except Exception:
            return {}
    return dict(cp["options"]) if cp.has_section("options") else {}


def conf_value(conf: dict, key: str, default=None):
    v = conf.get(key)
    if v is None or v.strip() in ("", "False", "None"):
        return default
    return v.strip()


# --------------------------------------------------------------------------- instance
@dataclass
class Instance:
    name: str
    kind: str = "bin"               # "bin" (odoo-bin) | "service" (Windows service)
    conf_path: str = ""
    odoo_bin: str = ""
    python_exe: str = ""
    service_name: str = ""
    autostart: bool = False
    pid: int | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    # ---- conf derived
    @property
    def conf(self) -> dict:
        return read_conf(self.conf_path) if self.conf_path and os.path.exists(self.conf_path) else {}

    @property
    def port(self) -> int:
        c = self.conf
        try:
            return int(conf_value(c, "http_port") or conf_value(c, "xmlrpc_port") or 8069)
        except ValueError:
            return 8069

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}"

    @property
    def log_path(self) -> str | None:
        lf = conf_value(self.conf, "logfile")
        if lf:
            return lf
        if self.kind == "bin":
            return str(LOG_DIR / f"{self.id}.log")
        return None

    @property
    def data_dir(self) -> str:
        d = conf_value(self.conf, "data_dir")
        if d:
            return d
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "OpenERP S.A", "Odoo")

    # ---- process lookup
    def _matches(self, p: psutil.Process) -> bool:
        try:
            cmd = " ".join(p.cmdline()).lower()
        except psutil.Error:
            return False
        return ("odoo-bin" in cmd or "odoo" in cmd) and \
            os.path.normcase(self.conf_path).lower() in os.path.normcase(cmd)

    def process(self) -> psutil.Process | None:
        if self.pid:
            try:
                p = psutil.Process(self.pid)
                if p.is_running() and p.status() != psutil.STATUS_ZOMBIE and self._matches(p):
                    return p
            except psutil.Error:
                pass
            self.pid = None
        if not self.conf_path:
            return None
        for p in psutil.process_iter(["name"]):
            if (p.info["name"] or "").lower().startswith("python") and self._matches(p):
                # take the top-most matching python (parent not a match)
                try:
                    par = p.parent()
                    if par and self._matches(par):
                        continue
                except psutil.Error:
                    pass
                self.pid = p.pid
                return p
        return None

    # ---- status
    def status(self) -> str:
        """running | stopped | starting | stopping | missing"""
        if self.kind == "service":
            try:
                s = psutil.win_service_get(self.service_name).status()
            except Exception:
                return "missing"
            return {"running": "running", "stopped": "stopped",
                    "start_pending": "starting", "stop_pending": "stopping"}.get(s, s)
        return "running" if self.process() else "stopped"

    def service_start_type(self) -> str:
        try:
            return psutil.win_service_get(self.service_name).start_type()
        except Exception:
            return "?"

    # ---- control
    def start(self) -> None:
        if self.kind == "service":
            if not run_elevated("sc.exe", f'start "{self.service_name}"'):
                raise RuntimeError(tr("err_svc_start"))
            return
        if self.process():
            return
        owner = port_owner(self.port)
        if owner:
            who = f"{owner.name()} (PID {owner.pid})" if isinstance(owner, psutil.Process) else tr("other_prog")
            raise RuntimeError(tr("err_port", p=self.port, w=who))
        for f, label in ((self.python_exe, "Python"), (self.odoo_bin, "odoo-bin"), (self.conf_path, "odoo.conf")):
            if not f or not os.path.exists(f):
                raise RuntimeError(tr("err_file", l=label, f=f))
        log = self.log_path
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        out = open(log, "ab")
        out.write(f"\n===== OdooManager start {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n".encode())
        out.flush()
        p = subprocess.Popen([self.python_exe, self.odoo_bin, "-c", self.conf_path],
                             cwd=os.path.dirname(self.odoo_bin), stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL,
                             creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP)
        out.close()
        self.pid = p.pid

    def stop(self) -> None:
        if self.kind == "service":
            if not run_elevated("sc.exe", f'stop "{self.service_name}"'):
                raise RuntimeError(tr("err_svc_stop"))
            return
        p = self.process()
        if not p:
            return
        procs = [p] + p.children(recursive=True)
        for c in procs:
            try:
                c.terminate()
            except psutil.Error:
                pass
        _, alive = psutil.wait_procs(procs, timeout=8)
        for c in alive:
            try:
                c.kill()
            except psutil.Error:
                pass
        self.pid = None

    def restart(self) -> None:
        if self.kind == "service":
            n = self.service_name
            if not run_elevated("cmd.exe", f'/c net stop "{n}" & net start "{n}"'):
                raise RuntimeError(tr("err_svc_restart"))
            return
        self.stop()
        for _ in range(20):
            if not port_owner(self.port):
                break
            time.sleep(0.5)
        self.start()

    def set_service_autostart(self, enable: bool) -> None:
        mode = "auto" if enable else "demand"
        if not run_elevated("sc.exe", f'config "{self.service_name}" start= {mode}'):
            raise RuntimeError(tr("err_svc_cfg"))


# --------------------------------------------------------------------------- registry
class Registry:
    def __init__(self):
        self.instances: list[Instance] = []
        self.load()

    def load(self):
        self.instances = []
        if not STATE_FILE.exists():
            return
        try:
            data = json.loads(STATE_FILE.read_text("utf-8"))
        except Exception:
            # keep the unreadable file aside instead of overwriting it with an empty list
            try:
                shutil.copy2(STATE_FILE, STATE_FILE.with_suffix(".broken.json"))
            except OSError:
                pass
            return
        fields = set(Instance.__dataclass_fields__)
        for d in data if isinstance(data, list) else []:
            try:
                self.instances.append(Instance(**{k: v for k, v in d.items() if k in fields}))
            except Exception:
                continue

    def save(self):
        _atomic_write(STATE_FILE, json.dumps([asdict(i) for i in self.instances], indent=2,
                                             ensure_ascii=False))

    def add(self, inst: Instance):
        self.instances.append(inst)
        self.save()

    def remove(self, inst: Instance):
        self.instances = [i for i in self.instances if i.id != inst.id]
        self.save()

    def get(self, iid: str) -> Instance | None:
        return next((i for i in self.instances if i.id == iid), None)

    def used_ports(self) -> set[int]:
        return {i.port for i in self.instances}


def discover_services() -> list[Instance]:
    """Find Windows services that run Odoo (e.g. the official installer, via nssm)."""
    import winreg
    res = []
    for svc in psutil.win_service_iter():
        try:
            name = svc.name()
        except Exception:
            continue
        if "odoo" not in name.lower() or "postgres" in name.lower():
            continue
        conf = odoo_bin = py = ""
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                rf"SYSTEM\CurrentControlSet\Services\{name}\Parameters") as k:
                py = winreg.QueryValueEx(k, "Application")[0]
                params = winreg.QueryValueEx(k, "AppParameters")[0]
            parts = shlex.split(params, posix=False)
            parts = [x.strip('"') for x in parts]
            for i, x in enumerate(parts):
                if x.endswith("odoo-bin"):
                    odoo_bin = x
                if x in ("-c", "--config") and i + 1 < len(parts):
                    conf = parts[i + 1]
                elif x.startswith("--config="):
                    conf = x.split("=", 1)[1]
        except OSError:
            try:
                bp = svc.binpath()
                m = re.search(r'-c\s+"?([^"]+\.conf)', bp)
                conf = m.group(1) if m else ""
            except Exception:
                pass
        res.append(Instance(name=name, kind="service", service_name=name, conf_path=conf,
                            odoo_bin=odoo_bin, python_exe=py))
    return res


# --------------------------------------------------------------------------- modules
CORE_MARKERS = (os.sep + "odoo" + os.sep + "addons", os.sep + "enterprise")


def addons_paths(inst: "Instance") -> list[str]:
    raw = conf_value(inst.conf, "addons_path") or ""
    return [p.strip() for p in raw.split(",") if p.strip()]


def custom_addons_dir(inst: "Instance") -> str | None:
    """The addons folder meant for custom modules (not Odoo's own)."""
    paths = [p for p in addons_paths(inst) if os.path.isdir(p)]
    for p in paths:
        if "custom" in p.lower():
            return p
    for p in reversed(paths):
        low = os.path.normcase(p)
        if not low.endswith(CORE_MARKERS) and not os.path.isdir(os.path.join(p, "web"))                 and not os.path.isdir(os.path.join(p, "base")):
            return p
    return None


def install_module(inst: "Instance", src: str, log=print) -> list[str]:
    """Copy a module folder (or a folder of modules, or a .zip) into the custom addons dir."""
    import zipfile, tempfile
    dest = custom_addons_dir(inst)
    if not dest:
        raise RuntimeError(tr("no_custom_dir"))
    tmp = None
    if src.lower().endswith(".zip"):
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        src = tmp
    mods = []
    if os.path.exists(os.path.join(src, "__manifest__.py")):
        mods = [src]
    else:
        for root, dirs, files in os.walk(src):
            if "__manifest__.py" in files:
                mods.append(root)
                dirs[:] = []
    if not mods:
        raise RuntimeError(tr("no_manifest"))
    names = []
    for m in mods:
        n = os.path.basename(os.path.normpath(m))
        target = os.path.join(dest, n)
        if os.path.exists(target):
            shutil.rmtree(target)
        shutil.copytree(m, target)
        log(tr("mod_copied", n=n, p=dest))
        names.append(n)
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    return names


def update_module(inst: "Instance", dbname: str, modules: str, log=print, install=False) -> None:
    """Run odoo-bin -u/-i for a database without starting HTTP."""
    if not (inst.python_exe and inst.odoo_bin and os.path.exists(inst.odoo_bin)):
        raise RuntimeError(tr("no_odoo_bin", p=inst.odoo_bin or "?"))
    lf = str(LOG_DIR / f"update_{inst.id}.log")
    cmd = [inst.python_exe, inst.odoo_bin, "-c", inst.conf_path, "-d", dbname,
           "-i" if install else "-u", modules, "--stop-after-init", "--no-http", "--logfile", lf]
    log("> " + " ".join(cmd[1:]))
    try:
        os.remove(lf)
    except OSError:
        pass
    rc = subprocess.run(cmd, creationflags=CREATE_NO_WINDOW, cwd=os.path.dirname(inst.odoo_bin)).returncode
    out = open(lf, encoding="utf-8", errors="replace").read() if os.path.exists(lf) else ""
    errs = [l for l in out.splitlines() if " ERROR " in l or " CRITICAL " in l]
    for l in errs[-8:]:
        log(l)
    if rc != 0 or errs:
        raise RuntimeError(tr("update_failed", p=lf))


def write_conf_text(path: str, text: str) -> None:
    """Write a conf file; if it is protected (e.g. Program Files) copy it in with UAC."""
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return
    except PermissionError:
        pass
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), f"om_conf_{uuid.uuid4().hex[:6]}.conf")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    run_elevated("cmd.exe", f'/c copy /Y "{tmp}" "{path}"')
    try:
        ok = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n") == text
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if not ok:
        raise RuntimeError(tr("no_perm"))


def suggest_custom_dir(inst: "Instance") -> str:
    base = os.path.dirname(inst.conf_path) if inst.conf_path else str(Path.home())
    if "program files" in base.lower() or not os.access(base, os.W_OK):
        return str(Path.home() / "Odoo" / "custom_addons")
    return os.path.join(base, "custom_addons")


def add_custom_dir(inst: "Instance", folder: str) -> None:
    """Create folder and append it to addons_path in the instance conf."""
    os.makedirs(folder, exist_ok=True)
    text = open(inst.conf_path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    m = re.search(r"^addons_path\s*=\s*(.*)$", text, re.M)
    if m:
        paths = [p.strip() for p in m.group(1).split(",") if p.strip()]
        if any(os.path.normcase(p) == os.path.normcase(folder) for p in paths):
            return
        line = "addons_path = " + ",".join(paths + [folder])
        text = text[:m.start()] + line + text[m.end():]
    else:
        # no addons_path yet: keep Odoo's own default folders before the new one
        root = os.path.dirname(inst.odoo_bin) if inst.odoo_bin else ""
        defaults = [p for p in (os.path.join(root, "odoo", "addons"), os.path.join(root, "addons"))
                    if root and os.path.isdir(p)]
        value = ",".join(defaults + [folder])
        text = re.sub(r"^\[options\]\s*$", lambda _m: "[options]\naddons_path = " + value, text, count=1, flags=re.M)
    write_conf_text(inst.conf_path, text)


# --------------------------------------------------------------------------- requirements
GIT_URL = "https://git-scm.com/download/win"
PY_URL = "https://www.python.org/downloads/release/python-3129/"
PG_URL = "https://www.enterprisedb.com/downloads/postgres-postgresql-downloads"
WINGET_IDS = {"git": "Git.Git", "python": "Python.Python.3.12", "postgres": "PostgreSQL.PostgreSQL.16"}


def find_git() -> str | None:
    w = shutil.which("git")
    if w:
        return w
    for c in (r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files (x86)\Git\cmd\git.exe",
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Git", "cmd", "git.exe")):
        if os.path.exists(c):
            return c
    return None


def py_tuple(exe: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\.(\d+)", python_version(exe))
    return (int(m.group(1)), int(m.group(2))) if m else None


def py_range(branch: str) -> tuple[tuple[int, int], tuple[int, int]]:
    try:
        major = int(branch.split(".")[0])
    except ValueError:
        major = 19
    if major >= 19:
        return (3, 10), (3, 13)
    if major >= 17:
        return (3, 10), (3, 12)
    return (3, 8), (3, 10)


def good_python(branch: str = "19.0") -> tuple[str, str] | None:
    lo, hi = py_range(branch)
    seen = set()
    for exe in find_pythons():
        key = os.path.normcase(exe)
        if key in seen:
            continue
        seen.add(key)
        if os.sep + "odoo" in key:   # Python bundled with an Odoo install: breaks if that Odoo is removed
            continue
        v = py_tuple(exe)
        if v and lo <= v <= hi:
            return exe, "%d.%d" % v
    return None


def postgres_running(port: int = 5432, host: str = "localhost") -> bool:
    """A TCP connect works without admin rights (listing connections may not)."""
    import socket
    for h in ("127.0.0.1", "::1") if host in ("localhost", "127.0.0.1") else (host,):
        fam = socket.AF_INET6 if ":" in h else socket.AF_INET
        s = socket.socket(fam, socket.SOCK_STREAM)
        s.settimeout(0.4)
        try:
            if s.connect_ex((h, port)) == 0:
                return True
        except OSError:
            pass
        finally:
            s.close()
    return False


def check_requirements(branch: str = "19.0") -> dict:
    return {"git": find_git(), "python": good_python(branch),
            "postgres": postgres_running(), "pg_bin": find_pg_bin(),
            "pythons": find_pythons(), "winget": has_winget()}


def has_winget() -> bool:
    return shutil.which("winget") is not None


# where each package lands and roughly how many files it has (for the install-phase percentage)
INSTALL_TARGETS = {
    "git": (r"C:\Program Files\Git", 2700),
    "python": (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python312"), 4000),
    "postgres": (r"C:\Program Files\PostgreSQL\16", 4200),
}


def _count_files(root: str) -> int:
    n = 0
    for _r, _d, files in os.walk(root):
        n += len(files)
    return n


def _install_watcher(what: str, progress, stop):
    """While the silent installer runs, map copied-file count to 50..99 %."""
    root, expected = INSTALL_TARGETS.get(what, ("", 0))
    if not (root and expected and progress):
        return
    base = _count_files(root) if os.path.isdir(root) else 0
    while not stop.is_set():
        if os.path.isdir(root):
            done = max(0, _count_files(root) - base)
            progress(min(99, 50 + done * 49 // expected), tr("phase_install"))
        stop.wait(1.5)


def _verify_installed(what: str) -> bool:
    """Look for the real thing on disk â€” winget's own records can be stale."""
    if what == "git":
        return bool(find_git())
    if what == "python":
        return bool(good_python("19.0"))
    return True        # postgres: the caller checks the service / port itself


def winget_install(what: str, log=print, override: str | None = None, progress=None) -> None:
    """Install with winget, then make sure it is really there.
    winget may answer "already installed" (0x8A15002B) for something that was removed
    but is still registered in Windows; then reinstall with --force."""
    rc = _winget_run(what, log, override, progress)
    ok_codes = (0, -1978335189, 2316632107)
    if rc not in ok_codes:
        raise RuntimeError(tr("install_failed", n=what, c=rc))
    if not _verify_installed(what):
        log(tr("stale_install"))
        rc = _winget_run(what, log, override, progress, force=True)
        if rc not in ok_codes or not _verify_installed(what):
            raise RuntimeError(tr("install_not_found", n=what))
    if what == "git":
        g = find_git()
        if g:
            os.environ["PATH"] = os.path.dirname(g) + os.pathsep + os.environ.get("PATH", "")


def _winget_run(what: str, log=print, override: str | None = None, progress=None, force: bool = False) -> int:
    """progress(pct, phase) â€” download 0..50 %, install 50..99 % (file count), 100 when done."""
    import threading
    cmd = ["winget", "install", "--id", WINGET_IDS[what], "-e", "--silent",
           "--accept-package-agreements", "--accept-source-agreements"] + (["--force"] if force else [])
    if override:
        cmd += ["--override", override]
    log("> winget install " + WINGET_IDS[what])
    if progress:
        progress(0, tr("phase_prepare"))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW)
    size_re = re.compile(r"([\d.]+)\s*(KB|MB|GB)\s*/\s*([\d.]+)\s*(KB|MB|GB)")
    unit = {"KB": 1, "MB": 1024, "GB": 1024 * 1024}
    stop = threading.Event()
    watcher = None
    buf = ""
    while True:
        ch = p.stdout.read(1)
        if not ch:
            break
        if ch not in "\r\n":
            buf += ch
            continue
        line, buf = buf.strip(), ""
        if not line:
            continue
        m = size_re.search(line)
        if m and progress:
            got = float(m.group(1)) * unit[m.group(2)]
            tot = float(m.group(3)) * unit[m.group(4)] or 1
            progress(min(50, int(got * 50 / tot)), tr("phase_download"))
            continue
        if set(line) <= set("-\\|/ â–ˆâ–’"):
            continue
        log(line)
        if progress and watcher is None and ("Starting package install" in line or "installer hash" in line):
            progress(50, tr("phase_install"))
            watcher = threading.Thread(target=_install_watcher, args=(what, progress, stop), daemon=True)
            watcher.start()
    rc = p.wait()
    stop.set()
    return rc


def setup_postgres_user(pg_bin: str, super_pw: str, user: str, pw: str, log=print, port: int = 5432) -> None:
    """Create an Odoo login role (CREATEDB) on a fresh PostgreSQL."""
    psql = os.path.join(pg_bin, "psql.exe")
    env = dict(os.environ, PGPASSWORD=super_pw)
    q = pw.replace("'", "''")
    sql = ("DO $$BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '%s') THEN "
           "CREATE ROLE \"%s\" LOGIN CREATEDB PASSWORD '%s'; "
           "ELSE ALTER ROLE \"%s\" LOGIN CREATEDB PASSWORD '%s'; END IF; END$$;"
           % (user, user, q, user, q))
    r = subprocess.run([psql, "-h", "localhost", "-p", str(port), "-U", "postgres", "-d", "postgres", "-c", sql],
                       env=env, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "psql failed")
    log(tr("pg_user_made", u=user))


# --------------------------------------------------------------------------- PostgreSQL (portable fallback)
PG_PORTABLE_VER = "16.16.0"
PG_PORTABLE_URL = ("https://github.com/theseus-rs/postgresql-binaries/releases/download/"
                   "{v}/postgresql-{v}-x86_64-pc-windows-msvc.zip")

PG_SETUP_PS1 = r"""
$ErrorActionPreference = 'Stop'
$zip = '{zip}'; $root = '{root}'; $data = Join-Path $root 'data'; $pw = '{pwfile}'
$svc = '{svc}'; $port = {port}; $done = '{done}'
try {{
  if (-not (Test-Path (Join-Path $root 'bin\pg_ctl.exe'))) {{
    $tmp = Join-Path $env:TEMP ('pgx_' + [guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
    $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Force $root | Out-Null
    Copy-Item (Join-Path $inner.FullName '*') $root -Recurse -Force
    Remove-Item $tmp -Recurse -Force
  }}
  if (-not (Test-Path (Join-Path $data 'PG_VERSION'))) {{
    & (Join-Path $root 'bin\initdb.exe') -D $data -U postgres -E UTF8 --locale=C -A scram-sha-256 --pwfile=$pw | Out-Null
    if ($LASTEXITCODE -ne 0) {{ throw "initdb failed ($LASTEXITCODE)" }}
    Add-Content (Join-Path $data 'postgresql.conf') "`nport = $port`nlisten_addresses = 'localhost'"
  }}
  icacls $data /grant '*S-1-5-20:(OI)(CI)F' /T /Q | Out-Null
  if (-not (Get-Service $svc -ErrorAction SilentlyContinue)) {{
    & (Join-Path $root 'bin\pg_ctl.exe') register -N $svc -U 'NT AUTHORITY\NetworkService' -D $data -S auto -w | Out-Null
  }}
  Start-Service $svc
  Set-Content $done 'ok'
}} catch {{ Set-Content $done ('error: ' + $_.Exception.Message) }}
"""


def edb_reachable(timeout: float = 6) -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(urllib.request.Request("https://get.enterprisedb.com/", method="HEAD"), timeout=timeout)
        return True
    except Exception as e:
        return getattr(e, "code", None) is not None   # an HTTP error still means the host answered


def install_postgres_portable(super_pw: str, log=print, port: int = 5432,
                              root: str = r"C:\Program Files\PostgreSQL\16",
                              service: str = "postgresql-x64-16", progress=None) -> str:
    """Download PostgreSQL binaries from GitHub, init a cluster and register a Windows service (UAC).
    Returns the bin folder."""
    import tempfile, urllib.request
    url = PG_PORTABLE_URL.format(v=PG_PORTABLE_VER)
    work = tempfile.mkdtemp(prefix="om_pg_")
    zp = os.path.join(work, "pg.zip")
    log(tr("pg_downloading", u="github.com"))
    with urllib.request.urlopen(url, timeout=60) as r, open(zp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got, last = 0, -1
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            pct = got * 100 // total if total else -1
            if pct >= 0 and progress:
                progress(pct * 60 // 100, tr("phase_download"))
            if pct >= 0 and pct // 20 != last:
                last = pct // 20
                log(f"  {pct}%")
    pwfile = os.path.join(work, "pw.txt")
    with open(pwfile, "w", encoding="utf-8", newline="\n") as f:
        f.write(super_pw + "\n")
    done = os.path.join(work, "done.txt")
    q = lambda p: p.replace("'", "''")
    ps1 = os.path.join(work, "setup.ps1")
    with open(ps1, "w", encoding="utf-8-sig") as f:
        f.write(PG_SETUP_PS1.format(zip=q(zp), root=q(root), pwfile=q(pwfile), svc=q(service),
                                    port=int(port), done=q(done)))
    log(tr("pg_setting_up"))
    import threading
    stop = threading.Event()

    def watch():                      # 60..95 % while files are copied, then cluster init
        while not stop.is_set():
            n = _count_files(root) if os.path.isdir(root) else 0
            if progress:
                ready = os.path.exists(os.path.join(root, "data", "PG_VERSION"))
                progress(95 if ready else min(90, 60 + n * 30 // 2998),
                         tr("phase_service") if ready else tr("phase_install"))
            stop.wait(1.5)
    threading.Thread(target=watch, daemon=True).start()
    try:
        run_elevated("powershell.exe", f'-NoProfile -ExecutionPolicy Bypass -File "{ps1}"')
        res = open(done, encoding="utf-8-sig").read().strip() if os.path.exists(done) else "error: " + tr("uac_denied")
    finally:
        stop.set()
        shutil.rmtree(work, ignore_errors=True)
    if res != "ok":
        raise RuntimeError(res.replace("error: ", "", 1))
    for _ in range(20):
        if postgres_running(port):
            break
        time.sleep(1)
    return os.path.join(root, "bin")


def set_conf_values(path: str, values: dict) -> None:
    """Set keys in an odoo.conf (replace existing lines, add missing ones under [options])."""
    text = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    for k, v in values.items():
        line = f"{k} = {v}"
        pat = re.compile(rf"^\s*{re.escape(k)}\s*=.*$", re.M)
        if pat.search(text):
            text = pat.sub(lambda _m: line, text, count=1)
            # drop accidental duplicates of the same key
            first = text.find(line) + len(line)
            text = text[:first] + pat.sub("", text[first:])
        elif re.search(r"^\[options\]\s*$", text, re.M):
            text = re.sub(r"^\[options\]\s*$", lambda _m: "[options]\n" + line, text, count=1, flags=re.M)
        else:
            text = "[options]\n" + line + "\n" + text
    text = re.sub(r"\n{3,}", "\n\n", text)
    write_conf_text(path, text)


VALID_ROLE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def check_db_login(host: str, port: str, user: str, pw: str) -> str:
    """'ok' | 'auth' (user missing or wrong password) | 'down' (server not reachable) | 'error: â€¦'"""
    import psycopg2
    try:
        con = psycopg2.connect(host=host or "localhost", port=int(port or 5432), user=user, password=pw,
                               dbname="postgres", connect_timeout=4)
        con.close()
        return "ok"
    except psycopg2.OperationalError as e:
        msg = str(e).lower()
        if "password authentication failed" in msg or "does not exist" in msg or "no password supplied" in msg:
            return "auth"
        if "could not connect" in msg or "connection refused" in msg or "timeout" in msg or "timed out" in msg:
            return "down"
        return "error: " + str(e).strip()
    except Exception as e:
        return "error: " + str(e).strip()


def is_bad_server_folder(path: str) -> bool:
    """A drive root (for example D:) or a non-empty folder that is not an earlier server of ours."""
    p = Path(path)
    if len(p.parts) <= 1 or str(p).rstrip("\\/").endswith(":"):
        return True
    if p.is_dir() and any(p.iterdir()):
        mine = (p / "odoo.conf").exists() or (p / "src" / "odoo-bin").exists()
        return not mine
    return False
