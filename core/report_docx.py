"""Consultant reports in the T-OSH format: Initial Review and Site Visit."""
import io
import re
from pathlib import Path

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm

from core import scoring, standard, thaidate
from core import docx_utils as du
SECTION_FILL = "FFE699"
SUB_FILL = "E7E6E6"
HEAD_FILL = "BDD7EE"
CHECK = du.CHECK


def _numbering():
    n = 0

    def nxt():
        nonlocal n
        n += 1
        return n
    return nxt


def build_report(project: dict, rnd: dict, settings: dict) -> bytes:
    font, size, tsize = settings["font"], settings["font_size"], settings["table_font_size"]
    doc = du.new_document(font, size)
    logo = Path(settings["logo"]) if settings.get("logo") else None
    site_visit = rnd["type"] == "site_visit"
    prof = project["profile"]

    def chrome(sec):
        du.letterhead(sec, settings["org_lines"], logo, size)
        du.page_number_footer(sec, size)

    sec = doc.sections[0]
    du.letterhead(sec, settings["org_lines"], logo, size)
    _cover(doc, prof, rnd, settings, size)

    sec = du.new_section(doc, landscape=False)
    chrome(sec)
    du.para(doc, "สารบัญ", bold=True, size=size + 4, align="center", space_after=6)
    du.toc(doc, size)

    num = _numbering()
    if not site_visit:
        sec = du.new_section(doc, landscape=False)
        chrome(sec)
        du.para(doc, prof["name"], bold=True, size=size + 2, align="center", space_after=6)
        _profile_sections(doc, project, num, size, tsize)
        doc.add_heading(f"{num()}. สรุปผลการดำเนินงานปัจจุบันเปรียบเทียบกับข้อกำหนดระบบมาตรฐานความปลอดภัย "
                        "อาชีวอนามัย และสภาพแวดล้อมในการทำงาน", level=1)
    sec = du.new_section(doc, landscape=True)
    chrome(sec)
    if site_visit:
        du.para(doc, prof["name"], bold=True, size=size + 2, align="center", space_after=6)
        doc.add_heading(f"{num()}. รายละเอียดผลการดำเนินงานตามมาตรฐานระบบการจัดการความปลอดภัย "
                        "อาชีวอนามัย และสภาพแวดล้อมในการทำงาน", level=1)
    results_table(doc, rnd["results"], site_visit, tsize, with_guidance=False)

    sec = du.new_section(doc, landscape=False)
    chrome(sec)
    _result_sections(doc, project, rnd, num, size, tsize)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _cover(doc, prof, rnd, settings, size):
    for _ in range(4):
        du.para(doc)
    if rnd["type"] == "initial":
        title = "รายงานการทบทวนสถานะเริ่มต้น (Initial Review)"
        sub = "มาตรฐานระบบการจัดการความปลอดภัย อาชีวอนามัย และสภาพแวดล้อมในการทำงาน"
    else:
        n = rnd["visit_no"]
        title = f"รายงานการให้คำปรึกษาและตรวจติดตามสถานประกอบกิจการครั้งที่ {n} (Site Visit {n})"
        sub = ""
    du.para(doc, title, bold=True, size=size + 6, align="center", space_after=4)
    if sub:
        du.para(doc, sub, bold=True, size=size + 2, align="center")
    du.para(doc, settings["project_name"], bold=True, size=size + 2, align="center")
    du.para(doc, f"ประจำปี {settings['fiscal_year']}", bold=True, size=size + 2, align="center")
    for _ in range(5):
        du.para(doc)
    du.para(doc, prof["name"], bold=True, size=size + 6, align="center", space_after=4)
    du.para(doc, thaidate.long(rnd["date"]), bold=True, size=size + 2, align="center")
    for _ in range(5):
        du.para(doc)
    du.para(doc, "จัดทำโดย", bold=True, size=size + 2, align="center", space_after=4)
    for c in rnd["consultants"]:
        if c.get("name"):
            du.para(doc, f"ชื่อ {c['name']}    ตำแหน่ง {c.get('role', '')}", size=size + 2, align="center")


def _profile_sections(doc, project, num, size, tsize):
    prof = project["profile"]
    doc.add_heading(f"{num()}. ประเภทกิจการ/รายละเอียดของผู้ประสานงาน", level=1)
    lines = [
        ("ชื่อสถานประกอบกิจการ", prof["name"]),
        ("ชื่อสินค้า (ผลิตภัณฑ์) / บริการหลักของบริษัท", prof["product"]),
        ("ประเภทของสถานประกอบกิจการ", prof["business_type"]),
        ("สถานที่ตั้ง", prof["address"]),
    ]
    for label, value in lines:
        p = du.para(doc)
        du.run(p, f"{label} : ", bold=True)
        du.run(p, value or "-")
    du.para(doc, "รายละเอียดผู้ประสานงาน :", bold=True)
    for i, c in enumerate([c for c in prof["coordinators"] if c.get("name")], 1):
        du.para(doc, f"{i}. {c['name']} ตำแหน่ง {c.get('position', '')} เบอร์ {c.get('phone', '')}", indent_cm=0.6)
        if c.get("email"):
            du.para(doc, f"อีเมล {c['email']}", indent_cm=1.0)
    p = du.para(doc)
    du.run(p, "จำนวนพนักงาน : ", bold=True)
    du.run(p, f"{prof['employees'] or '-'} คน")
    o = prof["officers"]
    du.para(doc, "จำนวนเจ้าหน้าที่ความปลอดภัย :", bold=True)
    du.para(doc, f"- ระดับบริหาร {o.get('executive') or '-'} คน, ระดับหัวหน้างาน {o.get('supervisor') or '-'} คน, "
                 f"ระดับเทคนิค {o.get('technical') or '-'} คน, ระดับเทคนิคขั้นสูง {o.get('technical_adv') or '-'} คน, "
                 f"ระดับวิชาชีพ {o.get('professional') or '-'} คน", indent_cm=0.6)
    p = du.para(doc)
    du.run(p, "ระบบมาตรฐานที่ได้รับการรับรอง : ", bold=True)
    du.run(p, prof["certifications"] or "-")

    doc.add_heading(f"{num()}. ผลิตภาพของสถานประกอบกิจการ (Productivity)", level=1)
    pr = prof["productivity"]
    t = du.grid_table(doc, 2, 2)
    du.cell_text(t.cell(0, 0), "ผลิตภาพ (Productivity)", tsize, True, "center", HEAD_FILL)
    du.cell_text(t.cell(0, 1), f"จำนวน/ปี\n{pr.get('period', '')}".strip(), tsize, True, "center", HEAD_FILL)
    du.cell_text(t.cell(1, 0), f"{prof['name']}\n{pr.get('description', '')}".strip(), tsize)
    du.cell_text(t.cell(1, 1), pr.get("value", ""), tsize, align="center", valign="center")
    du.set_widths(t, [11, 6])

    for title, key in (("แผนผังกระบวนการผลิตของสถานประกอบกิจการ", "process_chart"),
                       ("โครงสร้างการบริหารงาน และหน้าที่ความรับผิดชอบของหน่วยงานต่าง ๆ ของสถานประกอบกิจการ", "org_chart")):
        doc.add_heading(f"{num()}. {title}", level=1)
        _image(doc, prof.get(key), Cm(16))

    doc.add_heading(f"{num()}. สถานะการดำเนินงานของสถานประกอบกิจการ", level=1)
    for title, key in (("จุดแข็ง", "strengths"), ("จุดอ่อน", "weaknesses")):
        du.para(doc, title, bold=True, indent_cm=0.6)
        for line in _lines(prof[key]):
            p = du.para(doc, f"-\t{line}", indent_cm=1.5)
            p.paragraph_format.first_line_indent = Cm(-0.5)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(1.5))

    doc.add_heading(f"{num()}. ขอบข่ายการขอรับรองในการจัดทำมาตรฐานระบบการจัดการด้านความปลอดภัย "
                    "อาชีวอนามัย และสภาพแวดล้อมในการทำงาน", level=1)
    du.para(doc, prof["scope"] or "-", indent_cm=0.6)


def _lines(text):
    return [ln.strip().lstrip("-•").strip() for ln in (text or "").splitlines() if ln.strip()]


def _image(container, path, width):
    if path and Path(path).exists():
        p = container.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(str(path), width=width)
    else:
        du.para(container, "(ไม่มีรูปภาพ)", align="center")


def results_table(doc, results, site_visit, tsize, with_guidance=False, show_results=True):
    """The 169-item table; also used by the checklist export with guidance instead of results."""
    status_cols = (["ยังไม่ได้\nดำเนินการ", "อยู่ระหว่าง\nดำเนินการ", "ดำเนินการ\nแล้ว"] if site_visit
                   else ["ไม่สอดคล้อง", "สอดคล้อง"])
    if not show_results:
        status_cols = []
    middle = "แนวทางสำหรับการตรวจประเมิน" if with_guidance else "ผลการตรวจประเมินตามข้อกำหนด\n(อธิบายการดำเนินงาน)"
    extra_cols = ["กฎกระทรวงฯ 65"] if with_guidance else []
    ncols = 2 + 4 + 1 + len(extra_cols) + len(status_cols)
    if with_guidance and show_results:
        ncols += 1
    t = du.grid_table(doc, 2, ncols)
    h0, h1 = t.rows[0], t.rows[1]
    du.repeat_header(h0)
    du.repeat_header(h1)

    def head(r, c, text, r2=None, c2=None):
        cell = t.cell(r, c) if r2 is None else t.cell(r, c).merge(t.cell(r2, c2))
        du.cell_text(cell, text, tsize, True, "center", HEAD_FILL, "center")

    head(0, 0, "ลำดับ\nที่", 1, 0)
    head(0, 1, "ข้อกำหนด", 1, 1)
    head(0, 2, "ระดับที่ต้องปฏิบัติ", 0, 5)
    for i in range(4):
        head(1, 2 + i, f"SC{i + 1}")
    col = 6
    head(0, col, middle, 1, col)
    col += 1
    for x in extra_cols:
        head(0, col, x, 1, col)
        col += 1
    if with_guidance and show_results:
        head(0, col, "บันทึก/หลักฐาน", 1, col)
        col += 1
    if status_cols:
        if site_visit:
            head(0, col, "ไม่สอดคล้อง", 0, col + 1)
            head(0, col + 2, "สอดคล้อง")
            for i, x in enumerate(status_cols):
                head(1, col + i, x)
        else:
            head(0, col, "ผลการตรวจประเมิน", 0, col + 1)
            for i, x in enumerate(status_cols):
                head(1, col + i, x)

    if with_guidance:
        widths = [1.2, 6.6, 0.75, 0.75, 0.75, 0.75, 6.2, 1.8] + ([4.0] if show_results else []) + \
                 [1.4] * len(status_cols)
    elif site_visit:
        widths = [1.2, 7.4, 0.8, 0.8, 0.8, 0.8, 9.6, 1.7, 1.7, 1.7]
    else:
        widths = [1.2, 7.6, 0.8, 0.8, 0.8, 0.8, 10.4, 2.1, 2.1]

    def full_row(text, fill, code=""):
        row = t.add_row()
        du.no_split(row)
        if code:
            du.cell_text(row.cells[0], code, tsize, True, fill=fill)
            merged = row.cells[1].merge(row.cells[-1])
        else:
            merged = row.cells[0].merge(row.cells[-1])
        du.cell_text(merged, text, tsize, bool(code) or fill == SECTION_FILL, fill=fill)
        if code:
            du.shade(merged, fill)

    item_texts = {i["requirement"] for i in standard.items()}
    last_sub, last_parent = None, None
    sec_titles = {s["code"]: s["title"] for s in standard.sections()}
    last_sec = None
    for item in standard.items():
        if item["section"] != last_sec:
            last_sec = item["section"]
            full_row(f"{last_sec} {sec_titles[last_sec]}", SECTION_FILL)
        if item["subclause"] != last_sub:
            last_sub = item["subclause"]
            sub = next(s for s in standard.subclauses() if s["code"] == last_sub)
            full_row(sub["title"], SUB_FILL, code=last_sub)
            if sub["intro"]:
                full_row(sub["intro"], "FFFFFF")
            last_parent = None
        parent = item.get("parent")
        if parent and parent != last_parent and parent not in item_texts:
            full_row(parent, "FFFFFF")
        last_parent = parent or last_parent
        row = t.add_row()
        cells = row.cells
        du.cell_text(cells[1], item["requirement"], tsize)
        for lvl in range(1, 5):
            du.cell_text(cells[1 + lvl], CHECK if item["min_level"] <= lvl else "", tsize, align="center")
        res = results.get(str(item["id"]), {})
        col = 6
        if with_guidance:
            du.cell_text(cells[col], item["guidance"], tsize)
            col += 1
            du.cell_text(cells[col], item["law_ref"], tsize, align="center")
            col += 1
            if show_results:
                du.cell_text(cells[col], res.get("evidence", ""), tsize)
                col += 1
        else:
            du.cell_text(cells[col], res.get("evidence", ""), tsize)
            col += 1
        status = res.get("status", "")
        if status_cols:
            marks = ({"NS": 0, "IP": 1, "C": 2} if site_visit else {"NS": 0, "IP": 0, "C": 1})
            for i in range(len(status_cols)):
                du.cell_text(cells[col + i], CHECK if marks.get(status) == i else "", tsize + 2,
                             align="center", valign="center")

    if not with_guidance:
        _totals(t, results, site_visit, tsize)
    du.set_widths(t, widths)
    return t


def _totals(t, results, site_visit, tsize):
    lc = standard.level_counts()
    ov = scoring.overall(results)
    row = t.add_row()
    du.no_split(row)
    du.cell_text(row.cells[0].merge(row.cells[1]), "รวมข้อกำหนด", tsize, True, "center", HEAD_FILL)
    for lvl in range(1, 5):
        du.cell_text(row.cells[1 + lvl], str(lc[lvl]), tsize - 3, True, "center", HEAD_FILL)
    du.cell_text(row.cells[6].merge(row.cells[-1]), "", tsize, fill=HEAD_FILL)

    row = t.add_row()
    du.no_split(row)
    du.cell_text(row.cells[0].merge(row.cells[6]), "ระบุจำนวนที่ได้ดำเนินการตามข้อกำหนด ---->>", tsize, True,
                 fill=HEAD_FILL)
    vals = ([ov["not_started"], ov["in_progress"], ov["conform"]] if site_visit
            else [ov["non_conform"], ov["conform"]])
    for i, v in enumerate(vals):
        du.cell_text(row.cells[7 + i], str(v), tsize, True, "center", HEAD_FILL)

    row = t.add_row()
    du.no_split(row)
    du.cell_text(row.cells[0].merge(row.cells[6]),
                 f"ร้อยละของข้อกำหนดที่ได้ดำเนินการแล้ว (จาก {ov['total']} ข้อกำหนด)", tsize, True, fill=HEAD_FILL)
    du.cell_text(row.cells[7].merge(row.cells[-1]), f"{ov['pct']:.2f}", tsize, True, "center", HEAD_FILL)


def _result_sections(doc, project, rnd, num, size, tsize):
    site_visit = rnd["type"] == "site_visit"
    ov = scoring.overall(rnd["results"])
    target = rnd.get("target_level") or 4
    rec = rnd.get("recommended_level")
    if rec is None:
        rec = scoring.suggested_level(rnd["results"])
    rec_txt = f"SC {rec}" if rec else "ยังไม่ถึงระดับ SC 1"

    if site_visit:
        n = num()
        doc.add_heading(f"{n}. ผลการติดตามครั้งที่ {rnd['visit_no']} (Site Visit {rnd['visit_no']})", level=1)
    else:
        n = num()
        doc.add_heading(f"{n}. ผลการทบทวนสถานะเริ่มต้น (Initial Review)", level=1)
    du.para(doc, f"{n}.1 ความคาดหวังที่ขอการรับรองของสถานประกอบกิจการ : ระดับ SC {target}", indent_cm=0.6)
    du.para(doc, f"{n}.2 ผลการติดตามของที่ปรึกษา เห็นควรพิจารณาให้การรับรองอยู่ในระดับ {rec_txt}", indent_cm=0.6)

    doc.add_heading(f"{num()}. สรุปผลการดำเนินงาน", level=1)
    nc_pct = 100 * ov["non_conform"] / ov["total"]
    if site_visit:
        text = (f"จากผลการติดตามครั้งที่ {rnd['visit_no']} พบว่า สถานประกอบกิจการมีการดำเนินการตามระบบความปลอดภัย "
                f"อาชีวอนามัยและสภาพแวดล้อมในการทำงานที่มีความสอดคล้องตามข้อกำหนด {ov['conform']} ข้อ "
                f"จาก {ov['total']} ข้อ คิดเป็นร้อยละ {ov['pct']:.2f} และมีการดำเนินการที่ยังไม่สอดคล้องตามข้อกำหนด "
                f"{ov['non_conform']} ข้อ หรือคิดเป็นร้อยละ {nc_pct:.2f} (โดยแยกเป็นข้อกำหนดที่อยู่ระหว่างดำเนินการ "
                f"{ov['in_progress']} ข้อ และข้อกำหนดที่ยังไม่ได้ดำเนินการ {ov['not_started']} ข้อ)")
    else:
        text = (f"จากผลการทบทวนสถานะเริ่มต้น พบว่า สถานประกอบกิจการได้มีการดำเนินงานตามข้อกำหนดของ "
                f"T-OSH OSHMS 2023 ในภาพรวมมีการดำเนินการตามข้อกำหนด {ov['conform']} ข้อ จาก {ov['total']} ข้อ "
                f"คิดเป็นร้อยละ {ov['pct']:.2f}")
    p = du.para(doc, text, align="justify")
    p.paragraph_format.first_line_indent = Cm(1.25)
    stats = scoring.by_level(rnd["results"])
    du.para(doc, "ความพร้อมรายระดับ: " + ", ".join(
        f"SC{s.level} {s.conform}/{s.required} ข้อ ({s.pct:.1f}%)" for s in stats), indent_cm=0.6)
    if rnd.get("summary_note"):
        p = du.para(doc, rnd["summary_note"], align="justify")
        p.paragraph_format.first_line_indent = Cm(1.25)

    doc.add_heading(f"{num()}. ข้อเสนอแนะปรับปรุงในขอบเขตของมาตรฐานระบบการจัดการความปลอดภัย "
                    "อาชีวอนามัย และสภาพแวดล้อมในการทำงาน", level=1)
    _findings(doc, rnd, site_visit, tsize)

    if site_visit:
        doc.add_heading(f"{num()}. ปัญหาอุปสรรคและข้อเสนอแนะ", level=1)
        p = du.para(doc, rnd.get("problems") or "-", align="justify")
        p.paragraph_format.first_line_indent = Cm(1.25)
        doc.add_heading(f"{num()}. การมอบหมายงาน", level=1)
        du.para(doc, "หัวหน้าที่ปรึกษา/ที่ปรึกษา ขอมอบหมายทีมงานได้ดำเนินการจัดทำขั้นตอนการดำเนินงาน และเอกสาร"
                     "เพื่อเตรียมการตรวจประเมินระดับ ดังนี้", indent_cm=0.6)
    else:
        doc.add_heading(f"{num()}. สิ่งที่มอบหมายให้สถานประกอบกิจการดำเนินการ", level=1)
    _assignments(doc, rnd, tsize)

    if rnd.get("next_visit") or not site_visit:
        doc.add_heading(f"{num()}. การนัดหมายเพื่อเข้าตรวจเยี่ยมและให้คำปรึกษาครั้งถัดไป", level=1)
        du.para(doc, thaidate.long(rnd.get("next_visit")) or "-", indent_cm=1.25)

    doc.add_heading(f"{num()}. ที่ปรึกษาผู้รับผิดชอบ", level=1)
    people = [c for c in rnd["consultants"] if c.get("name")]
    for c in people:
        du.para(doc, f"{c.get('role', '')} : {c['name']}", indent_cm=0.6)
    for c in people:
        for p in (du.para(doc), du.para(doc),
                  du.para(doc, f"ลงชื่อ ........................................ {c.get('role', '')}", align="right")):
            p.paragraph_format.keep_with_next = True
        du.para(doc, f"( {c['name']} )", align="right")


def _findings(doc, rnd, site_visit, tsize):
    findings = rnd.get("findings", [])
    cols = ["รูปภาพ (ถ้ามี)", "คำอธิบาย\n(ประเด็นที่ไม่สอดคล้อง)", "ข้อเสนอแนะในการปรับปรุงแก้ไข"]
    widths = [5.6, 5.2, 6.2]
    if site_visit:
        cols.append("สถานะการแก้ไข")
        widths = [5.0, 4.6, 5.0, 2.4]
    t = du.grid_table(doc, 1, len(cols))
    du.repeat_header(t.rows[0])
    for i, c in enumerate(cols):
        du.cell_text(t.cell(0, i), c, tsize, True, "center", HEAD_FILL, "center")
    if not findings:
        row = t.add_row()
        du.cell_text(row.cells[0].merge(row.cells[-1]), "ไม่พบประเด็นที่ต้องปรับปรุงเพิ่มเติม", tsize, align="center")
    for f in findings:
        row = t.add_row()
        cell = row.cells[0]
        cell.text = ""
        photos = [Path(p) for p in f.get("photos", []) if p and Path(p).exists()]
        for i, ph in enumerate(photos):
            p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(ph), width=Cm(widths[0] - 0.6))
        desc = f.get("description", "")
        if f.get("location"):
            desc = f"{f['location']}\n{desc}"
        du.cell_text(row.cells[1], desc, tsize)
        du.cell_text(row.cells[2], f.get("recommendation", ""), tsize)
        if site_visit:
            du.cell_text(row.cells[3], FOLLOWUP.get(f.get("followup", ""), ""), tsize, align="center")
    du.set_widths(t, widths)


FOLLOWUP = {"": "", "pending": "รอดำเนินการ", "in_progress": "กำลังดำเนินการ", "done": "ดำเนินการแก้ไขแล้ว"}


def _assignments(doc, rnd, tsize):
    rows = [a for a in rnd.get("assignments", []) if a.get("clause") or a.get("task")]
    t = du.grid_table(doc, 1, 2)
    du.repeat_header(t.rows[0])
    du.cell_text(t.cell(0, 0), "ข้อกำหนด", tsize, True, "center", HEAD_FILL)
    du.cell_text(t.cell(0, 1), "สิ่งที่มอบหมาย", tsize, True, "center", HEAD_FILL)
    if not rows:
        row = t.add_row()
        du.cell_text(row.cells[0].merge(row.cells[1]), "-", tsize, align="center")
    for a in rows:
        row = t.add_row()
        du.cell_text(row.cells[0], a.get("clause", ""), tsize)
        du.cell_text(row.cells[1], a.get("task", ""), tsize)
    du.set_widths(t, [4.5, 12.5])


def default_assignments(results: dict) -> list[dict]:
    out = []
    for item in scoring.non_conforming(results):
        task = re.sub(r"^(\d+\)|[ก-ฮ]\.|-)\s*", "", item["requirement"].split("\n")[0])
        task = task.replace("นายจ้างต้อง", "").strip()
        out.append({"clause": item["label"], "task": "ดำเนินการ" + standard.short_text(task, 160)})
    return out
