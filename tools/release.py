"""Build and sign a new Odoo Manager release.

Usage (from C:\\OdooManager):
    .venv\\Scripts\\python.exe tools\\release.py --notes "What changed" --notes-ar "ما الجديد"
    optional: --min-version 1.2.0   (older versions must update before they can be used)
              --no-build            (reuse dist\\OdooManager.exe)

Before running: raise APP_VERSION in odoo_manager\\core.py.
Output: dist\\release\\v<version>\\  ->  upload all three files to a GitHub release named v<version>.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from odoo_manager.core import APP_VERSION          # noqa: E402
from odoo_manager import updater                    # noqa: E402

ISCC = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe")
KEY = os.path.join(ROOT, "keys", "update_private.pem")


def run(cmd, **kw):
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", default="")
    ap.add_argument("--notes-ar", default="")
    ap.add_argument("--min-version", default="0")
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args()

    base = updater.UPDATE_BASE_URL
    if not base.endswith("/releases/latest/download/"):
        sys.exit("Set UPDATE_BASE_URL in odoo_manager/updater.py to "
                 "https://github.com/<user>/<repo>/releases/latest/download/")
    if not os.path.exists(KEY):
        sys.exit(f"Signing key not found: {KEY}")
    ver = APP_VERSION
    print(f"== Releasing Odoo Manager {ver}")

    if not a.no_build:
        run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "build.ps1"])
    run([ISCC, f"/DAppVersion={ver}", "installer.iss"])

    setup_name = f"OdooManager-Setup-{ver}.exe"
    setup = os.path.join(ROOT, "dist", setup_name)
    out = os.path.join(ROOT, "dist", "release", f"v{ver}")
    os.makedirs(out, exist_ok=True)
    shutil.copy2(setup, os.path.join(out, setup_name))

    sha = hashlib.sha256(open(setup, "rb").read()).hexdigest()
    url = base.replace("/releases/latest/download/", f"/releases/download/v{ver}/") + setup_name
    manifest = {"version": ver, "url": url, "sha256": sha, "notes": a.notes, "notes_ar": a.notes_ar,
                "min_version": a.min_version, "date": datetime.date.today().isoformat()}
    raw = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    open(os.path.join(out, "latest.json"), "wb").write(raw)

    from cryptography.hazmat.primitives import serialization
    key = serialization.load_pem_private_key(open(KEY, "rb").read(), None)
    sig = base64.b64encode(key.sign(raw)).decode()
    open(os.path.join(out, "latest.json.sig"), "w", encoding="ascii").write(sig)
    assert updater.verify_signature(raw, sig), "signature self-check failed"

    print(f"""
== Done: {out}
   {setup_name}   ({os.path.getsize(setup) // 1048576} MB, sha256 {sha[:12]}…)
   latest.json
   latest.json.sig

Publish:
  1. GitHub → your repository → Releases → Draft a new release
  2. Tag: v{ver}    Title: Odoo Manager {ver}
  3. Upload the three files above, keep "Set as the latest release" ticked, Publish.
Every installed copy picks it up within 12 hours (or at its next start).
""")


if __name__ == "__main__":
    main()
