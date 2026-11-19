"""Create a GitHub release for the current version and upload dist/release/v<version>/*.

Uses the GitHub sign-in that git already stores on this machine (Git Credential Manager);
the token is read in memory only and never printed or saved.
Usage: .venv\\Scripts\\python.exe tools\\publish_release.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from odoo_manager.core import APP_VERSION      # noqa: E402
from odoo_manager import updater                # noqa: E402

OWNER_REPO = updater.UPDATE_BASE_URL.split("github.com/")[1].split("/releases")[0]


def token() -> str:
    r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True, cwd=ROOT)
    for line in r.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    sys.exit("No saved GitHub sign-in found (push once with git to sign in).")


def api(method, url, tok, data=None, ctype="application/json"):
    body = json.dumps(data).encode() if isinstance(data, dict) else data
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "Content-Type": ctype, "User-Agent": "OdooManager-release"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    ver = APP_VERSION
    tag = f"v{ver}"
    folder = os.path.join(ROOT, "dist", "release", tag)
    files = [f"OdooManager-Setup-{ver}.exe", "latest.json", "latest.json.sig"]
    for f in files:
        if not os.path.exists(os.path.join(folder, f)):
            sys.exit(f"Missing {f} — run tools\\release.py first.")
    tok = token()
    base = f"https://api.github.com/repos/{OWNER_REPO}"

    st, rel = api("GET", f"{base}/releases/tags/{tag}", tok)
    if st == 404:
        notes = json.load(open(os.path.join(folder, "latest.json"), encoding="utf-8")).get("notes", "")
        body = (f"{notes}\n\n**Download:** `OdooManager-Setup-{ver}.exe` and run it.\n\n"
                "If Windows SmartScreen appears: **More info → Run anyway** (the installer is not code-signed yet).\n\n"
                "`latest.json` and `latest.json.sig` are used by the app's signed auto-update.")
        st, rel = api("POST", f"{base}/releases", tok, {"tag_name": tag, "target_commitish": "main",
                                                        "name": f"Odoo Manager {ver}", "body": body,
                                                        "draft": False, "prerelease": False, "make_latest": "true"})
    if st not in (200, 201):
        sys.exit(f"Could not create the release ({st}): {rel.get('message')}")
    print(f"release {tag}: {rel['html_url']}")

    existing = {a["name"]: a["id"] for a in rel.get("assets", [])}
    upload = rel["upload_url"].split("{")[0]
    for f in files:
        if f in existing:
            api("DELETE", f"{base}/releases/assets/{existing[f]}", tok)
        data = open(os.path.join(folder, f), "rb").read()
        ctype = "application/octet-stream" if f.endswith((".exe", ".sig")) else "application/json"
        st, a = api("POST", f"{upload}?name={urllib.parse.quote(f)}", tok, data, ctype)
        print(f"  {'uploaded' if st in (200, 201) else 'FAILED ' + str(st)}: {f} ({len(data) // 1024} KB)")
        if st not in (200, 201):
            sys.exit(a.get("message"))
    print("done")


if __name__ == "__main__":
    main()
