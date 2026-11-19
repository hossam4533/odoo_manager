"""Capture English screenshots of every screen for the user guide."""
import os, sys
sys.path.insert(0, r"C:\OdooManager")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
os.makedirs(OUT, exist_ok=True)
import odoo_manager.core as core
core.STATE_FILE = core.APP_DIR / "shot_instances.json"
core.SETTINGS_FILE = core.APP_DIR / "shot_settings.json"
core.STATE_FILE.write_text((core.APP_DIR / "instances.json").read_text("utf-8"), "utf-8")
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
from odoo_manager import gui, wizard

plan = [("light", "main"), ("dark", "main_dark")]
st = {"i": 0}


def save(w, name):
    w.grab().save(os.path.join(OUT, name + ".png"))


def run():
    if st["i"] >= len(plan):
        core.STATE_FILE.unlink(); core.SETTINGS_FILE.unlink(); app.quit(); return
    theme, tag = plan[st["i"]]
    core.save_settings(dict(core.DEFAULT_SETTINGS, language="en", theme=theme, pg_bin=core.find_pg_bin(),
                            welcome_done=True, backup_dir=r"C:\Users\Areen\OdooBackups"))
    w = gui.MainWindow()
    w.resize(1320, 800)

    def tabs(k):
        if k < 4:
            w.tabs.setCurrentIndex(k)
            QTimer.singleShot(2000, lambda: (save(w, f"{tag}_tab{k}"), tabs(k + 1)))
            return
        if theme == "dark":
            return done()
        ds = {"welcome1": gui.WelcomeDialog(w, w.t), "about": gui.AboutDialog(w, w.t),
              "settings": gui.SettingsDialog(w, w.settings),
              "wizard": wizard.NewServerWizard(w, set(), {}, w.t),
              "remove": gui.RemoveDialog(w, w.current(), w.reg.instances)}
        w2 = gui.WelcomeDialog(w, w.t); w2.go(1); ds["welcome2"] = w2
        w3 = gui.WelcomeDialog(w, w.t); w3.go(2); ds["welcome3"] = w3
        wz = ds["wizard"]
        wz.resize(820, 900)
        for d in ds.values():
            d.show()
        QTimer.singleShot(1200, lambda: ([save(d, n) for n, d in ds.items()], [d.close() for d in ds.values()], done()))

    def done():
        w.dispose(); st["i"] += 1; QTimer.singleShot(300, run)
    QTimer.singleShot(2500, lambda: tabs(0))


QTimer.singleShot(100, run)
app.exec()
print(sorted(os.listdir(OUT)))
