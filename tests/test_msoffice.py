"""Tes backend Microsoft Office (logika murni + dispatcher).

Eksekusi COM asli hanya jalan di Windows ber-Office, jadi yang diuji
di sini: peta konversi, deteksi (dengan `exists` suntikan), dan
pemilihan backend di converters.office_convert (dengan monkeypatch).
"""
from pathlib import Path

import pytest

from salmanpdf import converters, msoffice
from salmanpdf.converters import ConversionError


# ------------------------------------------------------------- plan_for
def test_plan_word_semua_format():
    assert msoffice.plan_for("word", "pdf") == ("word", "saveas", 17)
    assert msoffice.plan_for("word", "txt") == ("word", "saveas", 2)
    assert msoffice.plan_for("word", "docx") == ("word", "saveas", 16)
    assert msoffice.plan_for("word", "odt") == ("word", "saveas", 23)


def test_plan_slides_dan_sheet():
    assert msoffice.plan_for("slides", "pdf") == ("slides", "saveas", 32)
    assert msoffice.plan_for("slides", "pptx") == ("slides", "saveas", 24)
    assert msoffice.plan_for("sheet", "pdf") == ("sheet", "export_pdf", 0)
    assert msoffice.plan_for("sheet", "csv") == ("sheet", "saveas", 6)
    assert msoffice.plan_for("sheet", "xlsx") == ("sheet", "saveas", 51)


def test_plan_format_tak_didukung_ms():
    # Aplikasi Microsoft memang tidak bisa menyimpan ODP / ODS.
    assert msoffice.plan_for("slides", "odp") is None
    assert msoffice.plan_for("sheet", "ods") is None
    assert msoffice.plan_for("word", "png") is None
    assert msoffice.plan_for("pdf", "pdf") is None


def test_plan_case_insensitive():
    assert msoffice.plan_for("word", "PDF") is not None


# ------------------------------------------------------------- deteksi
def _exists_for(*exe_names):
    def _exists(p: Path) -> bool:
        return p.name in exe_names
    return _exists


def test_find_ms_apps_hanya_yang_terpasang():
    apps = msoffice.find_ms_apps(exists=_exists_for("WINWORD.EXE"),
                                 platform="win32")
    assert set(apps) == {"word"}
    assert apps["word"].name == "WINWORD.EXE"


def test_find_ms_apps_bukan_windows_kosong():
    assert msoffice.find_ms_apps(exists=lambda p: True,
                                 platform="linux") == {}
    assert msoffice.find_ms_apps(exists=lambda p: True,
                                 platform="darwin") == {}


def test_available_plan():
    got = msoffice.available_plan("sheet", "pdf",
                                  exists=_exists_for("EXCEL.EXE"),
                                  platform="win32")
    assert got is not None
    plan, apps = got
    assert plan[0] == "sheet" and "sheet" in apps
    # ODS tetap None walau Excel ada (format tak didukung MS)
    assert msoffice.available_plan("sheet", "ods",
                                   exists=_exists_for("EXCEL.EXE"),
                                   platform="win32") is None
    # App-nya tidak terpasang -> None
    assert msoffice.available_plan("word", "pdf",
                                   exists=lambda p: False,
                                   platform="win32") is None


# ------------------------------------------------------------- dispatcher
def _dummy(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_bytes(b"dummy")
    return p


def test_dispatcher_ms_sukses_tanpa_libre(monkeypatch, tmp_path):
    src = _dummy(tmp_path, "a.docx")

    def fake_convert(src_, kind, fmt, out):
        assert kind == "word" and fmt == "pdf"
        out.write_bytes(b"%PDF-dari-ms")

    monkeypatch.setattr(msoffice, "available_plan",
                        lambda k, f: (("word", "saveas", 17), {"word": Path("x")}))
    monkeypatch.setattr(msoffice, "convert_with_ms_office", fake_convert)
    monkeypatch.setattr(converters, "_find_soffice", lambda: None)
    hasil = converters.office_convert(src, "PDF")
    assert len(hasil) == 1 and hasil[0].exists()
    assert hasil[0].read_bytes() == b"%PDF-dari-ms"


def test_dispatcher_ms_gagal_jatuh_ke_libre(monkeypatch, tmp_path):
    src = _dummy(tmp_path, "a.docx")
    sentinel = tmp_path / "dari-libre.pdf"
    sentinel.write_bytes(b"x")

    def boom(src_, kind, fmt, out):
        raise msoffice.MsOfficeError("COM meledak")

    monkeypatch.setattr(msoffice, "available_plan",
                        lambda k, f: (("word", "saveas", 17), {"word": Path("x")}))
    monkeypatch.setattr(msoffice, "convert_with_ms_office", boom)
    monkeypatch.setattr(converters, "_find_soffice", lambda: "/fake/soffice")
    monkeypatch.setattr(converters, "_office_convert_libre",
                        lambda s, f, b: [sentinel])
    assert converters.office_convert(src, "PDF") == [sentinel]


def test_dispatcher_tidak_ada_backend(monkeypatch, tmp_path):
    src = _dummy(tmp_path, "a.docx")
    monkeypatch.setattr(msoffice, "available_plan", lambda k, f: None)
    monkeypatch.setattr(converters, "_find_soffice", lambda: None)
    with pytest.raises(ConversionError) as ei:
        converters.office_convert(src, "PDF")
    assert "Microsoft Office" in str(ei.value)
    assert "LibreOffice" in str(ei.value)


def test_dispatcher_odp_pesan_khusus(monkeypatch, tmp_path):
    src = _dummy(tmp_path, "a.pptx")
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(msoffice, "available_plan", lambda k, f: None)
    monkeypatch.setattr(msoffice, "find_ms_apps",
                        lambda **kw: {"slides": Path("POWERPNT.EXE")})
    monkeypatch.setattr(converters, "_find_soffice", lambda: None)
    with pytest.raises(ConversionError) as ei:
        converters.office_convert(src, "ODP")
    assert "ODP" in str(ei.value) and "LibreOffice" in str(ei.value)


def test_convert_ms_plan_none_error_bersih(tmp_path):
    with pytest.raises(msoffice.MsOfficeError):
        msoffice.convert_with_ms_office(
            tmp_path / "a.pptx", "slides", "odp", tmp_path / "out.odp")
