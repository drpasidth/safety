"""Bridge between the Django models and the framework-free code in `core/`."""
from django.db import transaction

from core import checklist_export, pdf, report_docx, scoring

from .models import AssessmentRound, Assignment, Establishment, Finding, FindingPhoto, ReportSettings, Result


def _path(field) -> str:
    return field.path if field else ""


def results_dict(rnd: AssessmentRound) -> dict:
    return {str(r.item_id): {"status": r.status, "evidence": r.evidence} for r in rnd.results.all()}


def project_dict(est: Establishment) -> dict:
    return {
        "id": est.pk,
        "profile": {
            "name": est.name, "product": est.product, "business_type": est.business_type, "address": est.address,
            "coordinators": [{"name": c.name, "position": c.position, "phone": c.phone, "email": c.email}
                             for c in est.coordinators.all()],
            "employees": est.employees,
            "officers": {"executive": est.officers_executive, "supervisor": est.officers_supervisor,
                         "technical": est.officers_technical, "technical_adv": est.officers_technical_adv,
                         "professional": est.officers_professional},
            "certifications": est.certifications,
            "productivity": {"description": est.productivity_description, "value": est.productivity_value,
                             "period": est.productivity_period},
            "process_chart": _path(est.process_chart), "org_chart": _path(est.org_chart),
            "strengths": est.strengths, "weaknesses": est.weaknesses, "scope": est.scope,
        },
    }


def round_dict(rnd: AssessmentRound) -> dict:
    return {
        "id": rnd.pk, "type": rnd.kind, "visit_no": rnd.visit_no, "date": rnd.date.isoformat(),
        "consultants": [{"name": c.name, "role": c.role} for c in rnd.consultants.all()],
        "target_level": rnd.target_level, "recommended_level": rnd.recommended_level,
        "results": results_dict(rnd),
        "findings": [{"location": f.location, "description": f.description, "recommendation": f.recommendation,
                      "followup": f.followup, "photos": [_path(p.image) for p in f.photos.all()]}
                     for f in rnd.findings.all()],
        "assignments": [{"clause": a.clause, "task": a.task} for a in rnd.assignments.all()],
        "next_visit": rnd.next_visit.isoformat() if rnd.next_visit else "",
        "problems": rnd.problems, "summary_note": rnd.summary_note,
    }


def settings_dict() -> dict:
    s = ReportSettings.load()
    return {"org_lines": [x.strip() for x in s.org_lines.splitlines() if x.strip()], "logo": _path(s.logo),
            "project_name": s.project_name, "fiscal_year": s.fiscal_year, "font": s.font,
            "font_size": s.font_size, "table_font_size": s.table_font_size}


def effective_level(rnd: AssessmentRound, results: dict) -> tuple[int, bool]:
    """(level, chosen_by_consultant)."""
    if rnd.recommended_level is not None:
        return rnd.recommended_level, True
    return scoring.suggested_level(results), False


def save_results(rnd: AssessmentRound, updates: dict[int, dict]) -> None:
    existing = {r.item_id: r for r in rnd.results.filter(item_id__in=updates)}
    with transaction.atomic():
        for item_id, values in updates.items():
            obj = existing.get(item_id) or Result(round=rnd, item_id=item_id)
            for k, v in values.items():
                setattr(obj, k, v)
            obj.save()


@transaction.atomic
def copy_from(rnd: AssessmentRound, prev: AssessmentRound, results: bool, findings: bool) -> None:
    if results:
        Result.objects.bulk_create([Result(round=rnd, item_id=r.item_id, status=r.status, evidence=r.evidence)
                                    for r in prev.results.all()])
    if findings:
        copy_findings(rnd, prev)


@transaction.atomic
def copy_findings(rnd: AssessmentRound, prev: AssessmentRound) -> int:
    start = rnd.findings.count()
    n = 0
    for n, f in enumerate(prev.findings.all(), 1):
        new = Finding.objects.create(round=rnd, order=start + n, location=f.location, description=f.description,
                                     recommendation=f.recommendation, followup="pending")
        FindingPhoto.objects.bulk_create([FindingPhoto(finding=new, image=p.image.name, order=p.order)
                                          for p in f.photos.all()])
    return n


@transaction.atomic
def generate_assignments(rnd: AssessmentRound) -> int:
    rows = report_docx.default_assignments(results_dict(rnd))
    rnd.assignments.all().delete()
    Assignment.objects.bulk_create([Assignment(round=rnd, order=i, **row) for i, row in enumerate(rows)])
    return len(rows)


def build_report(rnd: AssessmentRound, as_pdf: bool) -> bytes:
    data = report_docx.build_report(project_dict(rnd.establishment), round_dict(rnd), settings_dict())
    if as_pdf:
        return pdf.docx_to_pdf(data)
    return pdf.update_docx_fields(data) if pdf.word_available() else data


def build_checklist(rnd: AssessmentRound | None, fmt: str) -> bytes:
    s = settings_dict()
    project = project_dict(rnd.establishment) if rnd else None
    rd = round_dict(rnd) if rnd else None
    if fmt == "xlsx":
        return checklist_export.build_xlsx(project, rd, s["font"])
    data = checklist_export.build_checklist_docx(project, rd, s, with_results=rnd is not None)
    return pdf.docx_to_pdf(data) if fmt == "pdf" else data
