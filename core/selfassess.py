"""Online self-assessment: questions per requirement and the rating derived from the answers."""
import re

from core import standard

SCORES = {2: "ดำเนินการแล้ว มีหลักฐาน", 1: "ดำเนินการบางส่วน / อยู่ระหว่างดำเนินการ", 0: "ยังไม่ได้ดำเนินการ"}
MAX = 2

# Clause 4.2.1 written out in detail; every other requirement is generated from its audit guidance.
CUSTOM = {
    1: ["มีการกำหนดประเด็นภายในที่ส่งผลต่อความสามารถในการบรรลุผลของระบบการจัดการความปลอดภัยฯ "
        "(เช่น บุคลากร กระบวนการผลิต เครื่องจักร งบประมาณ วัฒนธรรมความปลอดภัย) หรือไม่",
        "มีการกำหนดประเด็นภายนอกที่ส่งผลต่อระบบการจัดการความปลอดภัยฯ "
        "(เช่น กฎหมาย เศรษฐกิจ ชุมชนโดยรอบ ผู้รับเหมา สภาพแวดล้อม/ภัยธรรมชาติ) หรือไม่",
        "ประเด็นภายในและภายนอกที่กำหนดมีความเกี่ยวข้องกับการดำเนินงานตามข้อกำหนดของมาตรฐาน "
        "(เช่น นำไปพิจารณาความเสี่ยงและโอกาส) หรือไม่"],
    2: ["มีการระบุผู้มีส่วนได้ส่วนเสียทั้งภายในและภายนอก (เช่น ลูกจ้าง คปอ. ผู้รับเหมา หน่วยงานราชการ ชุมชน) หรือไม่",
        "มีการกำหนดความต้องการและความคาดหวังของผู้มีส่วนได้ส่วนเสียแต่ละกลุ่มหรือไม่",
        "ความต้องการและความคาดหวังที่กำหนดมีความเกี่ยวข้องกับการดำเนินการตามมาตรฐาน "
        "(เช่น ระบุว่าข้อใดเป็นข้อกฎหมายหรือข้อกำหนดที่ต้องปฏิบัติ) หรือไม่"],
    3: ["มีการทบทวนสถานะเบื้องต้นของการจัดการด้านความปลอดภัยฯ เทียบกับข้อกำหนดของมาตรฐานหรือไม่",
        "การทบทวนสถานะเบื้องต้นครอบคลุมการปฏิบัติตามกฎหมายความปลอดภัย อาชีวอนามัย และสภาพแวดล้อมในการทำงาน "
        "และข้อกำหนดอื่น ๆ ที่เกี่ยวข้องหรือไม่",
        "มีหลักฐานผลการทบทวนสถานะเบื้องต้น (เช่น รายงาน รายการตรวจสอบกฎหมาย) หรือไม่"],
    4: ["มีการนำระบบการจัดการด้านความปลอดภัยฯ ที่กำหนดไว้ไปปฏิบัติจริงในการทำงานหรือไม่",
        "มีการติดตามว่าการดำเนินการตามระบบบรรลุผลตามที่กำหนด (ประสิทธิผล) เช่น ผลตามวัตถุประสงค์และตัวชี้วัด หรือไม่",
        "มีการพิจารณาการใช้ทรัพยากรในการดำเนินการตามระบบให้เหมาะสม (ประสิทธิภาพ) หรือไม่"],
}


def questions(item: dict) -> list[str]:
    if item["id"] in CUSTOM:
        return CUSTOM[item["id"]]
    out = []
    for line in (item.get("guidance") or "").split("\n"):
        line = re.sub(r"\(ความเห็น:.*?\)", "", line).strip().lstrip("-•").strip()
        if line:
            out.append(("มี" + line if line.startswith("การ") else line) + " หรือไม่")
    if not out:
        req = re.sub(r"^(\d+\)|[ก-ฮ]\.)\s*", "", item["requirement"].split("\n")[0]).strip()
        out.append(f"ดำเนินการตามข้อกำหนดนี้แล้วหรือไม่: {req}")
    return out


def scoped_items(scope: list[str]) -> list[dict]:
    codes = set(scope)
    return [i for i in standard.items() if i["subclause"] in codes]


def band(pct: float) -> tuple[str, str]:
    """(label, bootstrap colour) for a score percentage."""
    if pct >= 100:
        return "สอดคล้องครบถ้วน", "success"
    if pct >= 75:
        return "ดี", "primary"
    if pct >= 50:
        return "พอใช้", "warning"
    return "ต้องปรับปรุง", "danger"


def rate_item(item: dict, answers: dict) -> dict:
    """`answers` maps (item_id, question_index) -> score or None."""
    qs = questions(item)
    scores = [answers.get((item["id"], n)) for n in range(len(qs))]
    answered = [s for s in scores if s is not None]
    points = sum(answered)
    pct = 100 * points / (MAX * len(qs))
    if not answered:
        status = ""
    elif points == MAX * len(qs):
        status = "C"
    elif points == 0 and len(answered) == len(qs):
        status = "NS"
    else:
        status = "IP"
    return {"item": item, "questions": qs, "scores": scores, "answered": len(answered), "total": len(qs),
            "points": points, "max": MAX * len(qs), "pct": pct, "status": status}


def rate(scope: list[str], answers: dict) -> dict:
    rows = [rate_item(i, answers) for i in scoped_items(scope)]
    points, maximum = sum(r["points"] for r in rows), sum(r["max"] for r in rows)
    pct = 100 * points / maximum if maximum else 0.0
    subs = []
    for code in scope:
        sub_rows = [r for r in rows if r["item"]["subclause"] == code]
        if not sub_rows:
            continue
        sp = sum(r["points"] for r in sub_rows)
        sm = sum(r["max"] for r in sub_rows)
        subs.append({"code": code, "title": standard.subclause_title(code), "pct": 100 * sp / sm,
                     "conform": sum(r["status"] == "C" for r in sub_rows), "total": len(sub_rows),
                     "band": band(100 * sp / sm)})
    levels = []
    for lvl in standard.LEVELS:
        req = [r for r in rows if r["item"]["min_level"] <= lvl]
        ok = sum(r["status"] == "C" for r in req)
        levels.append({"level": lvl, "required": len(req), "conform": ok, "complete": bool(req) and ok == len(req)})
    ready = max((lv["level"] for lv in levels if lv["complete"]), default=0)
    full = {s["code"] for s in standard.subclauses()} <= set(scope)
    return {"full_scope": full,"rows": rows, "subs": subs, "levels": levels, "points": points, "max": maximum, "pct": pct,
            "band": band(pct), "conform": sum(r["status"] == "C" for r in rows), "total": len(rows),
            "answered": sum(r["answered"] for r in rows), "questions": sum(r["total"] for r in rows),
            "ready_level": ready}


def evidence_summary(row: dict, notes: dict) -> str:
    """Text written into the consultant's checklist when the self-assessment is applied to a round."""
    lines = ["[ประเมินตนเองออนไลน์]"]
    for n, (q, s) in enumerate(zip(row["questions"], row["scores"])):
        label = SCORES.get(s, "ไม่ได้ตอบ")
        note = notes.get((row["item"]["id"], n), "")
        lines.append(f"- {standard.short_text(q, 80)}: {label}" + (f" — {note}" if note else ""))
    return "\n".join(lines)
