"""python-docx helpers for Thai reports."""
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

CHECK = "✓"
HEADER_BLUE = RGBColor(0x1F, 0x4E, 0x79)


def new_document(font: str, size: int) -> Document:
    doc = Document()
    for style_name in ("Normal", "Heading 1", "Heading 2", "Title"):
        style = doc.styles[style_name]
        style.font.name = font
        style.font.color.rgb = RGBColor(0, 0, 0)
        rpr = style.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.append(fonts)
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            fonts.set(qn(attr), font)
        for theme_attr in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
            fonts.attrib.pop(qn(theme_attr), None)
    _set_size(doc.styles["Normal"], size)
    _set_size(doc.styles["Heading 1"], size + 2, bold=True)
    _set_size(doc.styles["Heading 2"], size, bold=True)
    for style_name in ("Normal", "Heading 1", "Heading 2", "Title"):
        rpr = doc.styles[style_name].element.get_or_add_rPr()
        lang = rpr.find(qn("w:lang"))
        if lang is None:
            lang = OxmlElement("w:lang")
            rpr.append(lang)
        lang.set(qn("w:val"), "th-TH")
        lang.set(qn("w:bidi"), "th-TH")
        if rpr.find(qn("w:cs")) is None:
            rpr.append(OxmlElement("w:cs"))
        sort_rpr(rpr)
    for name in ("Heading 1", "Heading 2"):
        pf = doc.styles[name].paragraph_format
        pf.space_before, pf.space_after = Pt(8), Pt(4)
        pf.keep_with_next = True
    pf = doc.styles["Normal"].paragraph_format
    pf.space_after, pf.space_before, pf.line_spacing = Pt(0), Pt(0), 1.0
    settings = doc.settings.element
    upd = OxmlElement("w:updateFields")
    upd.set(qn("w:val"), "true")
    settings.append(upd)
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(2.0)
    sec.top_margin, sec.bottom_margin = Cm(1.5), Cm(1.5)
    sec.header_distance, sec.footer_distance = Cm(0.8), Cm(0.8)
    return doc


RPR_ORDER = ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline",
             "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing", "w",
             "kern", "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign",
             "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish", "oMath"]


def sort_rpr(rpr):
    """Word silently ignores run properties that are out of schema order."""
    rank = {qn(f"w:{n}"): i for i, n in enumerate(RPR_ORDER)}
    children = {}
    for c in list(rpr):
        rpr.remove(c)
        children[c.tag] = c
    for c in sorted(children.values(), key=lambda c: rank.get(c.tag, len(rank))):
        rpr.append(c)


def _set_size(style, size, bold=None):
    style.font.size = Pt(size)
    rpr = style.element.get_or_add_rPr()
    szcs = rpr.find(qn("w:szCs"))
    if szcs is None:
        szcs = OxmlElement("w:szCs")
        rpr.append(szcs)
    szcs.set(qn("w:val"), str(int(size * 2)))
    if bold is not None:
        style.font.bold = bold
        if rpr.find(qn("w:bCs")) is None:
            rpr.append(OxmlElement("w:bCs"))


def run(par, text, bold=False, size=None, color=None, italic=False):
    r = par.add_run(text)
    r.bold, r.italic = bold, italic
    rpr = r._element.get_or_add_rPr()
    if bold:
        rpr.append(OxmlElement("w:bCs"))
    if size:
        r.font.size = Pt(size)
        szcs = OxmlElement("w:szCs")
        szcs.set(qn("w:val"), str(int(size * 2)))
        rpr.append(szcs)
    if color:
        r.font.color.rgb = color
    sort_rpr(rpr)
    return r


def para(container, text="", bold=False, size=None, align=None, indent_cm=None, space_after=0):
    p = container.add_paragraph()
    if text:
        run(p, text, bold=bold, size=size)
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "right":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align == "justify":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if indent_cm:
        p.paragraph_format.left_indent = Cm(indent_cm)
    if space_after:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def multiline(cell_or_doc, text, size=None, bold=False, first=True):
    """Write text with line breaks into a cell (reusing its first paragraph)."""
    lines = (text or "").split("\n")
    if first and hasattr(cell_or_doc, "paragraphs") and cell_or_doc.paragraphs and not cell_or_doc.paragraphs[0].text:
        p = cell_or_doc.paragraphs[0]
    else:
        p = cell_or_doc.add_paragraph()
    for i, line in enumerate(lines):
        if i:
            p.add_run().add_break()
        run(p, line, size=size, bold=bold)
    return p


def letterhead(section, lines: list[str], logo: Path | None, size: int):
    section.different_first_page_header_footer = False
    header = section.header
    header.is_linked_to_previous = False
    table = header.add_table(rows=1, cols=2, width=section.page_width - section.left_margin - section.right_margin)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    logo_cell, text_cell = table.rows[0].cells
    logo_cell.width, text_cell.width = Cm(2.6), Cm(14)
    if logo and logo.exists():
        logo_cell.paragraphs[0].add_run().add_picture(str(logo), width=Cm(2.2))
    for i, line in enumerate(lines):
        p = text_cell.paragraphs[0] if i == 0 else text_cell.add_paragraph()
        run(p, line, size=size - 2, color=HEADER_BLUE)
    for p in header.paragraphs:
        if not p.text:
            bottom_border(p)
            break
    else:
        bottom_border(header.add_paragraph())
    for cell in (logo_cell, text_cell):
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def bottom_border(paragraph, color="1F4E79", size=18):
    ppr = paragraph._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", str(size)), ("w:space", "1"), ("w:color", color)):
        bottom.set(qn(k), v)
    bdr.append(bottom)
    ppr.append(bdr)


def page_number_footer(section, size):
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _field(p, "PAGE", size)


def _field(paragraph, instr, size):
    r = run(paragraph, "", size=size)
    for tag, text in (("begin", None), ("instr", instr), ("separate", None), ("text", "1"), ("end", None)):
        if tag == "instr":
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = f" {text} "
            r._element.append(el)
        elif tag == "text":
            t = OxmlElement("w:t")
            t.text = text
            r._element.append(t)
        else:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), tag)
            r._element.append(fc)


def toc(doc, size):
    p = doc.add_paragraph()
    _field(p, 'TOC \\o "1-2" \\h \\z \\u', size)


def new_section(doc, landscape: bool):
    from docx.enum.section import WD_SECTION
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    w, h = Cm(21.0), Cm(29.7)
    if landscape:
        sec.orientation, sec.page_width, sec.page_height = WD_ORIENT.LANDSCAPE, h, w
    else:
        sec.orientation, sec.page_width, sec.page_height = WD_ORIENT.PORTRAIT, w, h
    sec.left_margin = sec.right_margin = Cm(1.5 if landscape else 2.0)
    return sec


def shade(cell, fill: str):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcpr.append(shd)


def repeat_header(row):
    trpr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def no_split(row):
    trpr = row._tr.get_or_add_trPr()
    trpr.append(OxmlElement("w:cantSplit"))


def set_widths(table, widths_cm):
    table.autofit = False
    tbl = table._tbl
    grid = tbl.tblGrid
    for i, gc in enumerate(grid.findall(qn("w:gridCol"))):
        if i < len(widths_cm):
            gc.set(qn("w:w"), str(int(widths_cm[i] * 567)))
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            if i < len(widths_cm):
                cell.width = Cm(widths_cm[i])


def cell_text(cell, text, size=None, bold=False, align=None, fill=None, valign="top"):
    cell.text = ""
    p = multiline(cell, text, size=size, bold=bold)
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if fill:
        shade(cell, fill)
    cell.vertical_alignment = {"top": WD_CELL_VERTICAL_ALIGNMENT.TOP,
                               "center": WD_CELL_VERTICAL_ALIGNMENT.CENTER}[valign]
    return p


def grid_table(container, rows, cols):
    t = container.add_table(rows=rows, cols=cols)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    return t
