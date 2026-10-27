"""
Pemeriksa update SalmanPDF.

Sumber kebenaran versi = repo GitHub publik/privat user sendiri:
berkas salmanpdf/__init__.py (memuat __version__) dan CHANGELOG.md di
branch main. Logika di modul ini MURNI (tanpa GUI) dan fungsi ambil-data
bisa disuntikkan (fetch=...) supaya bisa diuji tanpa jaringan.

Catatan: repo saat ini bernama tangerine-linux di GitHub (rename ke
salmanpdf masih pending di Settings repo) — URL mengikutinya.
"""
from __future__ import annotations

import re
import urllib.request
from typing import Callable

REPO = "riccohsaputra/tangerine-linux"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
INIT_URL = f"{RAW}/salmanpdf/__init__.py"
CHANGELOG_URL = f"{RAW}/CHANGELOG.md"
RELEASES_URL = f"https://github.com/{REPO}/releases"
REPO_URL = f"https://github.com/{REPO}"

_VERSION_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')
_SECTION_RE = re.compile(r"^##\s+v(\d+\.\d+\.\d+)\b[^\n]*\n(.*?)(?=^##\s+v|\Z)",
                         re.M | re.S)


def fetch_text(url: str, timeout: float = 6.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "SalmanPDF"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def version_tuple(v: str) -> tuple[int, ...]:
    """'0.10.0' -> (0, 10, 0). Bagian non-angka dianggap 0."""
    parts = []
    for p in v.strip().lstrip("v").split("."):
        m = re.match(r"\d+", p)
        parts.append(int(m.group()) if m else 0)
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    return version_tuple(latest) > version_tuple(current)


def parse_latest_version(init_source: str) -> str | None:
    m = _VERSION_RE.search(init_source)
    return m.group(1) if m else None


def changelog_between(changelog_md: str, current: str,
                      latest: str) -> str:
    """
    Ambil irisan CHANGELOG untuk versi (current, latest] — yang lebih
    baru dari versi terpasang, sampai versi terbaru. Urutan mengikuti
    berkas (terbaru dulu). Kosong bila tak ada yang cocok.
    """
    cur, lat = version_tuple(current), version_tuple(latest)
    out: list[str] = []
    for m in _SECTION_RE.finditer(changelog_md):
        vt = version_tuple(m.group(1))
        if cur < vt <= lat:
            body = m.group(2).strip()
            out.append(f"v{m.group(1)}\n{body}".rstrip())
    return "\n\n".join(out)


def check_update_detailed(current: str,
                          fetch: Callable[[str], str] = fetch_text) -> dict:
    """
    Hasil cek update terperinci:
    {"state": "update", "latest": ..., "notes": ...} — ada versi baru
    {"state": "current", "latest": ...}              — sudah paling baru
    {"state": "error"}                               — server tak terjangkau
    """
    try:
        latest = parse_latest_version(fetch(INIT_URL))
    except Exception:
        return {"state": "error"}
    if latest is None:
        return {"state": "error"}
    if not is_newer(latest, current):
        return {"state": "current", "latest": latest}
    notes = ""
    try:
        notes = changelog_between(fetch(CHANGELOG_URL), current, latest)
    except Exception:
        notes = ""
    return {"state": "update", "latest": latest, "notes": notes}


def check_update(current: str,
                 fetch: Callable[[str], str] = fetch_text) -> dict | None:
    """
    Return dict {latest, notes} bila ada versi lebih baru, selain itu
    None (sudah terbaru / gagal cek) — untuk pemanggil mode senyap.
    """
    res = check_update_detailed(current, fetch)
    return res if res["state"] == "update" else None


# ------------------------------------------------------- cek via git lokal
def _git_runner(args: list[str], cwd) -> str:
    import subprocess

    proc = subprocess.run(["git", *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=90)
    if proc.returncode != 0:
        raise OSError((proc.stderr or "git gagal").strip())
    return proc.stdout


def check_update_git(current: str, root,
                     runner: Callable[..., str] = _git_runner) -> dict:
    """
    Cek update memakai git lokal (fetch + baca berkas dari origin/main).
    Jalan walau repo privat karena memakai kredensial git pengguna
    sendiri — jalur utama untuk instalasi checkout (Linux dev).
    Hasil sama bentuknya dengan check_update_detailed.
    """
    try:
        try:
            runner(["fetch", "--quiet", "origin"], root)
        except Exception:
            pass  # fetch gagal (offline): nilai dari refs yang ada
        latest = parse_latest_version(
            runner(["show", "origin/main:salmanpdf/__init__.py"], root))
    except Exception:
        return {"state": "error"}
    if latest is None:
        return {"state": "error"}
    if not is_newer(latest, current):
        return {"state": "current", "latest": latest}
    notes = ""
    try:
        notes = changelog_between(
            runner(["show", "origin/main:CHANGELOG.md"], root),
            current, latest)
    except Exception:
        notes = ""
    return {"state": "update", "latest": latest, "notes": notes}
