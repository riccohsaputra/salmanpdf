"""
Backend Microsoft Office untuk konversi dokumen (khusus Windows).

Menjalankan Word/PowerPoint/Excel asli lewat COM (pywin32) supaya
dokumen .docx/.pptx/.xlsx bisa dikonversi tanpa LibreOffice, dengan
hasil render yang sama seperti aplikasi aslinya. Modul ini MURNI
logika + deteksi di bagian atas; impor win32com dilakukan malas
(lazy) di dalam fungsi eksekusi, jadi modul aman diimpor di semua OS
dan logikanya bisa diuji unit di Linux.

Batasan jujur:
- Hanya Windows (COM tidak ada di OS lain).
- PowerPoint tidak bisa menyimpan ODP dan Excel tidak bisa menyimpan
  ODS -> plan_for() mengembalikan None untuk pasangan itu, dan
  pemanggil (converters.office_convert) jatuh ke LibreOffice.
- Butuh pywin32 terpasang (di requirements dengan penanda win32).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

# app_key -> (ProgID COM, nama berkas exe)
APPS: dict[str, tuple[str, str]] = {
    "word": ("Word.Application", "WINWORD.EXE"),
    "slides": ("PowerPoint.Application", "POWERPNT.EXE"),
    "sheet": ("Excel.Application", "EXCEL.EXE"),
}

# (kind, fmt) -> (app_key, metode, kode format)
# Kode = konstanta SaveAs aplikasi yang bersangkutan:
#   Word  (WdSaveFormat):        PDF 17, Text 2, DOCX 16, ODT 23
#   PowerPoint (PpSaveAsType):   PDF 32, PPTX 24
#   Excel (XlFileFormat):        CSV 6, XLSX 51; PDF lewat
#                                ExportAsFixedFormat(type=0 xlTypePDF)
_PLANS: dict[tuple[str, str], tuple[str, str, int]] = {
    ("word", "pdf"): ("word", "saveas", 17),
    ("word", "txt"): ("word", "saveas", 2),
    ("word", "docx"): ("word", "saveas", 16),
    ("word", "odt"): ("word", "saveas", 23),
    ("slides", "pdf"): ("slides", "saveas", 32),
    ("slides", "pptx"): ("slides", "saveas", 24),
    ("sheet", "pdf"): ("sheet", "export_pdf", 0),
    ("sheet", "csv"): ("sheet", "saveas", 6),
    ("sheet", "xlsx"): ("sheet", "saveas", 51),
    # ("slides", "odp") dan ("sheet", "ods") SENGAJA tidak ada:
    # aplikasi Microsoft tidak mendukung menyimpan format itu.
}


def plan_for(kind: str, fmt: str) -> tuple[str, str, int] | None:
    """Rencana konversi MS Office untuk (kind, fmt); None bila tidak didukung."""
    return _PLANS.get((kind, fmt.lower()))


def _candidate_paths(exe: str) -> list[Path]:
    """Lokasi pemasangan baku Microsoft Office (Click-to-Run & lama)."""
    roots = [Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")]
    layouts = [r"Microsoft Office\root\Office16",
               r"Microsoft Office\Office16",
               r"Microsoft Office\Office15",
               r"Microsoft Office\Office14"]
    return [root / layout / exe for root in roots for layout in layouts]


def find_ms_apps(exists: Callable[[Path], bool] | None = None,
                 platform: str | None = None) -> dict[str, Path]:
    """
    Deteksi aplikasi MS Office yang terpasang: {app_key: path exe}.
    Hanya Windows; di OS lain selalu {}. `exists` bisa disuntikkan
    untuk pengujian.
    """
    if (platform or sys.platform) != "win32":
        return {}
    if exists is None:
        exists = Path.exists
    found: dict[str, Path] = {}
    for key, (_progid, exe) in APPS.items():
        for cand in _candidate_paths(exe):
            if exists(cand):
                found[key] = cand
                break
    return found


def available_plan(kind: str, fmt: str,
                   exists: Callable[[Path], bool] | None = None,
                   platform: str | None = None
                   ) -> tuple[tuple[str, str, int], dict[str, Path]] | None:
    """
    (plan, apps) bila konversi (kind, fmt) bisa dilayani MS Office di
    mesin ini; None bila tidak (format tak didukung / app tak ada /
    bukan Windows).
    """
    plan = plan_for(kind, fmt)
    if plan is None:
        return None
    apps = find_ms_apps(exists=exists, platform=platform)
    if plan[0] not in apps:
        return None
    return plan, apps


class MsOfficeError(Exception):
    """Kegagalan backend MS Office (pesan aman ditampilkan ke user)."""


def convert_with_ms_office(src: Path, kind: str, fmt: str, out: Path) -> None:
    """
    Konversi `src` ke berkas `out` memakai aplikasi MS Office terkait.
    HANYA Windows + pywin32; kegagalan apa pun -> MsOfficeError.
    """
    plan = plan_for(kind, fmt)
    if plan is None:
        raise MsOfficeError(f"Microsoft Office tidak mendukung {kind} -> {fmt}")
    app_key, method, code = plan
    progid = APPS[app_key][0]
    try:
        import pythoncom
        import win32com.client
    except ImportError as e:
        raise MsOfficeError(
            "pywin32 tidak terpasang, backend Microsoft Office nonaktif") from e
    pythoncom.CoInitialize()
    app = None
    try:
        app = win32com.client.Dispatch(progid)
        app.Visible = False
        try:
            app.DisplayAlerts = 0  # wdAlertsNone / ppAlertsNone / xlAlertsNone
        except Exception:
            pass
        if app_key == "word":
            doc = app.Documents.Open(str(src), ReadOnly=True)
            try:
                doc.SaveAs2(str(out), code)
            finally:
                doc.Close(False)
        elif app_key == "slides":
            pres = app.Presentations.Open(str(src), WithWindow=False)
            try:
                pres.SaveAs(str(out), code)
            finally:
                pres.Close()
        else:  # sheet
            wb = app.Workbooks.Open(str(src), ReadOnly=True)
            try:
                if method == "export_pdf":
                    wb.ExportAsFixedFormat(code, str(out))
                else:
                    wb.SaveAs(str(out), code)
            finally:
                wb.Close(False)
    except MsOfficeError:
        raise
    except Exception as e:  # COM error dsb.
        raise MsOfficeError(f"{progid}: {e}") from e
    finally:
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
    if not out.exists():
        raise MsOfficeError(f"{progid} tidak menghasilkan berkas keluaran")
