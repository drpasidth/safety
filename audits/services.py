"""Bridge between the Django models and the framework-free code in `core/`."""
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core import checklist_export, context_docx, pdf, report_docx, scoring

from .models import (EXTERNAL, INTERNAL, AssessmentRound, Assignment, ContextAnalysis, ContextIssue, Establishment,
                     Finding, FindingPhoto, InterestedParty, ReportSettings, Result)


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
    return pdf.update_docx_fields(data)


def context_of(est: Establishment) -> ContextAnalysis:
    obj, _ = ContextAnalysis.objects.get_or_create(establishment=est)
    return obj


def enable_share(ctx: ContextAnalysis, days: int) -> None:
    ctx.share_token = secrets.token_urlsafe(32)
    ctx.share_expires = timezone.localdate() + timedelta(days=days)
    ctx.save(update_fields=["share_token", "share_expires"])


def disable_share(ctx: ContextAnalysis) -> None:
    ctx.share_token, ctx.share_expires = None, None
    ctx.save(update_fields=["share_token", "share_expires"])


def initial_round_summary(est: Establishment) -> dict | None:
    rnd = est.rounds.filter(kind=AssessmentRound.INITIAL).order_by("-date").first()
    if not rnd:
        return None
    return {"pk": rnd.pk, "date": rnd.date.isoformat(), **scoring.overall(results_dict(rnd))}


def context_dict(est: Establishment) -> dict:
    ctx = context_of(est)
    data = {f: getattr(ctx, f) for f in ("doc_no", "revision", "prepared_by", "prepared_position", "approved_by",
                                         "approved_position", "initial_review_note", "effectiveness_note")}
    for f in ("effective_date", "reviewed_date", "next_review"):
        data[f] = getattr(ctx, f).isoformat() if getattr(ctx, f) else ""
    data["issues"] = [{"scope": i.scope, "category_label": i.get_category_display(), "issue": i.issue,
                       "effect": i.effect, "nature_label": i.get_nature_display(), "action": i.action,
                       "responsible": i.responsible} for i in est.context_issues.all()]
    data["parties"] = [{"scope": p.scope, "party": p.party, "needs": p.needs, "is_requirement": p.is_requirement,
                        "action": p.action, "responsible": p.responsible} for p in est.interested_parties.all()]
    data["initial_round"] = initial_round_summary(est)
    return data


def build_context(est: Establishment | None, fmt: str) -> bytes:
    data = context_docx.build_context_docx(project_dict(est) if est else None,
                                           context_dict(est) if est else None, settings_dict())
    return pdf.docx_to_pdf(data) if fmt == "pdf" else data


DEFAULT_PARTIES = [
    ("ลูกจ้าง", INTERNAL, "ทำงานในสภาพแวดล้อมที่ปลอดภัย ได้รับการฝึกอบรมและอุปกรณ์คุ้มครองความปลอดภัยที่เหมาะสม "
     "มีส่วนร่วมและได้รับคำปรึกษาในเรื่องความปลอดภัยฯ", True),
    ("ผู้บริหาร / นายจ้าง", INTERNAL, "ไม่เกิดอุบัติเหตุและการเจ็บป่วยจากการทำงาน ปฏิบัติตามกฎหมาย "
     "ลดความสูญเสียและต้นทุน ได้รับการรับรองมาตรฐาน", False),
    ("คณะกรรมการความปลอดภัยฯ (คปอ.) / เจ้าหน้าที่ความปลอดภัย (จป.)", INTERNAL,
     "ได้รับการสนับสนุนทรัพยากรและอำนาจในการดำเนินงานตามกฎหมาย", True),
    ("หน่วยงานราชการ (กรมสวัสดิการและคุ้มครองแรงงาน, สำนักงานประกันสังคม ฯลฯ)", EXTERNAL,
     "ปฏิบัติตามกฎหมายความปลอดภัย อาชีวอนามัย และสภาพแวดล้อมในการทำงาน รายงานอุบัติเหตุตามที่กฎหมายกำหนด", True),
    ("ผู้รับเหมา / ผู้รับเหมาช่วง", EXTERNAL, "ได้รับข้อมูลอันตรายและข้อปฏิบัติด้านความปลอดภัยก่อนเข้าทำงาน "
     "มีพื้นที่ทำงานที่ปลอดภัย", True),
    ("ลูกค้า", EXTERNAL, "ได้รับสินค้า/บริการตามกำหนด ผู้ผลิตมีระบบการจัดการความปลอดภัยที่เชื่อถือได้", False),
    ("ผู้ส่งมอบ / ผู้ขาย", EXTERNAL, "ได้รับข้อกำหนดด้านความปลอดภัยของสินค้าและการขนส่งที่ชัดเจน", False),
    ("ชุมชนโดยรอบ", EXTERNAL, "ไม่ได้รับผลกระทบจากเหตุฉุกเฉิน มลพิษ เสียง หรือการจราจรจากการดำเนินงาน", False),
]


@transaction.atomic
def prefill_context(est: Establishment) -> tuple[int, int]:
    """Seed empty worksheets: common interested parties, plus issues from the profile's strengths/weaknesses."""
    issues = parties = 0
    if not est.interested_parties.exists():
        InterestedParty.objects.bulk_create([
            InterestedParty(establishment=est, order=n, party=party, scope=scope, needs=needs, is_requirement=req)
            for n, (party, scope, needs, req) in enumerate(DEFAULT_PARTIES)])
        parties = len(DEFAULT_PARTIES)
    if not est.context_issues.exists():
        rows = [(line, ContextIssue.OPPORTUNITY) for line in report_docx._lines(est.strengths)]
        rows += [(line, ContextIssue.RISK) for line in report_docx._lines(est.weaknesses)]
        ContextIssue.objects.bulk_create([
            ContextIssue(establishment=est, order=n, category="management", issue=text, nature=nature)
            for n, (text, nature) in enumerate(rows)])
        issues = len(rows)
    return issues, parties


def build_checklist(rnd: AssessmentRound | None, fmt: str) -> bytes:
    s = settings_dict()
    project = project_dict(rnd.establishment) if rnd else None
    rd = round_dict(rnd) if rnd else None
    if fmt == "xlsx":
        return checklist_export.build_xlsx(project, rd, s["font"])
    data = checklist_export.build_checklist_docx(project, rd, s, with_results=rnd is not None)
    return pdf.docx_to_pdf(data) if fmt == "pdf" else data
