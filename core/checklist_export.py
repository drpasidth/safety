"""Checklist outputs: Excel workbook and printable Word checklist."""
import io
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from core import scoring, standard, thaidate
from core import docx_utils as du
from core.report_docx import results_table

THIN = Side(style="thin", color="808080")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def build_xlsx(project: dict | None, rnd: dict | None, font: str = "TH SarabunPSK") -> bytes:
    results = rnd["results"] if rnd else {}
    wb = Workbook()
    ws = wb.active
    ws.title = "Checklist"
    base = Font(name=font, size=14)
    bold = Font(name=font, size=14, bold=True)
    title = Font(name=font, size=18, bold=True)

    ws["A1"] = "Checklist ข้อกำหนดระบบการจัดการด้านความปลอดภัยฯ (T-OSH OSHMS:2023) เทียบ กฎกระทรวงกำหนดมาตรฐานเกี่ยวกับระบบการจัดการด้านความปลอดภัยฯ 2565"
    ws["A1"].font = title
    info = []
    if project:
        info.append(f"สถานประกอบกิจการ: {project['profile']['name']}")
    if rnd:
        kind = "Initial Review" if rnd["type"] == "initial" else f"Site Visit ครั้งที่ {rnd['visit_no']}"
        info.append(f"รอบการตรวจ: {kind}  วันที่ {thaidate.short(rnd['date'])}  ระดับที่คาดหวัง SC{rnd.get('target_level', 4)}")
    ws["A2"] = "    ".join(info)
    ws["A2"].font = base

    headers = ["ลำดับ", "ข้อกำหนด", "รายละเอียดข้อกำหนด TOSH-OSHMS:2023", "แนวทางสำหรับการตรวจประเมิน",
               "กฎกระทรวงการจัดการฯ 65", "SC1", "SC2", "SC3", "SC4", "ผลการตรวจประเมิน", "หลักฐาน / บันทึกการตรวจ"]
    widths = [7, 10, 60, 55, 14, 6, 6, 6, 6, 24, 60]
    hr = 4
    for c, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(hr, c, h)
        cell.font, cell.alignment, cell.border = bold, CENTER, BORDER
        cell.fill = PatternFill("solid", fgColor="BDD7EE")
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = ws.cell(hr + 1, 3)

    dv = DataValidation(type="list", formula1='"' + ",".join(standard.STATUS_SHORT[s] for s in ("C", "IP", "NS")) + '"',
                        allow_blank=True)
    ws.add_data_validation(dv)

    sec_titles = {s["code"]: s["title"] for s in standard.sections()}
    r = hr + 1
    last_sec = last_sub = None
    for item in standard.items():
        if item["section"] != last_sec:
            last_sec = item["section"]
            _band(ws, r, f"ข้อกำหนด {last_sec} {sec_titles[last_sec]}", "FFE699", bold, len(headers))
            r += 1
        if item["subclause"] != last_sub:
            last_sub = item["subclause"]
            _band(ws, r, f"{last_sub}  {standard.subclause_title(last_sub)}", "E7E6E6", bold, len(headers))
            r += 1
        res = results.get(str(item["id"]), {})
        requirement = item["requirement"]
        if item.get("parent"):
            requirement = f"{item['parent']}\n{requirement}"
        row = [item["id"], item["subclause"], requirement, item["guidance"], item["law_ref"],
               *["✓" if item["min_level"] <= lvl else "" for lvl in standard.LEVELS],
               standard.STATUS_SHORT[res.get("status", "")] if res.get("status") else "",
               res.get("evidence", "")]
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v)
            cell.font, cell.border = base, BORDER
            cell.alignment = CENTER if c in (1, 2, 5, 6, 7, 8, 9, 10) else WRAP
        dv.add(ws.cell(r, 10))
        r += 1

    lc = standard.level_counts()
    _band(ws, r, "รวมข้อกำหนด", "BDD7EE", bold, 5)
    for i, lvl in enumerate(standard.LEVELS):
        cell = ws.cell(r, 6 + i, lc[lvl])
        cell.font, cell.alignment, cell.border = bold, CENTER, BORDER
    ws.print_title_rows = f"{hr}:{hr}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    if rnd:
        _summary_sheet(wb, rnd, base, bold)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _band(ws, r, text, fill, font, ncols):
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
    cell = ws.cell(r, 1, text)
    cell.font, cell.fill = font, PatternFill("solid", fgColor=fill)
    cell.alignment = Alignment(vertical="center", wrap_text=True)
    for c in range(1, ncols + 1):
        ws.cell(r, c).border = BORDER


def _summary_sheet(wb, rnd, base, bold):
    ws = wb.create_sheet("สรุปผล")
    ov = scoring.overall(rnd["results"])
    rows = [("รายการ", "จำนวน"), ("ข้อกำหนดทั้งหมด", ov["total"]), ("สอดคล้อง/ดำเนินการแล้ว", ov["conform"]),
            ("อยู่ระหว่างดำเนินการ", ov["in_progress"]), ("ยังไม่ได้ดำเนินการ", ov["not_started"]),
            ("ยังไม่ประเมิน", ov["unassessed"]), ("ร้อยละที่ดำเนินการแล้ว", ov["pct"]), ("", ""),
            ("ระดับ", "สอดคล้อง / ที่ต้องปฏิบัติ")]
    rows += [(f"SC{s.level}", f"{s.conform} / {s.required} ({s.pct:.1f}%)") for s in scoring.by_level(rnd["results"])]
    rows += [("", ""), ("ข้อกำหนดย่อย", "สอดคล้อง / ทั้งหมด")]
    rows += [(f"{s['code']} {s['title']}", f"{s['conform']} / {s['total']}") for s in scoring.by_subclause(rnd["results"])]
    for r, (a, b) in enumerate(rows, 1):
        ws.cell(r, 1, a).font = bold if r == 1 or a in ("ระดับ", "ข้อกำหนดย่อย") else base
        ws.cell(r, 2, b).font = base
    ws.column_dimensions["A"].width = 70
    ws.column_dimensions["B"].width = 28


def build_checklist_docx(project: dict | None, rnd: dict | None, settings: dict, with_results: bool) -> bytes:
    doc = du.new_document(settings["font"], settings["font_size"])
    sec = doc.sections[0]
    from docx.enum.section import WD_ORIENT
    from docx.shared import Cm
    sec.orientation, sec.page_width, sec.page_height = WD_ORIENT.LANDSCAPE, Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(1.2)
    logo = Path(settings["logo"]) if settings.get("logo") else None
    du.letterhead(sec, settings["org_lines"], logo, settings["font_size"])
    du.page_number_footer(sec, settings["font_size"])
    du.para(doc, "ข้อกำหนดระบบการจัดการด้านความปลอดภัยฯ (TOSH-OSHMS:2023) เทียบ กฎกระทรวงกำหนดมาตรฐาน"
                 "เกี่ยวกับระบบการจัดการด้านความปลอดภัยฯ 2565", bold=True, align="center")
    line = []
    if project:
        line.append(f"สถานประกอบกิจการ: {project['profile']['name']}")
    if rnd:
        line.append(f"วันที่ตรวจ: {thaidate.short(rnd['date'])}")
    else:
        line.append("สถานประกอบกิจการ: ........................................  วันที่ตรวจ: ....................")
    du.para(doc, "    ".join(line), align="center", space_after=4)
    results = rnd["results"] if (rnd and with_results) else {}
    results_table(doc, results, site_visit=bool(rnd and rnd["type"] == "site_visit"),
                  tsize=settings["table_font_size"] - 1, with_guidance=True, show_results=True)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
