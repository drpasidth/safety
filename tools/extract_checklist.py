"""Build data/requirements.json from the T-OSH OSHMS 2023 checklist PDF.

Run once: python tools/extract_checklist.py
"""
import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "checklist T-OSH OSHMS 2023 (2).pdf"
OUT = ROOT / "data" / "requirements.json"

PUA = {
    0xF700: "ฐ", 0xF701: "ิ", 0xF702: "ี", 0xF703: "ึ", 0xF704: "ื",
    0xF705: "่", 0xF706: "้", 0xF707: "๊", 0xF708: "๋", 0xF709: "์",
    0xF70A: "่", 0xF70B: "้", 0xF70C: "๊", 0xF70D: "๋", 0xF70E: "์",
    0xF70F: "ญ", 0xF710: "ั", 0xF711: "ํ", 0xF712: "็",
    0xF713: "่", 0xF714: "้", 0xF715: "๊", 0xF716: "๋", 0xF717: "์",
    0xF718: "ุ", 0xF719: "ู", 0xF71A: "ฺ",
}


# Cells where the PDF text overflows into neighbouring rows; wording taken from the standard.
ITEM_PATCHES = {
    12: {"requirement": "3) นายจ้างต้องให้ลูกจ้างมีส่วนร่วมในการกำหนดนโยบายด้านความปลอดภัย อาชีวอนามัย และสภาพแวดล้อมในการทำงาน"},
    16: {"requirement": "ก. วิธีการทำงาน (รวมถึงภาระงาน ชั่วโมงทำงาน การเป็นเหยื่อ การข่มขู่ การข่มเหงรังแก) ความเป็นผู้นำ วัฒนธรรมและค่านิยมความปลอดภัยในสถานประกอบกิจการ"},
    27: {"requirement": "4) วิธีการในการกำหนดมาตรการควบคุมความเสี่ยง ควรพิจารณามาตรการเพื่อลดความเสี่ยง ดังนี้\nก. การขจัดอันตราย\nข. การทดแทน\nค. การควบคุมทางวิศวกรรม\nง. การควบคุมเชิงบริหารจัดการ\nจ. อุปกรณ์คุ้มครองความปลอดภัยส่วนบุคคล"},
    32: {"requirement": "นายจ้างต้องกำหนดแนวทาง ดำเนินงาน และการกำกับดูแลกระบวนการในการชี้บ่งและการประเมินความเสี่ยงและโอกาสที่มีผลระบบการจัดการความปลอดภัย อาชีวอนามัย และสภาพแวดล้อมในการทำงานครอบคลุมถึงบริบทและนโยบายของสถานประกอบกิจการ รวมทั้งกฎหมายความปลอดภัย อาชีวอนามัย และสภาพแวดล้อมในการทำงาน และข้อกำหนดอื่น ๆ ที่เกี่ยวข้อง ที่ส่งผลต่อการดำเนินงาน และการกำกับดูแลระบบการจัดการความปลอดภัย อาชีวอนามัย และสภาพแวดล้อมในการทำงาน"},
    49: {"requirement": "3) นายจ้างต้องกำหนดให้มีการติดตามและประเมินผลการดำเนินการตามแผนงานอย่างสม่ำเสมอเพื่อให้บรรลุตามวัตถุประสงค์และแผนงาน พร้อมทั้งปรับเปลี่ยนให้ทันสมัยและเหมาะสม และนำผลการประเมินไปปรับปรุงแผนงานด้านความปลอดภัย อาชีวอนามัย และสภาพแวดล้อมในการทำงาน"},
    50: {"requirement": "นายจ้างต้องจัดทำและเก็บบันทึกที่เกี่ยวข้อง", "guidance": "-การจัดทำและเก็บบันทึกที่เกี่ยวข้อง"},
}
INTRO_PATCHES = {
    "4.3.1": "",
    "4.6.1": "นายจ้างต้องจัดทำระเบียบปฏิบัติ การดำเนินงาน และกำกับดูแลการสอบสวนและวิเคราะห์หาสาเหตุที่แท้จริงของการเกิดอุบัติการณ์ อุบัติเหตุ เหตุการณ์เกือบเป็นอุบัติเหตุ การเจ็บป่วย โรคจากการทำงาน หรือความเสียหายต่อทรัพย์สิน ดังนี้",
    "4.6.2": "นายจ้างต้องจัดทำระเบียบปฏิบัติ การดำเนินงาน และกำกับดูแลสำหรับการแก้ไข การดำเนินการแก้ไขข้อบกพร่องที่เกิดขึ้นและการดำเนินการป้องกันแนวโน้มความบกพร่องที่อาจจะเกิดขึ้น ดังนี้",
    "4.6.3": "นายจ้างต้องปรับปรุงและพัฒนาระบบการจัดการความปลอดภัย อาชีวอนามัย และสภาพแวดล้อมในการทำงานอย่างต่อเนื่อง ตามความเหมาะสม โดยนำผลการดำเนินการตามระบบการจัดการด้านความปลอดภัยของสถานประกอบกิจการมาวิเคราะห์หาสาเหตุของข้อบกพร่องและแนวโน้มที่จะเกิดข้อบกพร่อง โดย",
}
PARENT_PATCHES = {}


def clean(text: str) -> str:
    if not text:
        return ""
    text = text.translate(PUA)
    # "ก าหนด" -> "กำหนด": sara am is extracted as nikhahit-less space + sara aa
    text = re.sub(r"([ก-ฮ][่-๋]?) า", r"\1ำ", text)
    text = text.replace("ํา", "ำ")
    lines = [ln.strip() for ln in text.splitlines()]
    out = ""
    for ln in lines:
        if not ln:
            continue
        if not out:
            out = ln
        elif ln.startswith("-") or re.match(r"^[ก-ฮ]\.\s", ln) or re.match(r"^\d+\)", ln):
            out += "\n" + ln
        elif re.match(r"^[A-Za-z0-9(]", ln) or out[-1:].isascii():
            out += " " + ln
        else:
            out += ln
    return re.sub(r"[ \t]+", " ", out).strip()


def cell_text(page, rect) -> str:
    if rect is None:
        return ""
    return clean(page.get_textbox(pymupdf.Rect(rect)))


CACHE = ROOT / "tools" / "_rows_cache.json"


def read_rows():
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    doc = pymupdf.open(SRC)
    rows = []
    for page in doc:
        for tab in page.find_tables().tables:
            for row in tab.rows:
                cells = list(row.cells) + [None] * (8 - len(row.cells))
                rows.append([cell_text(page, c) for c in cells[:8]])
    CACHE.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def main():
    rows = read_rows()

    sections, items = [], []
    section = subclause = None
    parent = None
    last = None
    for clause, req, guide, law, *marks in rows:
        if clause.startswith("รวม"):
            break
        if clause.startswith("ข้อกำหนด") and "TOSH" not in clause and "รายละเอียด" not in clause:
            m = re.match(r"ข้อกำหนด\s*(4\.\d)\s*(.*)", clause)
            if m:
                section = {"code": m.group(1), "title": m.group(2).strip(), "subclauses": []}
                sections.append(section)
                continue
        if clause in ("ข้อกำหนด", "") and req.startswith("รายละเอียด"):
            continue
        if "SC1" in marks:
            continue
        if re.fullmatch(r"4\.\d\.\d+", clause):
            subclause = {"code": clause, "title": req, "intro": ""}
            section["subclauses"].append(subclause)
            parent = None
            last = None
            continue
        has_marks = any(m.strip() for m in marks)
        is_sub = bool(re.match(r"^([ก-ฮ]\.|-)", req))
        if not has_marks:
            if req:
                if re.match(r"^\d+\)", req) or not any(i["subclause"] == subclause["code"] for i in items):
                    parent = req
                if not re.match(r"^\d+\)", req) and not subclause["intro"]:
                    subclause["intro"] = req
                last = None
            elif last is not None and guide:
                last["guidance"] += "\n" + guide
            continue
        if re.match(r"^\d+\)", req):
            parent = req
        first_sc = next(i + 1 for i, m in enumerate(marks) if m.strip())
        item = {
            "id": len(items) + 1,
            "section": section["code"],
            "subclause": subclause["code"],
            "parent": parent if is_sub else None,
            "requirement": req or (last["requirement"] if last else ""),
            "guidance": guide,
            "law_ref": law,
            "min_level": first_sc,
        }
        items.append(item)
        last = item

    by_id = {i["id"]: i for i in items}
    for item_id, fields in ITEM_PATCHES.items():
        by_id[item_id].update(fields)
    subs = {s["code"]: s for sec in sections for s in sec["subclauses"]}
    for code, intro in INTRO_PATCHES.items():
        subs[code]["intro"] = intro
    for item in items:
        if item["parent"] in PARENT_PATCHES:
            item["parent"] = PARENT_PATCHES[item["parent"]]

    by_level = {lvl: sum(1 for i in items if i["min_level"] <= lvl) for lvl in range(1, 5)}
    print("items:", len(items), "by level:", by_level, file=sys.stderr)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps({"standard": "T-OSH OSHMS:2023", "sections": sections, "items": items},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
