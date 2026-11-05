"""Clause 4.2.1 worksheet: context of the establishment (issues, interested parties, initial review)."""
import io
from pathlib import Path

from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_ROW_HEIGHT_RULE
from docx.shared import Cm

from core import standard, thaidate
from core import docx_utils as du
from core.report_docx import HEAD_FILL, SUB_FILL

BLANK_ROWS = 4
ISSUE_COLS = [("ลำดับ", 1.2), ("ประเภทประเด็น", 4.4), ("ประเด็น", 5.8), ("ผลกระทบต่อความปลอดภัยฯ /\nต่อการบรรลุผลของระบบ", 5.2),
              ("ความเสี่ยง /\nโอกาส", 2.2), ("การดำเนินการ / มาตรการ", 5.7), ("ผู้รับผิดชอบ", 2.8)]
PARTY_COLS = [("ลำดับ", 1.2), ("ผู้มีส่วนได้ส่วนเสีย", 4.2), ("ความต้องการและความคาดหวัง", 7.5),
              ("เป็นข้อกำหนด\nที่ต้องปฏิบัติ", 2.4), ("การตอบสนอง / การดำเนินการ", 9.0), ("ผู้รับผิดชอบ", 3.0)]
ISSUE_BANDS = [("internal", "ประเด็นภายใน"), ("external", "ประเด็นภายนอก")]
PARTY_BANDS = [("internal", "ผู้มีส่วนได้ส่วนเสียภายในองค์กร"), ("external", "ผู้มีส่วนได้ส่วนเสียภายนอกองค์กร")]


def build_context_docx(project: dict | None, ctx: dict | None, settings: dict) -> bytes:
    """`ctx=None` produces a blank form for filling in by hand."""
    ctx = ctx or {}
    size, tsize = settings["font_size"], settings["table_font_size"]
    doc = du.new_document(settings["font"], size)
    sec = doc.sections[0]
    sec.orientation, sec.page_width, sec.page_height = WD_ORIENT.LANDSCAPE, Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(1.2)
    logo = Path(settings["logo"]) if settings.get("logo") else None
    du.letterhead(sec, settings["org_lines"], logo, size)
    du.page_number_footer(sec, size)

    du.para(doc, "แบบฟอร์มการวิเคราะห์บริบทของสถานประกอบกิจการ", bold=True, size=size + 2, align="center")
    du.para(doc, "ข้อกำหนด 4.2.1 บริบทของสถานประกอบกิจการ (T-OSH OSHMS:2023)", align="center", space_after=6)
    _doc_info(doc, project, ctx, tsize)
    _requirements(doc, tsize)

    doc.add_heading("ส่วนที่ 1 ประเด็นภายในและภายนอกที่ส่งผลต่อความสามารถในการบรรลุผลของระบบการจัดการฯ (ข้อ 1)", level=2)
    _table(doc, ISSUE_COLS, ISSUE_BANDS, tsize, ctx.get("issues"), _issue_row)

    doc.add_heading("ส่วนที่ 2 ความต้องการและความคาดหวังของผู้มีส่วนได้ส่วนเสีย (ข้อ 2)", level=2)
    _table(doc, PARTY_COLS, PARTY_BANDS, tsize, ctx.get("parties"), _party_row)

    doc.add_heading("ส่วนที่ 3 การทบทวนสถานะเบื้องต้น รวมถึงการปฏิบัติตามกฎหมายและข้อกำหนดอื่น ๆ ที่เกี่ยวข้อง (ข้อ 3)", level=2)
    ir = ctx.get("initial_round")
    if ir:
        p = du.para(doc, f"ดำเนินการทบทวนสถานะเริ่มต้น (Initial Review) เมื่อ{thaidate.long(ir['date'])} "
                         f"ผลการดำเนินการตามข้อกำหนด {ir['conform']} ข้อ จาก {ir['total']} ข้อ คิดเป็นร้อยละ {ir['pct']:.2f}",
                    indent_cm=0.6)
        p.paragraph_format.keep_with_next = True
    _note(doc, ctx.get("initial_review_note"), tsize)

    doc.add_heading("ส่วนที่ 4 การติดตามให้ระบบการจัดการฯ ดำเนินการได้อย่างมีประสิทธิภาพและประสิทธิผล (ข้อ 4)", level=2)
    _note(doc, ctx.get("effectiveness_note"), tsize)

    _signatures(doc, ctx, size)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _doc_info(doc, project, ctx, tsize):
    dots = "...................."
    name = (project or {}).get("profile", {}).get("name") or dots * 2
    rows = [("สถานประกอบกิจการ", name, "เลขที่เอกสาร", ctx.get("doc_no") or dots),
            ("วันที่มีผลบังคับใช้", thaidate.short(ctx.get("effective_date")) or dots,
             "แก้ไขครั้งที่", ctx.get("revision") or dots),
            ("วันที่ทบทวนล่าสุด", thaidate.short(ctx.get("reviewed_date")) or dots,
             "กำหนดทบทวนครั้งถัดไป", thaidate.short(ctx.get("next_review")) or dots)]
    t = du.grid_table(doc, len(rows), 4)
    for r, values in enumerate(rows):
        for c, v in enumerate(values):
            du.cell_text(t.cell(r, c), v, tsize, bold=c % 2 == 0, fill=SUB_FILL if c % 2 == 0 else None)
    du.set_widths(t, [4.0, 11.0, 4.5, 7.8])
    du.para(doc, space_after=4)


def _requirements(doc, tsize):
    items = [i for i in standard.items() if i["subclause"] == "4.2.1"]
    t = du.grid_table(doc, 2, 1)
    du.cell_text(t.cell(0, 0), "ข้อกำหนดที่เกี่ยวข้อง", tsize, bold=True, fill=HEAD_FILL)
    du.cell_text(t.cell(1, 0), "\n".join(i["requirement"] for i in items), tsize - 1)
    du.set_widths(t, [27.3])


def _min_height(row, cm):
    row.height, row.height_rule = Cm(cm), WD_ROW_HEIGHT_RULE.AT_LEAST


def _table(doc, cols, bands, tsize, rows, fill_row):
    t = du.grid_table(doc, 1, len(cols))
    du.repeat_header(t.rows[0])
    for i, (label, _) in enumerate(cols):
        du.cell_text(t.cell(0, i), label, tsize, True, "center", HEAD_FILL, "center")
    n = 0
    for scope, label in bands:
        band = t.add_row()
        du.no_split(band)
        du.cell_text(band.cells[0].merge(band.cells[-1]), label, tsize, True, fill=SUB_FILL)
        scoped = [r for r in rows or [] if r["scope"] == scope]
        for r in scoped or [None] * (BLANK_ROWS if rows is None else 1):
            row = t.add_row()
            du.no_split(row)
            if r is None:
                if rows is None:
                    _min_height(row, 1.2)
                else:
                    du.cell_text(row.cells[0].merge(row.cells[-1]), "-", tsize, align="center")
                continue
            n += 1
            du.cell_text(row.cells[0], str(n), tsize, align="center")
            fill_row(row, r, tsize)
    du.set_widths(t, [w for _, w in cols])
    du.para(doc, space_after=4)


def _issue_row(row, r, tsize):
    for i, key in enumerate(("category_label", "issue", "effect"), 1):
        du.cell_text(row.cells[i], r.get(key, ""), tsize)
    du.cell_text(row.cells[4], r.get("nature_label", ""), tsize, align="center")
    du.cell_text(row.cells[5], r.get("action", ""), tsize)
    du.cell_text(row.cells[6], r.get("responsible", ""), tsize)


def _party_row(row, r, tsize):
    du.cell_text(row.cells[1], r.get("party", ""), tsize)
    du.cell_text(row.cells[2], r.get("needs", ""), tsize)
    du.cell_text(row.cells[3], du.CHECK if r.get("is_requirement") else "", tsize, align="center")
    du.cell_text(row.cells[4], r.get("action", ""), tsize)
    du.cell_text(row.cells[5], r.get("responsible", ""), tsize)


def _note(doc, text, tsize):
    t = du.grid_table(doc, 1, 1)
    du.cell_text(t.cell(0, 0), text or "", tsize)
    du.no_split(t.rows[0])
    _min_height(t.rows[0], 2.5)
    du.set_widths(t, [27.3])
    du.para(doc, space_after=4)


def _signatures(doc, ctx, size):
    t = doc.add_table(rows=4, cols=2)
    people = [("ผู้จัดทำ", ctx.get("prepared_by"), ctx.get("prepared_position")),
              ("ผู้อนุมัติ", ctx.get("approved_by"), ctx.get("approved_position"))]
    for c, (role, name, position) in enumerate(people):
        lines = ["", f"ลงชื่อ ........................................ {role}",
                 f"( {name or '........................................'} )",
                 f"ตำแหน่ง {position or '........................................'}"]
        for r, text in enumerate(lines):
            du.cell_text(t.cell(r, c), text, size, align="center")
    for row in t.rows:
        du.no_split(row)
        row.cells[0].paragraphs[0].paragraph_format.keep_with_next = True
        row.cells[1].paragraphs[0].paragraph_format.keep_with_next = True
