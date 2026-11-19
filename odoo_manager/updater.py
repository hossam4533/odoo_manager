"""Auto-update: check a signed manifest, download the new installer, verify it, run it.

Release side (tools/release.py) publishes three files to the update channel:
    latest.json      {"version", "url", "sha256", "notes", "min_version", "date"}
    latest.json.sig  base64 Ed25519 signature of latest.json's exact bytes
    OdooManager-Setup-<version>.exe
Only someone holding keys/update_private.pem can produce a manifest this app accepts,
so a tampered or spoofed manifest/installer is rejected.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

from .core import APP_VERSION
from .i18n import tr

# Where the app looks for updates. Set it once the GitHub repository exists, e.g.
# "https://github.com/<user>/<repo>/releases/latest/download/" (must end with "/").
UPDATE_BASE_URL = "https://github.com/hossam4533/odoo_manager/releases/latest/download/"

# Public half of the release-signing key (keys/update_private.pem stays private, never shipped).
PUBLIC_KEY_B64 = "+UvM3bvBGjZEB2u6qPKD5D4Qm1UCgPI2IfNMZFFzSz0="

UA = {"User-Agent": f"OdooManager/{APP_VERSION}"}


def vtuple(v: str) -> tuple[int, ...]:
    out = []
    for part in str(v).split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out + [0] * (3 - len(out)))


def enabled() -> bool:
    return bool(UPDATE_BASE_URL)


def _get(url: str, timeout: float = 15) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def verify_signature(data: bytes, sig_b64: str) -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_B64))
        key.verify(base64.b64decode(sig_b64.strip()), data)
        return True
    except Exception:
        return False


def check(base_url: str | None = None) -> dict | None:
    """Return the manifest when a newer version exists, else None. Raises on network/signature errors."""
    base = base_url or UPDATE_BASE_URL
    if not base:
        return None
    raw = _get(base + "latest.json")
    sig = _get(base + "latest.json.sig").decode("ascii", "replace")
    if not verify_signature(raw, sig):
        raise RuntimeError(tr("upd_bad_sig"))
    m = json.loads(raw.decode("utf-8"))
    m["mandatory"] = vtuple(APP_VERSION) < vtuple(m.get("min_version", "0"))
    return m if vtuple(m["version"]) > vtuple(APP_VERSION) else None


def download(manifest: dict, progress=None, cancelled=lambda: False) -> str:
    """Download the installer, check its SHA-256, return the local path."""
    url = manifest["url"]
    dest = os.path.join(tempfile.gettempdir(), f"OdooManager-Setup-{manifest['version']}.exe")
    h = hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            if cancelled():
                raise RuntimeError(tr("cancelled"))
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
            if progress and total:
                progress(got * 100 // total)
    if h.hexdigest().lower() != manifest["sha256"].lower():
        os.remove(dest)
        raise RuntimeError(tr("upd_bad_hash"))
    return dest


def launch_installer(path: str) -> None:
    """Run the new installer silently; it closes this app and starts the new version when done."""
    flags = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/UPDATE=1"]
    subprocess.Popen([path] + flags, close_fds=True,
                     creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS | NEW_PROCESS_GROUP


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
