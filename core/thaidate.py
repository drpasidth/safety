from datetime import date

MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
          "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]


def parse(value) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def long(value) -> str:
    d = parse(value)
    return f"วันที่ {d.day} เดือน {MONTHS[d.month - 1]} พ.ศ. {d.year + 543}" if d else ""


def short(value) -> str:
    d = parse(value)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year + 543}" if d else ""
