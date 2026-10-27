"""Tes pemeriksa update (murni, jaringan disuntikkan)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salmanpdf import updater as U

CHANGELOG = """# Changelog SalmanPDF

## v0.11.0 — 2026-10-27
- Fitur update otomatis.
- Siap lintas platform.

## v0.10.0 — 2026-10-27
- Pisah PDF manual.

## v0.9.0 — 2026-10-27
- Edit PDF bisa zoom & seret.
"""


def fake_fetch_factory(init_version="0.11.0", changelog=CHANGELOG):
    def fetch(url: str) -> str:
        if url.endswith("__init__.py"):
            return f'__version__ = "{init_version}"\n'
        return changelog
    return fetch


def test_banding_versi():
    assert U.version_tuple("0.10.0") > U.version_tuple("0.9.0")
    assert U.is_newer("1.0.0", "0.99.9")
    assert not U.is_newer("0.11.0", "0.11.0")
    assert U.parse_latest_version('__version__ = "2.3.4"') == "2.3.4"


def test_changelog_irisan():
    notes = U.changelog_between(CHANGELOG, "0.9.0", "0.11.0")
    assert "v0.11.0" in notes and "Pisah PDF manual" in notes
    assert "Edit PDF bisa zoom" not in notes  # versi terpasang tak ikut


def test_check_update():
    res = U.check_update("0.9.0", fetch=fake_fetch_factory())
    assert res is not None and res["latest"] == "0.11.0"
    assert "Fitur update otomatis" in res["notes"]
    assert U.check_update("0.11.0", fetch=fake_fetch_factory()) is None


def test_check_update_jaringan_gagal_senyap():
    def boom(url: str) -> str:
        raise OSError("offline")
    assert U.check_update("0.9.0", fetch=boom) is None


def test_check_update_detailed_states():
    assert U.check_update_detailed(
        "0.9.0", fetch=fake_fetch_factory())["state"] == "update"
    cur = U.check_update_detailed("0.11.0", fetch=fake_fetch_factory())
    assert cur["state"] == "current" and cur["latest"] == "0.11.0"

    def boom(url: str) -> str:
        raise OSError("offline")
    assert U.check_update_detailed("0.9.0", fetch=boom)["state"] == "error"


def test_check_update_git():
    outputs = {
        ("show", "origin/main:salmanpdf/__init__.py"): '__version__ = "0.11.0"\n',
        ("show", "origin/main:CHANGELOG.md"): CHANGELOG,
    }

    def runner(args, cwd):
        if args[0] == "fetch":
            return ""
        return outputs[tuple(args)]

    res = U.check_update_git("0.10.0", "/repo", runner=runner)
    assert res["state"] == "update" and res["latest"] == "0.11.0"
    assert "Fitur update otomatis" in res["notes"]
    assert "Pisah PDF manual" not in res["notes"]  # 0.10.0 = versi terpasang
    assert U.check_update_git("0.11.0", "/repo", runner=runner)["state"] == "current"

    def boom(args, cwd):
        raise OSError("no repo")
    assert U.check_update_git("0.10.0", "/repo", runner=boom)["state"] == "error"
