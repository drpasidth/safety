"""Extract per-item results from a T-OSH consultant report PDF (Initial Review or Site Visit).

Usage: python tools/extract_report_sample.py "<report.pdf>" <out.json>

Each checklist row carries Wingdings check marks (U+F0FC). Every item is required at SC4,
so the SC4 marks give the 169 item rows in order; the result mark on the same row gives
the status and the ruled cell around it gives the evidence text.
"""
import json
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_checklist import clean  # noqa: E402

SC_X = [(262, 290), (291, 319), (320, 348), (349, 378)]
EVIDENCE_X = (378, 605)


def marks(page):
    out = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for ch in span["chars"]:
                    if ord(ch["c"]) == 0xF0FC:
                        x0, y0, x1, y1 = ch["bbox"]
                        out.append(((x0 + x1) / 2, (y0 + y1) / 2))
    return out


def h_lines(page):
    ys = set()
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l" and abs(it[1].y - it[2].y) < 1 and abs(it[1].x - it[2].x) > 40:
                ys.add(round(it[1].y, 1))
            elif it[0] == "re" and it[1].height < 2 and it[1].width > 40:
                ys.add(round(it[1].y0, 1))
    return sorted(ys)


def classify(x, site_visit):
    if site_visit:
        if x < 660:
            return "NC", "not_started"
        if x < 735:
            return "NC", "in_progress"
        return "C", "done"
    return ("NC", "") if x < 710 else ("C", "")


def evidence_text(page, top, bottom):
    words = [w for w in page.get_text("words")
             if EVIDENCE_X[0] <= w[0] < EVIDENCE_X[1] and top - 1 <= w[1] and w[3] <= bottom + 1]
    lines = {}
    for w in words:
        lines.setdefault(round(w[1] / 4), []).append(w)
    text = "\n".join(" ".join(clean(w[4]) for w in sorted(ws, key=lambda w: w[0]))
                     for _, ws in sorted(lines.items()))
    return text.strip()


def main(src, out):
    doc = pymupdf.open(src)
    full = "".join(clean(p.get_text()) for p in doc)
    site_visit = "ยังไม่ได้" in full[:20000] or "Site Visit" in full[:3000]
    results = []
    for page in doc:
        ms = marks(page)
        if not ms:
            continue
        lines = h_lines(page)
        header_bottom = next((w[3] for w in page.get_text("words") if w[4] == "SC4"), 0) + 2
        sc4 = sorted(y for x, y in ms if SC_X[3][0] <= x < SC_X[3][1])
        # text at top of page before the first item belongs to the previous item
        if results and sc4:
            first_top = max([l for l in lines if l <= sc4[0]] or [header_bottom])
            extra = evidence_text(page, header_bottom, first_top)
            if extra:
                results[-1]["evidence"] = (results[-1]["evidence"] + "\n" + extra).strip()
        for y in sc4:
            top = max([l for l in lines if l <= y - 3] or [header_bottom])
            bottom = min([l for l in lines if l >= y + 3] or [page.rect.height - 40])
            level = next(i + 1 for i, (a, b) in enumerate(SC_X)
                         if any(a <= mx < b and abs(my - y) < 6 for mx, my in ms))
            res = [mx for mx, my in ms if mx > 600 and top - 2 <= my <= bottom + 2]
            status, progress = classify(res[0], site_visit) if res else ("", "")
            results.append({"min_level": level, "status": status, "progress": progress,
                            "evidence": evidence_text(page, top, bottom)})
    print("rows:", len(results), "conform:", sum(r["status"] == "C" for r in results),
          "site_visit:", site_visit, file=sys.stderr)
    Path(out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
