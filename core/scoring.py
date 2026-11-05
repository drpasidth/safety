"""Compliance statistics for an assessment round."""
from dataclasses import dataclass

from core import standard


@dataclass
class LevelStat:
    level: int
    required: int
    conform: int

    @property
    def pct(self) -> float:
        return 100 * self.conform / self.required if self.required else 0.0

    @property
    def missing(self) -> int:
        return self.required - self.conform

    @property
    def complete(self) -> bool:
        return self.conform == self.required


def status_of(results: dict, item_id: int) -> str:
    return results.get(str(item_id), {}).get("status", "")


def counts(results: dict, items=None) -> dict[str, int]:
    items = standard.items() if items is None else items
    out = {"C": 0, "IP": 0, "NS": 0, "": 0}
    for item in items:
        out[status_of(results, item["id"])] += 1
    return out


def overall(results: dict) -> dict:
    total = len(standard.items())
    c = counts(results)
    conform = c["C"]
    return {
        "total": total,
        "conform": conform,
        "non_conform": c["IP"] + c["NS"],
        "in_progress": c["IP"],
        "not_started": c["NS"],
        "unassessed": c[""],
        "pct": round(100 * conform / total, 2) if total else 0.0,
    }


def by_level(results: dict) -> list[LevelStat]:
    return [
        LevelStat(lvl, len(its), sum(status_of(results, i["id"]) == "C" for i in its))
        for lvl in standard.LEVELS
        for its in [standard.items_for_level(lvl)]
    ]


def suggested_level(results: dict) -> int:
    """Highest SC level whose required items are all conforming (0 = below SC1)."""
    best = 0
    for stat in by_level(results):
        if not stat.complete:
            break
        best = stat.level
    return best


def by_subclause(results: dict) -> list[dict]:
    rows = []
    for sub in standard.subclauses():
        its = [i for i in standard.items() if i["subclause"] == sub["code"]]
        c = counts(results, its)
        rows.append({
            "section": sub["section"], "code": sub["code"], "title": sub["title"],
            "total": len(its), "conform": c["C"], "in_progress": c["IP"],
            "not_started": c["NS"], "unassessed": c[""],
            "pct": round(100 * c["C"] / len(its), 1) if its else 0.0,
        })
    return rows


def non_conforming(results: dict) -> list[dict]:
    return [i for i in standard.items() if status_of(results, i["id"]) in ("IP", "NS")]
