"""T-OSH OSHMS:2023 requirement catalogue (169 items, SC1-SC4)."""
import json
import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LEVELS = (1, 2, 3, 4)

STATUS_LABELS = {
    "C": "สอดคล้อง / ดำเนินการแล้ว",
    "IP": "อยู่ระหว่างดำเนินการ",
    "NS": "ไม่พบ / ยังไม่ได้ดำเนินการ",
}
STATUS_SHORT = {"C": "สอดคล้อง", "IP": "อยู่ระหว่างดำเนินการ", "NS": "ยังไม่ได้ดำเนินการ", "": "ยังไม่ประเมิน"}
CONFORM = {"C"}

ROUND_TYPES = {
    "initial": "ทบทวนสถานะเริ่มต้น (Initial Review)",
    "site_visit": "ให้คำปรึกษาและตรวจติดตาม (Site Visit)",
}


@lru_cache(maxsize=1)
def catalogue() -> dict:
    data = json.loads((DATA_DIR / "requirements.json").read_text(encoding="utf-8"))
    for item in data["items"]:
        item["label"] = _label(item)
    return data


def items() -> list[dict]:
    return catalogue()["items"]


def sections() -> list[dict]:
    return catalogue()["sections"]


def subclauses() -> list[dict]:
    return [sub | {"section": sec["code"]} for sec in sections() for sub in sec["subclauses"]]


def subclause_title(code: str) -> str:
    return next(s["title"] for s in subclauses() if s["code"] == code)


def items_for_level(level: int) -> list[dict]:
    return [i for i in items() if i["min_level"] <= level]


def level_counts() -> dict[int, int]:
    return {lvl: len(items_for_level(lvl)) for lvl in LEVELS}


def _label(item: dict) -> str:
    """Short reference used in reports, e.g. '4.3.1 ข้อ 2 (ก)'."""
    req, parent = item["requirement"], item.get("parent") or ""
    num = re.match(r"^(\d+)\)", req) or re.match(r"^(\d+)\)", parent)
    letter = re.match(r"^([ก-ฮ])\.", req)
    out = item["subclause"]
    if num:
        out += f" ข้อ {num.group(1)}"
    if letter:
        out += f" ({letter.group(1)})"
    if req.startswith("นายจ้างต้องจัดทำและเก็บบันทึก"):
        out += " (บันทึก)"
    return out


def short_text(text: str, limit: int = 120) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
