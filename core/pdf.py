"""DOCX -> PDF through Microsoft Word (Windows) or LibreOffice (servers)."""
import io
import os
import shutil
import subprocess
import tempfile
import uuid
from functools import lru_cache
from pathlib import Path

WORD, LIBREOFFICE = "Microsoft Word", "LibreOffice"


@lru_cache(maxsize=1)
def word_available() -> bool:
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    import winreg
    try:
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Word.Application")
        return True
    except OSError:
        return False


@lru_cache(maxsize=1)
def soffice_path() -> str:
    candidates = [os.environ.get("SOFFICE_PATH", ""), shutil.which("soffice") or "", shutil.which("libreoffice") or "",
                  r"C:\Program Files\LibreOffice\program\soffice.exe"]
    return next((c for c in candidates if c and Path(c).exists()), "")


def available() -> str:
    """Name of the PDF engine, or "" when PDF export is not possible."""
    if os.environ.get("PDF_ENGINE", "").lower() != "libreoffice" and word_available():
        return WORD
    return LIBREOFFICE if soffice_path() else ""


def docx_to_pdf(docx_bytes: bytes) -> bytes:
    engine = available()
    if engine == WORD:
        return _word_to_pdf(docx_bytes)
    if engine == LIBREOFFICE:
        return _soffice_to_pdf(docx_bytes)
    raise RuntimeError("PDF export needs Microsoft Word or LibreOffice")


def update_docx_fields(docx_bytes: bytes) -> bytes:
    """Refresh the table of contents so the downloaded DOCX opens with page numbers filled in (Word only)."""
    if available() != WORD:
        return docx_bytes
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    word = None
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "report.docx"
        src.write_bytes(docx_bytes)
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            doc = word.Documents.Open(str(src), AddToRecentFiles=False)
            for toc in doc.TablesOfContents:
                toc.Update()
            doc.Save()
            doc.Close(SaveChanges=0)
        finally:
            if word is not None:
                word.Quit()
            pythoncom.CoUninitialize()
        return _drop_update_fields(src.read_bytes())


def _word_to_pdf(docx_bytes: bytes) -> bytes:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    word = None
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "report.docx", Path(tmp) / "report.pdf"
        src.write_bytes(docx_bytes)
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            doc = word.Documents.Open(str(src), ReadOnly=False, AddToRecentFiles=False)
            for toc in doc.TablesOfContents:
                toc.Update()
            doc.Fields.Update()
            doc.SaveAs2(str(dst), FileFormat=17)
            doc.Close(SaveChanges=0)
        finally:
            if word is not None:
                word.Quit()
            pythoncom.CoUninitialize()
        return dst.read_bytes()


def _soffice_to_pdf(docx_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "report.docx"
        src.write_bytes(docx_bytes)
        # A private profile per call: concurrent soffice processes sharing one profile block each other.
        profile = (Path(tmp) / f"lo-{uuid.uuid4().hex}").as_uri()
        subprocess.run([soffice_path(), f"-env:UserInstallation={profile}", "--headless", "--norestore",
                        "--convert-to", "pdf", "--outdir", tmp, str(src)],
                       check=True, capture_output=True, timeout=180)
        return (Path(tmp) / "report.pdf").read_bytes()


def _drop_update_fields(docx_bytes: bytes) -> bytes:
    """Fields are already current, so stop Word asking to update them on every open."""
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(io.BytesIO(docx_bytes))
    for el in doc.settings.element.findall(qn("w:updateFields")):
        el.getparent().remove(el)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
