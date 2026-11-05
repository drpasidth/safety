"""DOCX -> PDF through Microsoft Word (Windows only)."""
import tempfile
from pathlib import Path


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


def docx_to_pdf(docx_bytes: bytes) -> bytes:
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


def update_docx_fields(docx_bytes: bytes) -> bytes:
    """Refresh the table of contents so the downloaded DOCX opens with page numbers filled in."""
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


def _drop_update_fields(docx_bytes: bytes) -> bytes:
    """Fields are already current, so stop Word asking to update them on every open."""
    import io

    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(io.BytesIO(docx_bytes))
    for el in doc.settings.element.findall(qn("w:updateFields")):
        el.getparent().remove(el)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
